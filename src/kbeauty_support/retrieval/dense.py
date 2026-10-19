"""Pinned official BGE-M3 ONNX dense encoder; no sparse or generative inference."""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Any, Protocol
from uuid import uuid4

from kbeauty_support.ingestion.pipeline import digest, write_file
from kbeauty_support.ingestion.sources import reject_links

MODEL_ID = "BAAI/bge-m3"
REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
DIMENSION = 1024
MAX_TOKENS = 8192
LOG = logging.getLogger(__name__)


def encoded(value: Any) -> bytes:
    """Dense artifacts contain IEEE floats; source money serialization stays separate."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


class RetrievalError(ValueError):
    """Invalid model, source generation, vectors or index state."""


class Encoder(Protocol):
    signature: dict[str, Any]

    def token_counts(self, texts: list[str]) -> list[int]: ...
    def encode(self, texts: list[str]) -> list[list[float]]: ...


def load_prepared(output: Path) -> tuple[list[dict], dict]:
    """Pin CURRENT once and verify the immutable ingestion export before use."""
    reject_links(output)
    reject_links(output / "CURRENT")
    generation = (output / "CURRENT").read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[a-f0-9]{64}", generation):
        raise RetrievalError("Invalid preparation generation")
    root = output / "generations" / generation
    reject_links(root)
    manifest_path = root / "manifest.json"
    reject_links(manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    required = {"chunks.jsonl", "catalog.snapshot.json", "validation.json"}
    if manifest.get("fingerprint") != generation or set(manifest.get("files_sha256", {})) != required:
        raise RetrievalError("Invalid preparation manifest")
    raw = {}
    for name in required:
        reject_links(root / name)
        raw[name] = (root / name).read_bytes()
        if digest(raw[name]) != manifest["files_sha256"][name]:
            raise RetrievalError("Preparation file integrity failure")
    chunks = [json.loads(line) for line in raw["chunks.jsonl"].splitlines()]
    if len(chunks) != manifest["chunk_count"] or not chunks:
        raise RetrievalError("Preparation chunk count mismatch")
    if len({c["id"] for c in chunks}) != len(chunks):
        raise RetrievalError("Duplicate chunk IDs")
    for c in chunks:
        if c["metadata"]["preparation_generation"] != generation or digest(c["text"].encode()) != c["metadata"]["chunk_sha256"]:
            raise RetrievalError("Chunk integrity failure")
    return chunks, manifest


class BgeM3Encoder:
    """One input per inference, CLS pooling, L2 normalization, CPU only."""

    def __init__(self, model_dir: Path, *, threads: int = 2):
        from tokenizers import Tokenizer

        reject_links(model_dir)
        manifest = json.loads((model_dir / "download-manifest.json").read_bytes())
        approved = json.loads(Path(__file__).with_name("bge-m3.lock.json").read_bytes())
        if manifest != approved:
            raise RetrievalError("Model manifest differs from the approved file hashes")
        required = {"model.onnx", "model.onnx_data", "Constant_7_attr__value", "tokenizer.json",
                    "tokenizer_config.json", "config.json", "special_tokens_map.json"}
        if manifest.get("model_id") != MODEL_ID or manifest.get("revision") != REVISION or set(manifest.get("files", {})) != required:
            raise RetrievalError("Model files must match the approved pinned checkpoint")
        for name, spec in manifest["files"].items():
            path = model_dir / name
            reject_links(path)
            if path.stat().st_size != spec["size"]:
                raise RetrievalError("Model file size mismatch")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != spec["sha256"]:
                    raise RetrievalError("Model SHA-256 mismatch")
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.signature = {"model_id": MODEL_ID, "revision": REVISION, "dimension": DIMENSION,
                          "max_tokens": MAX_TOKENS, "pooling": "cls", "normalize": True,
                          "format": "official-onnx-fp32", "device": "cpu", "threads": threads,
                          "runtime": {p: importlib.metadata.version(p) for p in ("onnxruntime", "tokenizers", "numpy")},
                          "files": manifest["files"]}
        self._model_dir = model_dir
        self._threads = threads
        self._session = None

    def token_counts(self, texts: list[str]) -> list[int]:
        return [len(self.tokenizer.encode(text, add_special_tokens=True).ids) for text in texts]

    def encode(self, texts: list[str]) -> list[list[float]]:
        import numpy as np
        import onnxruntime as ort

        counts = self.token_counts(texts)
        if any(n > MAX_TOKENS or n < 2 for n in counts):
            raise RetrievalError("Model token limit exceeded; truncation is forbidden")
        if self._session is None:
            options = ort.SessionOptions()
            options.intra_op_num_threads = self._threads
            options.inter_op_num_threads = 1
            options.enable_cpu_mem_arena = False
            options.enable_mem_pattern = False
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
            self._session = ort.InferenceSession(str(self._model_dir / "model.onnx"),
                                                 sess_options=options, providers=["CPUExecutionProvider"])
        session = self._session
        outputs = {o.name: o.shape for o in session.get_outputs()}
        name = next((n for n in ("last_hidden_state", "token_embeddings", "sentence_embedding", "dense_vecs") if n in outputs), None)
        if name is None:
            raise RetrievalError("Unsupported official ONNX output contract")
        vectors = []
        for text in texts:
            tokens = self.tokenizer.encode(text, add_special_tokens=True)
            values = {"input_ids": np.array([tokens.ids], dtype=np.int64),
                      "attention_mask": np.array([tokens.attention_mask], dtype=np.int64),
                      "token_type_ids": np.array([tokens.type_ids], dtype=np.int64)}
            result = session.run([name], {i.name: values[i.name] for i in session.get_inputs()})[0]
            vector = result[0, 0] if name in ("last_hidden_state", "token_embeddings") else result[0]
            vector = np.asarray(vector, dtype=np.float32)
            norm = np.linalg.norm(vector)
            if vector.shape != (DIMENSION,) or not np.isfinite(vector).all() or norm <= 0:
                raise RetrievalError("Invalid dense model output")
            vectors.append((vector / norm).tolist())
            LOG.info("dense_encoded completed=%d total=%d", len(vectors), len(texts))
        return vectors


def validate_vectors(vectors: list[list[float]], count: int, dimension: int) -> None:
    if len(vectors) != count:
        raise RetrievalError("Incomplete embedding batch")
    for vector in vectors:
        if len(vector) != dimension or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in vector):
            raise RetrievalError("Invalid vector dimension or values")
        if not math.isclose(sum(v*v for v in vector), 1.0, abs_tol=1e-4):
            raise RetrievalError("Vector is not normalized")


def embed(chunks: list[dict], source_manifest: dict, encoder: Encoder) -> dict:
    texts = [c["text"] for c in chunks]
    counts = encoder.token_counts(texts)
    if len(counts) != len(chunks) or any(not isinstance(n, int) or isinstance(n, bool) or n < 2 or n > encoder.signature["max_tokens"] for n in counts):
        raise RetrievalError("Token counts invalid or over model limit")
    vectors = encoder.encode(texts)
    validate_vectors(vectors, len(chunks), encoder.signature["dimension"])
    descriptor = {"schema_version": "dense-v1", "preparation_generation": source_manifest["fingerprint"],
                  "catalog_sha256": source_manifest["files_sha256"]["catalog.snapshot.json"],
                  "model": encoder.signature, "distance": "Cosine", "vector_name": "dense"}
    fingerprint = digest(encoded(descriptor))
    records = []
    for c, vector, count in zip(chunks, vectors, counts, strict=True):
        payload = copy.deepcopy(c)
        payload["metadata"].update(token_count=count, tokenizer_id=MODEL_ID + "@" + REVISION)
        payload["index"] = {**descriptor, "generation": fingerprint}
        records.append({"id": c["id"], "vector": vector, "payload": payload})
    artifact = {"generation": fingerprint, "descriptor": descriptor, "records": records}
    artifact["content_sha256"] = digest(encoded(artifact))
    return artifact


def validate_artifact(artifact: dict) -> None:
    body = {k: v for k, v in artifact.items() if k != "content_sha256"}
    if digest(encoded(body)) != artifact.get("content_sha256"):
        raise RetrievalError("Embedding artifact integrity failure")
    descriptor = artifact["descriptor"]
    if digest(encoded(descriptor)) != artifact["generation"] or descriptor.get("distance") != "Cosine" or descriptor.get("vector_name") != "dense":
        raise RetrievalError("Embedding generation mismatch")
    records = artifact["records"]
    if not records or len({r["id"] for r in records}) != len(records):
        raise RetrievalError("Empty or duplicate embedding records")
    validate_vectors([r["vector"] for r in records], len(records), descriptor["model"]["dimension"])
    for record in records:
        payload = record["payload"]
        if payload["id"] != record["id"] or payload["index"] != {**descriptor, "generation": artifact["generation"]}:
            raise RetrievalError("Payload belongs to another generation")
        if digest(payload["text"].encode()) != payload["metadata"]["chunk_sha256"]:
            raise RetrievalError("Payload text hash mismatch")


def save_artifact(artifact: dict, output: Path) -> Path:
    validate_artifact(artifact)
    reject_links(output)
    output.mkdir(parents=True, exist_ok=True)
    dest = output / (artifact["generation"] + ".json")
    reject_links(dest)
    content = encoded(artifact)
    if dest.exists():
        if dest.read_bytes() != content:
            raise RetrievalError("Existing immutable embedding artifact differs")
        return dest
    tmp = output / (".tmp-" + uuid4().hex)
    write_file(tmp, content)
    os.replace(tmp, dest)
    return dest
