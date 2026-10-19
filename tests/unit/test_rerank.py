"""Ordering, complete fallback and immutable retrieval contract without model downloads."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from kbeauty_support.retrieval.dense import RetrievalError, digest
from kbeauty_support.retrieval.rerank import RerankConfig, RerankedSearch


class Index:
    def __init__(self):
        self.result = {"generation": "frozen", "collection": "physical", "mode": "hybrid",
                       "hits": [{"id": str(n), "text": f"document {n}", "score": 1/(n+2),
                                 "metadata": {"source": "policy.md", "section": str(n), "document_version": "1.1"},
                                 "product": None} for n in range(10)]}
        self.calls = []

    def search(self, query, encoder, **kwargs):
        self.calls.append(kwargs)
        return copy.deepcopy({**self.result, "hits": self.result["hits"][:kwargs["limit"]]})


class Scorer:
    signature = {"test_contract_only": True}

    def score(self, query, texts):
        self.seen = query, texts
        return list(range(len(texts)))


def test_pair_scores_reorder_entire_pool_without_mutating_payload():
    index, scorer = Index(), Scorer()
    before = copy.deepcopy(index.result)
    result = RerankedSearch(index, None, lambda: scorer).search("request")
    assert [h["id"] for h in result["hits"]] == ["9", "8", "7", "6", "5"]
    assert scorer.seen == ("request", [f"document {n}" for n in range(10)])
    assert index.result == before
    assert result["generation"] == "frozen" and result["collection"] == "physical"
    assert result["reranking"]["applied"]
    assert len(result["reranking"]["positions"]) == 10
    for hit in result["hits"]:
        original = before["hits"][int(hit["id"])]
        assert all(hit[k] == v for k, v in original.items())


def test_disabled_keeps_original_top_k_and_never_loads_model():
    index = Index()
    result = RerankedSearch(index, None, lambda: pytest.fail("Model must not load"), RerankConfig(enabled=False)).search("query")
    assert result["hits"] == index.result["hits"][:5]
    assert not result["reranking"]["applied"]
    assert result["timing_ms"]["rerank"] == 0
    assert index.calls == [{"mode": "hybrid", "limit": 5, "prefetch": 20}]


@pytest.mark.parametrize("scores", [[1.0], [float("nan")]*10, [float("inf")]*10, [True]*10])
def test_invalid_scores_use_complete_original_ranking(scores):
    index = Index()
    scorer = Scorer()
    scorer.score = lambda *_: scores
    result = RerankedSearch(index, None, lambda: scorer).search("query")
    assert result["hits"] == index.result["hits"][:5]
    assert result["reranking"]["fallback_reason"] == "RetrievalError"
    assert result["reranking"]["positions"] == []


@pytest.mark.parametrize("during_load", [True, False])
def test_model_load_and_inference_failure_safe_fallback(during_load, caplog):
    def fail(*_):
        raise RuntimeError("PRIVATE QUERY MUST NOT BE LOGGED")
    scorer = Scorer()
    scorer.score = fail
    index = Index()
    result = RerankedSearch(index, None, fail if during_load else lambda: scorer).search("query")
    assert result["hits"] == index.result["hits"][:5]
    assert result["reranking"]["fallback_reason"] == "RuntimeError"
    assert "PRIVATE QUERY" not in caplog.text


def test_retrieval_errors_propagate():
    index = Index()
    def fail(*_, **__):
        raise ConnectionError("retrieval unavailable")
    index.search = fail
    with pytest.raises(ConnectionError):
        RerankedSearch(index, None, Scorer).search("query")


def test_equal_logits_preserve_rrf_order_and_empty_pool_skips_model():
    scorer = Scorer()
    scorer.score = lambda _, texts: [0.0]*len(texts)
    index = Index()
    assert RerankedSearch(index, None, lambda: scorer).search("query")["hits"][0]["id"] == "0"
    index.result["hits"] = []
    assert RerankedSearch(index, None, lambda: pytest.fail("empty pool")).search("query")["hits"] == []


def test_generation_change_during_scoring_does_not_refetch_or_mix_candidates():
    index = Index()
    scorer = Scorer()
    def switch_generation(query, texts):
        index.result["generation"] = "next"
        index.result["collection"] = "new-physical"
        index.result["hits"][0]["text"] = "new source text"
        return [0.0]*len(texts)
    scorer.score = switch_generation
    result = RerankedSearch(index, None, lambda: scorer).search("query")
    assert result["generation"] == "frozen" and result["collection"] == "physical"
    assert result["hits"][0]["text"] == "document 0"
    assert len(index.calls) == 1


@pytest.mark.parametrize("kwargs", [{"candidate_pool":4},{"candidate_pool":21},{"final_k":0},{"prefetch":9},{"enabled":1},{"candidate_pool":True}])
def test_invalid_depth_rejected(kwargs):
    with pytest.raises(RetrievalError):
        RerankConfig(**kwargs)


def test_original_relevance_labels_frozen_and_no_labels_in_ranker():
    root = Path(__file__).resolve().parents[2]
    assert digest((root/"tests/fixtures/retrieval-qrels-v1.1.json").read_bytes()) == "d7b1bbd56f943e1f9e56255b6a7fa822965ec8b480a38c6ec7a4660f848573cd"
    holdout = json.loads((root/"tests/fixtures/retrieval-holdout-v1.1.json").read_bytes())
    assert len(holdout["queries"]) == 10
    import kbeauty_support.retrieval.rerank as module
    source = Path(module.__file__).read_text(encoding="utf8")
    assert "qrels" not in source and "fixtures" not in source
