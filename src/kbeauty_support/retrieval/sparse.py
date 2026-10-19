"""Versioned Russian BM25 adapter over FastEmbed 0.7.3; server applies IDF once."""
from __future__ import annotations

import copy
import importlib.metadata
import json
import math
from pathlib import Path
import re
import unicodedata

from .dense import RetrievalError, digest, encoded, validate_artifact

ASSETS = Path(__file__).with_name("assets")
KEEP_WORDS = {"не", "нет", "без"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return re.sub(r"\bkb[-\s\u2010-\u2015]?(\d{3})\b", r"kb\1", text)


class RussianBm25:
    def __init__(self, *, avg_len: float = 256.0, stemming: bool = True):
        if not isinstance(stemming, bool):
            raise RetrievalError("Invalid stemming setting")
        if not math.isfinite(avg_len) or avg_len <= 0:
            raise RetrievalError("Invalid BM25 average length")
        if importlib.metadata.version("fastembed") != "0.7.3":
            raise RetrievalError("BM25 adapter requires FastEmbed 0.7.3")
        from fastembed.sparse.bm25 import Bm25

        asset = json.loads((ASSETS / "bm25.lock.json").read_bytes())
        if digest((ASSETS / "russian.txt").read_bytes()) != asset["russian_sha256"]:
            raise RetrievalError("Russian stopword asset SHA-256 mismatch")

        class Utf8Bm25(Bm25):
            @classmethod
            def _load_stopwords(cls, model_dir: Path, language: str) -> list[str]:
                return [normalize(w) for w in (model_dir / (language + ".txt")).read_text(encoding="utf-8").splitlines()]

        self.model = Utf8Bm25("Qdrant/bm25", specific_model_path=str(ASSETS),
                             local_files_only=True, language="russian", k=1.2, b=0.75,
                             avg_len=avg_len, token_max_length=40, disable_stemmer=not stemming)
        # FastEmbed disables stopwords together with stemming: keep stopwords independent.
        self.model.stopwords = set(Utf8Bm25._load_stopwords(ASSETS, "russian")) - KEEP_WORDS
        self.signature = {**asset, "analyzer_version": "ru-bm25-v1", "normalization": "NFKC+casefold+yo-e+sku-kbNNN",
                          "language": "russian", "stemming": stemming, "keep_stopwords": sorted(KEEP_WORDS),
                          "k": 1.2, "b": 0.75, "avg_len": avg_len, "token_max_length": 40,
                          "modifier": "idf", "text_view": "full-source-text", "unicode_version": unicodedata.unidata_version,
                          "runtime": {p: importlib.metadata.version(p) for p in ("fastembed", "py-rust-stemmers", "mmh3")}}

    def tokens(self, text: str) -> list[str]:
        from fastembed.common.utils import remove_non_alphanumeric
        return self.model._stem(self.model.tokenizer.tokenize(remove_non_alphanumeric(normalize(text))))

    def document(self, text: str) -> dict:
        return self._plain(self.model.raw_embed([normalize(text)])[0])

    def query(self, text: str) -> dict:
        return self._plain(next(self.model.query_embed(normalize(text))))

    @staticmethod
    def _plain(vector) -> dict:
        pairs = sorted(zip(vector.indices.tolist(), vector.values.tolist(), strict=True))
        return {"indices": [int(i) for i, _ in pairs], "values": [float(v) for _, v in pairs]}


def build_hybrid(dense: dict, *, stemming: bool = True) -> dict:
    validate_artifact(dense)
    texts = [r["payload"]["text"] for r in dense["records"]]
    analyzer = RussianBm25(stemming=stemming)
    tokens = [analyzer.tokens(text) for text in texts]
    # Fail on a hash collision within this corpus rather than silently merge terms.
    ids: dict[int, str] = {}
    for term in {token for row in tokens for token in row}:
        identity = analyzer.model.compute_token_id(term)
        if identity >= 2**31 or identity in ids and ids[identity] != term:
            raise RetrievalError("BM25 vocabulary hash collision or unsupported int32 ID")
        ids[identity] = term
    avg_len = sum(map(len, tokens)) / len(tokens)
    analyzer = RussianBm25(avg_len=avg_len, stemming=stemming)
    descriptor = {**dense["descriptor"], "schema_version": "hybrid-v1", "sparse_model": analyzer.signature,
                  "dense_artifact_sha256": dense["content_sha256"]}
    generation = digest(encoded(descriptor))
    records = copy.deepcopy(dense["records"])
    for record in records:
        record["bm25"] = analyzer.document(record["payload"]["text"])
        record["payload"]["sparse_sha256"] = digest(encoded(record["bm25"]))
        record["payload"]["index"] = {**descriptor, "generation": generation}
    artifact = {"generation": generation, "descriptor": descriptor, "records": records}
    artifact["content_sha256"] = digest(encoded(artifact))
    validate_hybrid(artifact)
    return artifact


def validate_sparse(vector: dict, *, allow_empty: bool = False) -> None:
    indices, values = vector["indices"], vector["values"]
    if (not allow_empty and not indices) or len(indices) != len(values) or indices != sorted(set(indices)):
        raise RetrievalError("Sparse vector empty, duplicate or unsorted")
    if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < 2**31 for i in indices):
        raise RetrievalError("Invalid sparse vector index")
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v <= 0 for v in values):
        raise RetrievalError("Invalid sparse vector weight")


def validate_hybrid(artifact: dict) -> None:
    validate_artifact(artifact, expected_schema="hybrid-v1")
    spec = artifact["descriptor"]["sparse_model"]
    analyzer = RussianBm25(avg_len=spec["avg_len"], stemming=spec["stemming"])
    if analyzer.signature != spec:
        raise RetrievalError("Sparse analyzer signature mismatch")
    texts = [r["payload"]["text"] for r in artifact["records"]]
    if sum(len(analyzer.tokens(t)) for t in texts) / len(texts) != spec["avg_len"]:
        raise RetrievalError("BM25 corpus length mismatch")
    for record in artifact["records"]:
        validate_sparse(record["bm25"])
        if record["bm25"] != analyzer.document(record["payload"]["text"]) or record["payload"]["sparse_sha256"] != digest(encoded(record["bm25"])):
            raise RetrievalError("Dense/sparse text representation mismatch")
