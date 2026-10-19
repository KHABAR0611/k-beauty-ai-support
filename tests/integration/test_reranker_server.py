"""Real ONNX pair inference above the existing Qdrant Server generation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

import pytest

from kbeauty_support.retrieval.dense import BgeM3Encoder, RetrievalError
from kbeauty_support.retrieval.hybrid import HybridIndex
from kbeauty_support.retrieval.rerank import MiniLMCrossEncoder, RerankConfig, RerankedSearch

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def runtime():
    if os.environ.get("KBEAUTY_RERANK_SERVER_TESTS") != "1":
        pytest.skip("Explicit real reranker Server opt-in required")
    from qdrant_client import QdrantClient
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=30, trust_env=False)
    encoder = BgeM3Encoder(Path(os.environ["KBEAUTY_MODEL_DIR"]))
    encoder.encode(["Разогрев поиска перед проверкой reranker"])
    scorer = MiniLMCrossEncoder(Path(os.environ["KBEAUTY_RERANKER_DIR"]))
    index = HybridIndex(client)
    try:
        yield client, index, encoder, scorer
    finally:
        client.close()


def test_actual_pair_logits_and_no_truncation(runtime):
    _, _, _, scorer = runtime
    scores = scorer.score("Как вернуть повреждённый товар?", ["Повреждение: приложите фото и обратитесь в поддержку.",
                                                          "Крем предназначен для сухой кожи."])
    assert scores[0] > scores[1]
    with pytest.raises(RetrievalError, match="512"):
        scorer.score("товар "*600, ["описание"])


def test_real_pool_reordering_is_reproducible_and_preserves_payload(runtime):
    _, index, encoder, scorer = runtime
    query = "Развернула посылку только на третий день, а баночка разбита. Срок жалобы уже вышел?"
    search = RerankedSearch(index, encoder, lambda: scorer)
    first, second = search.search(query), search.search(query)
    assert first["reranking"]["applied"] and second["reranking"]["applied"]
    assert first["hits"] == second["hits"]
    original = index.search(query, encoder, limit=10)
    by_id = {h["id"]: h for h in original["hits"]}
    assert first["generation"] == original["generation"]
    for hit in first["hits"]:
        assert all(hit[k] == value for k, value in by_id[hit["id"]].items())
    assert sorted(p["after"] for p in first["reranking"]["positions"]) == list(range(1, 11))


def test_disabled_and_failed_model_equal_real_hybrid(runtime):
    _, index, encoder, _ = runtime
    query = "KB-005"
    original = index.search(query, encoder)
    def fail():
        raise RuntimeError("Injected model initialization failure")
    off = RerankedSearch(index, encoder, fail, RerankConfig(enabled=False)).search(query)
    failed = RerankedSearch(index, encoder, fail).search(query)
    assert off["hits"] == failed["hits"] == original["hits"]
    assert not off["reranking"]["applied"]
    assert failed["reranking"]["fallback_reason"] == "RuntimeError"


def test_missing_or_tampered_model_rejected_before_inference(runtime, tmp_path):
    with pytest.raises(FileNotFoundError):
        MiniLMCrossEncoder(tmp_path)
    lock = json.loads((ROOT/"src/kbeauty_support/retrieval/reranker.lock.json").read_bytes())
    lock["revision"] = "unapproved"
    (tmp_path/"download-manifest.json").write_text(json.dumps(lock), encoding="utf8")
    with pytest.raises(RetrievalError, match="manifest"):
        MiniLMCrossEncoder(tmp_path)


def test_actual_token_counts_cover_all_frozen_queries_without_truncation(runtime):
    _, _, _, scorer = runtime
    artifact = json.loads(Path(os.environ["KBEAUTY_HYBRID_ARTIFACT"]).read_bytes())
    texts = [r["payload"]["text"] for r in artifact["records"]]
    for name in ("retrieval-qrels-v1.1.json", "retrieval-holdout-v1.1.json"):
        labels = json.loads((ROOT/"tests/fixtures"/name).read_bytes())
        for case in labels["queries"]:
            assert max(scorer.pair_token_counts(case["query"], texts)) <= 512


def test_restart_keeps_actual_reranked_results_and_points(runtime):
    if os.environ.get("KBEAUTY_ALLOW_SMOKE_RESTART") != "1":
        pytest.skip("Explicit restart opt-in required")
    assert os.environ["QDRANT_URL"] == "http://127.0.0.1:6394"
    client, index, encoder, scorer = runtime
    search = RerankedSearch(index, encoder, lambda: scorer)
    before = search.search("За сколько дней возвращают деньги за товар?")
    points_before, _ = client.scroll(index.resolve(), limit=64, with_vectors=True)
    subprocess.run(["docker", "compose", "-p", "kbeauty-review-check", "restart", "qdrant"], cwd=ROOT,
                   env=dict(os.environ, QDRANT_HTTP_PORT="6394"), check=True, capture_output=True, timeout=60)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic()+180
    ready = False
    while time.monotonic() < deadline:
        try:
            request = urllib.request.Request(os.environ["QDRANT_URL"]+"/readyz", headers={"api-key":os.environ["QDRANT_API_KEY"]})
            with opener.open(request, timeout=5) as response:
                ready = response.status == 200
            if ready:
                break
        except OSError:
            pass
        time.sleep(1)
    assert ready
    after = search.search("За сколько дней возвращают деньги за товар?")
    assert before["hits"] == after["hits"] and before["generation"] == after["generation"]
    points_after, _ = client.scroll(index.resolve(), limit=64, with_vectors=True)
    assert {str(p.id): (p.payload, p.vector) for p in points_before} == {str(p.id): (p.payload, p.vector) for p in points_after}
