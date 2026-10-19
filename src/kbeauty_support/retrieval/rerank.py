"""Optional pairwise cross-encoder over a single pinned Hybrid candidate pool."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import logging
import math
from pathlib import Path
import time
from typing import Callable, Protocol

from kbeauty_support.ingestion.sources import reject_links
from .dense import Encoder, RetrievalError

MODEL_ID = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
REVISION = "1427fd652930e4ba29e8149678df786c240d8825"
LOG = logging.getLogger(__name__)


class PairScorer(Protocol):
    signature: dict

    def score(self, query: str, texts: list[str]) -> list[float]: ...


class HybridRetriever(Protocol):
    def search(self, query: str, encoder: Encoder | None = None, *, mode: str = "hybrid",
               limit: int = 5, prefetch: int = 20) -> dict: ...


class MiniLMCrossEncoder:
    """Official FP32 ONNX, raw scalar logits, batch one, no truncation."""

    def __init__(self, model_dir: Path, *, threads: int = 2):
        from tokenizers import Tokenizer

        if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 16:
            raise RetrievalError("Invalid reranker thread count")
        approved = json.loads(Path(__file__).with_name("reranker.lock.json").read_bytes())
        reject_links(model_dir)
        reject_links(model_dir / "download-manifest.json")
        if json.loads((model_dir / "download-manifest.json").read_bytes()) != approved:
            raise RetrievalError("Unapproved reranker manifest")
        for name, spec in approved["files"].items():
            path = model_dir / name
            reject_links(path)
            with path.open("rb") as stream:
                if path.stat().st_size != spec["size"] or hashlib.file_digest(stream, "sha256").hexdigest() != spec["sha256"]:
                    raise RetrievalError("Reranker file integrity failure")
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.signature = {"model_id": MODEL_ID, "revision": REVISION, "format": "official-onnx-fp32",
                          "max_pair_tokens": 512, "device": "cpu", "threads": threads, "batch_size": 1,
                          "activation": "identity", "truncation": False, "files": approved["files"],
                          "runtime": {p: importlib.metadata.version(p) for p in ("onnxruntime", "tokenizers", "numpy")}}
        self._model_dir = model_dir
        self._threads = threads
        self._session = None

    def pair_token_counts(self, query: str, texts: list[str]) -> list[int]:
        return [len(self.tokenizer.encode(query, text, add_special_tokens=True).ids) for text in texts]

    def score(self, query: str, texts: list[str]) -> list[float]:
        import numpy as np
        import onnxruntime as ort

        if not query.strip() or any(not text.strip() for text in texts):
            raise RetrievalError("Empty reranker input")
        pairs = [self.tokenizer.encode(query, text, add_special_tokens=True) for text in texts]
        if any(len(pair.ids) > 512 for pair in pairs):
            raise RetrievalError("Reranker pair exceeds 512 tokens; truncation forbidden")
        if not pairs:
            return []
        if self._session is None:
            options = ort.SessionOptions()
            options.intra_op_num_threads = self._threads
            options.inter_op_num_threads = 1
            options.enable_cpu_mem_arena = False
            options.enable_mem_pattern = False
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
            self._session = ort.InferenceSession(str(self._model_dir / "model.onnx"), sess_options=options,
                                                 providers=["CPUExecutionProvider"])
        session = self._session
        if [o.name for o in session.get_outputs()] != ["logits"]:
            raise RetrievalError("Unsupported reranker output contract")
        scores = []
        for pair in pairs:
            values = {"input_ids": np.array([pair.ids], dtype=np.int64),
                      "attention_mask": np.array([pair.attention_mask], dtype=np.int64),
                      "token_type_ids": np.array([pair.type_ids], dtype=np.int64)}
            raw = np.asarray(session.run(["logits"], {i.name: values[i.name] for i in session.get_inputs()})[0])
            if raw.shape != (1, 1) or not np.isfinite(raw).all():
                raise RetrievalError("Invalid reranker output")
            scores.append(float(raw[0, 0]))
        return scores


@dataclass(frozen=True)
class RerankConfig:
    candidate_pool: int = 10
    final_k: int = 5
    prefetch: int = 20
    enabled: bool = True

    def __post_init__(self) -> None:
        if (any(isinstance(n, bool) or not isinstance(n, int) for n in (self.candidate_pool, self.final_k, self.prefetch))
                or not 1 <= self.final_k <= self.candidate_pool <= 20
                or not self.candidate_pool <= self.prefetch <= 100 or not isinstance(self.enabled, bool)):
            raise RetrievalError("Invalid reranking configuration")


class RerankedSearch:
    """Reranker errors fall back atomically; retrieval errors propagate."""

    def __init__(self, index: HybridRetriever, encoder: Encoder | None,
                 scorer_factory: Callable[[], PairScorer], config: RerankConfig | None = None):
        self.index = index
        self.encoder = encoder
        self.config = config or RerankConfig()
        self._factory = scorer_factory
        self._scorer: PairScorer | None = None

    def search(self, query: str) -> dict:
        cfg = self.config
        started = time.perf_counter()
        result = self.index.search(query, self.encoder, mode="hybrid",
                                   limit=cfg.candidate_pool if cfg.enabled else cfg.final_k, prefetch=cfg.prefetch)
        retrieval_ms = (time.perf_counter() - started) * 1000
        candidates = result["hits"]
        output = {**result, "hits": candidates[:cfg.final_k]}
        info = {"enabled": cfg.enabled, "applied": False, "fallback_reason": None,
                "requested_pool": cfg.candidate_pool, "candidate_count": len(candidates),
                "final_k": cfg.final_k, "positions": []}
        rerank_ms = 0.0
        if cfg.enabled and candidates:
            rerank_started = time.perf_counter()
            try:
                if self._scorer is None:
                    self._scorer = self._factory()
                scores = self._scorer.score(query, [hit["text"] for hit in candidates])
                if (len(scores) != len(candidates) or any(isinstance(s, bool) or not isinstance(s, (float, int))
                                                        or not math.isfinite(s) for s in scores)):
                    raise RetrievalError("Incomplete or invalid reranker scores")
                order = sorted(range(len(candidates)), key=lambda n: (-scores[n], n))
                positions = {n: rank for rank, n in enumerate(order, 1)}
                info.update(applied=True, model=self._scorer.signature,
                            positions=[{"id": h["id"], "before": n+1, "after": positions[n],
                                        "rerank_score": scores[n]} for n, h in enumerate(candidates)])
                output["hits"] = [{**candidates[n], "rerank_score": scores[n], "original_rank": n+1}
                                  for n in order[:cfg.final_k]]
                LOG.info("rerank_positions %s", json.dumps(info["positions"], sort_keys=True))
            except Exception as exc:
                # Do not log exception strings: SDK/model errors may contain input data or paths.
                info["fallback_reason"] = type(exc).__name__
                LOG.warning("rerank_fallback category=%s", type(exc).__name__)
            rerank_ms = (time.perf_counter() - rerank_started) * 1000
        output["reranking"] = info
        output["timing_ms"] = {"retrieval": retrieval_ms, "rerank": rerank_ms,
                                "total": (time.perf_counter() - started) * 1000}
        return output
