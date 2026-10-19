"""Dense/BM25 searches and server-side reciprocal rank fusion on one generation."""
from __future__ import annotations

import math

from .dense import Encoder, RetrievalError, validate_vectors
from .index import DenseIndex
from .sparse import RussianBm25, validate_hybrid, validate_sparse


def stable_fused_hits(points: list, limit: int) -> list:
    """Tie-break the full fused candidate union before applying the visible top-k."""
    return sorted(points, key=lambda point: (-point.score, str(point.id)))[:limit]


class HybridIndex(DenseIndex):
    collection_prefix = "kbeauty_hybrid_"
    validator = staticmethod(validate_hybrid)

    def _create(self, name: str, artifact: dict) -> None:
        from qdrant_client import models as m
        self.client.create_collection(name, vectors_config={"dense": m.VectorParams(
            size=artifact["descriptor"]["model"]["dimension"], distance=m.Distance.COSINE)},
            sparse_vectors_config={"bm25": m.SparseVectorParams(modifier=m.Modifier.IDF)}, on_disk_payload=True)

    def _verify_config(self, info, artifact: dict) -> None:
        super()._verify_config(info, artifact)
        sparse = info.config.params.sparse_vectors
        if not sparse or set(sparse) != {"bm25"} or sparse["bm25"].modifier.value != "idf":
            raise RetrievalError("Qdrant sparse configuration mismatch")

    def _vectors(self, record: dict) -> dict:
        from qdrant_client import models as m
        return {"dense": record["vector"], "bm25": m.SparseVector(**record["bm25"])}

    def _verify_vector(self, vector, record: dict, dimension: int) -> None:
        super()._verify_vector(vector, record, dimension)
        sparse = vector.get("bm25")
        if sparse is None or sparse.indices != record["bm25"]["indices"] or len(sparse.values) != len(record["bm25"]["values"]):
            raise RetrievalError("Qdrant sparse indices readback mismatch")
        if not all(math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-6) for a, b in zip(sparse.values, record["bm25"]["values"], strict=True)):
            raise RetrievalError("Qdrant sparse weights readback mismatch")

    def _smoke(self, name: str, artifact: dict) -> None:
        from qdrant_client import models as m
        super()._smoke(name, artifact)
        sparse = m.SparseVector(**artifact["records"][0]["bm25"])
        for kwargs in ({"query": sparse, "using": "bm25"},
                       {"query": m.FusionQuery(fusion=m.Fusion.RRF), "prefetch": [
                           m.Prefetch(query=artifact["records"][0]["vector"], using="dense", limit=20),
                           m.Prefetch(query=sparse, using="bm25", limit=20)]}):
            if not self.client.query_points(name, limit=1, **kwargs).points:
                raise RetrievalError("Sparse/RRF search smoke returned no points")

    def search(self, query: str, encoder: Encoder | None = None, *, mode: str = "hybrid", limit: int = 5,
               prefetch: int = 20) -> dict:
        from qdrant_client import models as m
        if (mode not in {"dense", "bm25", "hybrid"} or not query.strip() or len(query) > 12000
                or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20
                or isinstance(prefetch, bool) or not isinstance(prefetch, int) or not limit <= prefetch <= 100):
            raise RetrievalError("Invalid retrieval mode, query or search depth")
        collection = self.resolve()
        if collection is None:
            raise RetrievalError("No published hybrid index")
        sample, _ = self.client.scroll(collection, limit=1, with_payload=True)
        if not sample or sample[0].payload["index"].get("schema_version") != "hybrid-v1":
            raise RetrievalError("Published collection is not a hybrid generation")
        descriptor = sample[0].payload["index"]
        spec = descriptor["sparse_model"]
        analyzer = RussianBm25(avg_len=spec["avg_len"], stemming=spec["stemming"])
        if analyzer.signature != spec:
            raise RetrievalError("Sparse query analyzer differs from the index")
        dense = None
        if mode != "bm25":
            if encoder is None or encoder.signature != descriptor["model"]:
                raise RetrievalError("Query encoder differs from the published model")
            vectors = encoder.encode([query])
            validate_vectors(vectors, 1, descriptor["model"]["dimension"])
            dense = vectors[0]
        sparse = analyzer.query(query) if mode != "dense" else {"indices": [], "values": []}
        validate_sparse(sparse, allow_empty=True)
        if mode == "dense":
            kwargs = {"query": dense, "using": "dense"}
        elif mode == "bm25":
            if not sparse["indices"]:
                return {"collection": collection, "generation": descriptor["generation"], "mode": mode, "hits": []}
            kwargs = {"query": m.SparseVector(**sparse), "using": "bm25"}
        else:
            branches = [m.Prefetch(query=dense, using="dense", limit=prefetch)]
            if sparse["indices"]:
                branches.append(m.Prefetch(query=m.SparseVector(**sparse), using="bm25", limit=prefetch))
            kwargs = {"query": m.FusionQuery(fusion=m.Fusion.RRF), "prefetch": branches}
        # Qdrant1.15.1 RRF does not break equal-score ties; request the full union.
        response_limit = 2 * prefetch if mode == "hybrid" else limit
        hits = self.client.query_points(collection, limit=response_limit, with_payload=True, **kwargs).points
        if mode == "hybrid":
            hits = stable_fused_hits(hits, limit)
        if any(p.payload["index"] != descriptor for p in hits):
            raise RetrievalError("Mixed hybrid generations")
        return {"collection": collection, "generation": descriptor["generation"], "mode": mode,
                "hits": [{"id": str(p.id), "score": p.score, "text": p.payload["text"],
                          "metadata": p.payload["metadata"], "product": p.payload.get("product"),
                          "price_kopecks": p.payload.get("price_kopecks")} for p in hits]}
