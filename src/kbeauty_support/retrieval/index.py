"""Verify a complete physical collection, then publish with one alias transaction."""
from __future__ import annotations

from contextlib import contextmanager
import logging
import math
import os
from pathlib import Path
import re
from typing import Iterator

from kbeauty_support.ingestion.sources import reject_links
from .dense import Encoder, RetrievalError, validate_artifact, validate_vectors

LOG = logging.getLogger(__name__)


@contextmanager
def writer_lock(root: Path) -> Iterator[None]:
    reject_links(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".publish.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RetrievalError("Index writer lock is held; check for a live writer before manual recovery") from exc
    try:
        yield
    finally:
        os.close(fd)
        lock.unlink()


class DenseIndex:
    def __init__(self, client, *, alias: str = "kbeauty_active"):
        if not re.fullmatch(r"kbeauty_[a-zA-Z0-9_]+", alias):
            raise RetrievalError("Alias must use the kbeauty_ namespace")
        self.client = client
        self.alias = alias

    def resolve(self) -> str | None:
        aliases = self.client.get_aliases().aliases
        return next((a.collection_name for a in aliases if a.alias_name == self.alias), None)

    def _verify(self, name: str, artifact: dict) -> None:
        info = self.client.get_collection(name)
        config = info.config.params.vectors
        dimension = artifact["descriptor"]["model"]["dimension"]
        if not isinstance(config, dict) or set(config) != {"dense"} or config["dense"].size != dimension or config["dense"].distance.value != "Cosine":
            raise RetrievalError("Collection vector configuration mismatch")
        expected = {r["id"]: r for r in artifact["records"]}
        actual = {}
        offset = None
        while True:
            points, offset = self.client.scroll(name, limit=64, offset=offset, with_payload=True, with_vectors=True)
            for point in points:
                actual[str(point.id)] = point
            if offset is None:
                break
        if set(actual) != set(expected) or self.client.count(name, exact=True).count != len(expected):
            raise RetrievalError("Incomplete collection or stale points")
        for identity, record in expected.items():
            point = actual[identity]
            if point.payload != record["payload"]:
                raise RetrievalError("Qdrant payload integrity failure")
            vector = point.vector.get("dense", []) if isinstance(point.vector, dict) else []
            if len(vector) != dimension or not all(math.isclose(a, b, rel_tol=1e-4, abs_tol=1e-6) for a, b in zip(vector, record["vector"], strict=True)):
                raise RetrievalError("Qdrant vector readback mismatch")

    def publish(self, artifact: dict, lock_dir: Path, *, batch_size: int = 4) -> dict:
        from qdrant_client import models as m

        validate_artifact(artifact)
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise RetrievalError("Invalid indexing batch size")
        generation = artifact["generation"]
        name = "kbeauty_dense_" + generation
        with writer_lock(lock_dir):
            current = self.resolve()
            if current == name:
                self._verify(name, artifact)
                LOG.info("index_verified_noop generation=%s", generation)
                return {"collection": name, "points": len(artifact["records"]), "status": "noop"}
            if not self.client.collection_exists(name):
                self.client.create_collection(name, vectors_config={"dense": m.VectorParams(
                    size=artifact["descriptor"]["model"]["dimension"], distance=m.Distance.COSINE)},
                    on_disk_payload=True)
            else:
                # Resume only our deterministic generation. Never write to an active collection.
                if any(a.collection_name == name for a in self.client.get_aliases().aliases):
                    self._verify(name, artifact)
                    return self._switch(name, current, artifact)
                existing, _ = self.client.scroll(name, limit=1, with_payload=True)
                if existing and existing[0].payload.get("index") != {**artifact["descriptor"], "generation": generation}:
                    raise RetrievalError("Staging collection ownership mismatch")
            for start in range(0, len(artifact["records"]), batch_size):
                batch = artifact["records"][start:start + batch_size]
                self.client.upsert(name, points=[m.PointStruct(id=r["id"], vector={"dense": r["vector"]}, payload=r["payload"]) for r in batch], wait=True)
                LOG.info("index_batch generation=%s completed=%d", generation, start + len(batch))
            self._verify(name, artifact)
            # A real search smoke must also succeed before publication.
            hits = self.client.query_points(name, query=artifact["records"][0]["vector"], using="dense", limit=1).points
            if not hits:
                raise RetrievalError("Staging search smoke returned no points")
            return self._switch(name, current, artifact)

    def _switch(self, name: str, previous: str | None, artifact: dict) -> dict:
        from qdrant_client import models as m

        if self.resolve() != previous:
            raise RetrievalError("Alias changed during publication; refusing to overwrite")
        operations = []
        if previous is not None:
            operations.append(m.DeleteAliasOperation(delete_alias=m.DeleteAlias(alias_name=self.alias)))
        operations.append(m.CreateAliasOperation(create_alias=m.CreateAlias(collection_name=name, alias_name=self.alias)))
        self.client.update_collection_aliases(change_aliases_operations=operations)
        if self.resolve() != name:
            raise RetrievalError("Alias publication not confirmed; inspect server before retry")
        LOG.info("index_published generation=%s points=%d", artifact["generation"], len(artifact["records"]))
        return {"collection": name, "previous_collection": previous, "points": len(artifact["records"]), "status": "published"}

    def search(self, query: str, encoder: Encoder, *, limit: int = 5) -> dict:
        if not query.strip() or len(query) > 12000 or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise RetrievalError("Invalid query or search limit")
        collection = self.resolve()
        if collection is None:
            raise RetrievalError("No published index")
        # Resolve exactly once; every subsequent operation pins the physical generation.
        sample, _ = self.client.scroll(collection, limit=1, with_payload=True)
        if not sample or sample[0].payload["index"]["model"] != encoder.signature:
            raise RetrievalError("Query encoder differs from the published model")
        descriptor = sample[0].payload["index"]
        vector = encoder.encode([query])
        validate_vectors(vector, 1, encoder.signature["dimension"])
        hits = self.client.query_points(collection, query=vector[0], using="dense", limit=limit, with_payload=True).points
        if any(p.payload["index"] != descriptor for p in hits):
            raise RetrievalError("Mixed index generations")
        return {"collection": collection, "generation": descriptor["generation"],
                "hits": [{"id": str(p.id), "score": p.score, "text": p.payload["text"],
                          "metadata": p.payload["metadata"], "product": p.payload.get("product"),
                          "price_kopecks": p.payload.get("price_kopecks")} for p in hits]}
