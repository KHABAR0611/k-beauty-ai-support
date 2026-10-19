from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

pytest.importorskip("fastembed")
from qdrant_client import QdrantClient, models as m
from kbeauty_support.ingestion.pipeline import prepare, export
from kbeauty_support.retrieval.dense import RetrievalError, encoded, digest, embed, load_prepared, save_artifact
from kbeauty_support.retrieval.sparse import RussianBm25, normalize, build_hybrid, validate_hybrid
from kbeauty_support.retrieval.hybrid import HybridIndex, stable_fused_hits
from kbeauty_support.retrieval.evaluation import reciprocal_rank, percentile
from test_dense_index import ContractEncoder

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def dense(tmp_path):
    bundle = prepare(ROOT / "data")
    export(bundle, tmp_path / "prepared", ROOT / "data")
    chunks, manifest = load_prepared(tmp_path / "prepared")
    return embed(chunks, manifest, ContractEncoder())


@pytest.fixture
def artifact(dense):
    return build_hybrid(dense)


@pytest.fixture
def index():
    client = QdrantClient(":memory:")
    try:
        yield HybridIndex(client)
    finally:
        client.close()


@pytest.mark.parametrize("forms", [
    ["доставка", "доставки", "доставкой"], ["бонусы", "бонусами"],
    ["ниацинамид", "ниацинамидом"], ["керамиды", "керамидами"],
    ["KB-004", "kb004", "KB‑004", "KB 004"], ["ёлка", "елка"],
    ["JEJU CLOUD", "Jeju Cloud"], ["WELCOME10", "welcome10"]])
def test_analyzer_equivalent_forms(forms):
    analyzer = RussianBm25()
    outputs = [analyzer.query(text) for text in forms]
    assert all(output == outputs[0] and output["indices"] for output in outputs)


def test_stemming_is_not_translation_or_full_lemmatization():
    analyzer = RussianBm25()
    assert analyzer.query("ниацинамид") != analyzer.query("niacinamide")
    assert analyzer.query("возврат") != analyzer.query("вернуть")
    assert analyzer.query("Jeju") != analyzer.query("Джеджу")
    assert analyzer.query("KB-004") != analyzer.query("KB-005")


def test_stopwords_utf8_and_negations_preserved():
    analyzer = RussianBm25()
    assert analyzer.tokens("и на в") == []
    assert analyzer.tokens("не нет без") == ["не", "нет", "без"]
    assert RussianBm25(stemming=False).tokens("и на в") == []


def test_query_weights_are_binary_without_client_idf():
    analyzer = RussianBm25()
    assert set(analyzer.query("крем крем крем")['values']) == {1.0}
    doc = analyzer.document("крем крем крем")
    assert len(doc['indices']) == 1 and doc['values'][0] > 1.0


def test_hybrid_reuses_exact_dense_and_product_payload(dense, artifact, tmp_path):
    assert len(artifact["records"]) == 20
    for original, current in zip(dense["records"], artifact["records"], strict=True):
        assert current["id"] == original["id"]
        assert current["vector"] == original["vector"]
        assert current["payload"]["text"] == original["payload"]["text"]
        assert current["payload"].get("product") == original["payload"].get("product")
        assert current["bm25"]["indices"]
    assert build_hybrid(dense) == artifact
    save_artifact(artifact, tmp_path / "hybrid", validator=validate_hybrid)


def test_sparse_tampering_rejected_even_with_rehashed_outer_artifact(artifact):
    artifact["records"][0]["bm25"]["values"][0] += 1
    artifact["content_sha256"] = digest(encoded({k:v for k,v in artifact.items() if k!='content_sha256'}))
    with pytest.raises(RetrievalError, match="representation mismatch"):
        validate_hybrid(artifact)


def test_three_modes_and_noop(index, artifact, tmp_path):
    index.publish(artifact, tmp_path)
    assert index.publish(artifact, tmp_path)["status"] == "noop"
    for mode in ("dense", "bm25", "hybrid"):
        hits = index.search("KB-004", ContractEncoder() if mode!='bm25' else None, mode=mode)["hits"]
        assert hits
        if mode == "bm25":
            assert hits[0]["metadata"]["section"] == "KB-004"
    assert index.search("и на в", mode="bm25")["hits"] == []


def test_query_analyzer_mismatch_blocks_search(index, artifact, tmp_path, monkeypatch):
    index.publish(artifact, tmp_path)
    real_init = RussianBm25.__init__
    def altered(self, **kwargs):
        real_init(self, **kwargs)
        self.signature["b"] = 0.1
    monkeypatch.setattr(RussianBm25, "__init__", altered)
    with pytest.raises(RetrievalError, match="analyzer differs"):
        index.search("KB-004", mode="bm25")


def test_server_rrf_uses_rank_order_not_raw_scores(index):
    # Deliberately different dense/sparse score scales; source ranks define fusion.
    name="rrf_contract"
    index.client.create_collection(name,vectors_config={"dense":m.VectorParams(size=2,distance=m.Distance.COSINE)},
        sparse_vectors_config={"bm25":m.SparseVectorParams(modifier=m.Modifier.IDF)})
    index.client.upsert(name,points=[
        m.PointStruct(id=1,vector={"dense":[1.0,0.0],"bm25":m.SparseVector(indices=[1],values=[1.0])}),
        m.PointStruct(id=2,vector={"dense":[0.0,1.0],"bm25":m.SparseVector(indices=[1],values=[1000.0])})])
    result=index.client.query_points(name,query=m.FusionQuery(fusion=m.Fusion.RRF),prefetch=[
        m.Prefetch(query=[1.0,0.0],using="dense",limit=2),
        m.Prefetch(query=m.SparseVector(indices=[1],values=[1.0]),using="bm25",limit=2)],limit=2).points
    assert all(math.isclose(point.score,1/2+1/3,rel_tol=1e-5) for point in result)


def test_metrics_definitions():
    assert reciprocal_rank(["bad","good","other"],["good"]) == 0.5
    assert reciprocal_rank(["bad"],["good"]) == 0
    assert percentile([1,2,3,4,5],50) == 3
    assert percentile([1,2,3,4,5],95) == 5


def test_rrf_ties_at_cutoff_are_stable_before_top_k():
    from types import SimpleNamespace
    points=[SimpleNamespace(id=str(i),score=0.33333334) for i in (6,5,4,3,2,1)]
    assert [p.id for p in stable_fused_hits(points,5)]==['1','2','3','4','5']
    assert [p.id for p in stable_fused_hits(list(reversed(points)),5)]==['1','2','3','4','5']
