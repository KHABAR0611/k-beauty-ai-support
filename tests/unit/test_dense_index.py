from __future__ import annotations

import copy
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path

import pytest

from kbeauty_support.ingestion.pipeline import prepare, export, digest, encoded
from kbeauty_support.retrieval.dense import RetrievalError, embed, load_prepared, save_artifact, validate_artifact
from kbeauty_support.retrieval.evaluation import recall

ROOT = Path(__file__).resolve().parents[2]


class ContractEncoder:
    """Synthetic deterministic vectors for protocol tests, never for quality scores."""
    signature = {"model_id": "synthetic-contract-test", "dimension": 3, "max_tokens": 8192}

    def token_counts(self, texts):
        return [len(t.split()) + 2 for t in texts]

    def encode(self, texts):
        vectors = []
        for text in texts:
            values = [b + 1 for b in hashlib.sha256(text.encode()).digest()[:3]]
            norm = math.sqrt(sum(v*v for v in values))
            vectors.append([v / norm for v in values])
        return vectors


@pytest.fixture
def prepared(tmp_path):
    bundle = prepare(ROOT / "data")
    output = tmp_path / "prepared"
    export(bundle, output, ROOT / "data")
    return output, *load_prepared(output)


@pytest.fixture
def artifact(prepared):
    _, chunks, manifest = prepared
    return embed(chunks, manifest, ContractEncoder())


def changed_artifact(prepared):
    _, chunks, manifest = copy.deepcopy(prepared)
    chunks = chunks[:-1]
    chunks[0]["text"] += "\nИзменение для теста контракта индекса."
    chunks[0]["metadata"]["chunk_sha256"] = digest(chunks[0]["text"].encode())
    manifest["fingerprint"] = digest(b"modified-contract-generation")
    for chunk in chunks:
        chunk["metadata"]["preparation_generation"] = manifest["fingerprint"]
    return embed(chunks, manifest, ContractEncoder())


def test_embedding_preserves_all_sources_and_structured_fields(prepared, artifact):
    _, chunks, _ = prepared
    assert len(artifact["records"]) == 20
    assert len({r["id"] for r in artifact["records"]}) == 20
    products = [r["payload"] for r in artifact["records"] if "product" in r["payload"]]
    assert len(products) == 9
    assert {p["metadata"]["product_id"] for p in products} == {f"KB-{i:03}" for i in range(1, 10)}
    for before, record in zip(chunks, artifact["records"], strict=True):
        after = record["payload"]
        assert before["text"] == after["text"]
        assert before.get("product") == after.get("product")
        assert before.get("price_kopecks") == after.get("price_kopecks")
        assert after["metadata"]["token_count"] > 0
    assert next(p for p in products if p["metadata"]["product_id"] == "KB-004")["price_kopecks"] == 189000


def test_embedding_repeat_is_identical(prepared, artifact, tmp_path):
    assert embed(prepared[1], prepared[2], ContractEncoder()) == artifact
    path = save_artifact(artifact, tmp_path / "vectors")
    before = path.read_bytes()
    assert save_artifact(artifact, path.parent).read_bytes() == before


def test_corrupted_preparation_rejected(prepared):
    output, _, manifest = prepared
    path = output / "generations" / manifest["fingerprint"] / "chunks.jsonl"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(RetrievalError, match="integrity"):
        load_prepared(output)


@pytest.mark.parametrize("bad", [[[]], [[float("nan")]*3]*20, [[0.0]*3]*20, [[1.0, 0.0]]*20])
def test_incomplete_invalid_vectors_fail_before_publication(prepared, bad):
    encoder = ContractEncoder()
    encoder.encode = lambda texts: bad
    with pytest.raises(RetrievalError):
        embed(prepared[1], prepared[2], encoder)


def test_token_overflow_fails_without_encoder_call(prepared):
    encoder = ContractEncoder()
    encoder.token_counts = lambda texts: [8193]*len(texts)
    encoder.encode = lambda texts: pytest.fail("Overflow must be rejected before inference")
    with pytest.raises(RetrievalError, match="Token"):
        embed(prepared[1], prepared[2], encoder)


def test_artifact_tampering_rejected(artifact):
    artifact["records"][0]["vector"][0] += 0.1
    with pytest.raises(RetrievalError, match="integrity"):
        validate_artifact(artifact)


@pytest.fixture
def index():
    client_module = pytest.importorskip("qdrant_client")
    from kbeauty_support.retrieval.index import DenseIndex
    with closing(client_module.QdrantClient(":memory:")) as client:
        yield DenseIndex(client)


def test_publish_noop_and_payload_readback(index, artifact, tmp_path):
    first = index.publish(artifact, tmp_path)
    assert first["status"] == "published"
    assert index.publish(artifact, tmp_path)["status"] == "noop"
    assert index.client.count(index.resolve(), exact=True).count == 20
    hits = index.search("условия доставки", ContractEncoder())
    assert len(hits["hits"]) == 5
    assert all(h["metadata"]["source"].startswith("data/") and h["text"] for h in hits["hits"])


def test_update_changes_text_and_excludes_deleted_records(index, artifact, prepared, tmp_path):
    before = index.publish(artifact, tmp_path)
    updated = changed_artifact(prepared)
    after = index.publish(updated, tmp_path)
    assert before["collection"] != after["collection"]
    points, _ = index.client.scroll(index.resolve(), limit=64)
    assert len(points) == 19
    assert artifact["records"][-1]["id"] not in {str(p.id) for p in points}
    assert any("Изменение для теста" in p.payload["text"] for p in points)
    assert index.client.count(before["collection"], exact=True).count == 20


def test_interrupted_staging_keeps_active_and_resume_succeeds(index, artifact, prepared, tmp_path, monkeypatch):
    before = index.publish(artifact, tmp_path)
    updated = changed_artifact(prepared)
    real_upsert = index.client.upsert
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Injected transport interruption")
        return real_upsert(*args, **kwargs)

    monkeypatch.setattr(index.client, "upsert", fail_second)
    with pytest.raises(RuntimeError, match="interruption"):
        index.publish(updated, tmp_path)
    assert index.resolve() == before["collection"]
    assert index.client.count(index.resolve(), exact=True).count == 20
    assert not (tmp_path / ".publish.lock").exists()
    monkeypatch.setattr(index.client, "upsert", real_upsert)
    assert index.publish(updated, tmp_path)["points"] == 19


def test_failed_alias_switch_keeps_previous(index, artifact, prepared, tmp_path, monkeypatch):
    first = index.publish(artifact, tmp_path)
    monkeypatch.setattr(index.client, "update_collection_aliases", lambda **kw: (_ for _ in ()).throw(RuntimeError("alias failure")))
    with pytest.raises(RuntimeError):
        index.publish(changed_artifact(prepared), tmp_path)
    assert index.resolve() == first["collection"]


def test_query_model_mismatch_fails(index, artifact, tmp_path):
    index.publish(artifact, tmp_path)
    encoder = ContractEncoder()
    encoder.signature = {**encoder.signature, "model_id": "other"}
    with pytest.raises(RetrievalError, match="encoder differs"):
        index.search("крем", encoder)


def test_query_pins_physical_generation_during_alias_change(index, artifact, prepared, tmp_path):
    before = index.publish(artifact, tmp_path)
    encoder = ContractEncoder()
    real_encode = encoder.encode

    def switch_during_encode(texts):
        index.publish(changed_artifact(prepared), tmp_path)
        return real_encode(texts)

    encoder.encode = switch_during_encode
    result = index.search("доставка", encoder)
    assert index.resolve() != before["collection"]
    assert result["collection"] == before["collection"]
    assert result["generation"] == artifact["generation"]


def test_writer_contention_does_not_change_index(index, artifact, tmp_path):
    (tmp_path / ".publish.lock").touch()
    with pytest.raises(RetrievalError, match="writer lock"):
        index.publish(artifact, tmp_path)
    assert index.resolve() is None


def test_corrupt_active_payload_is_detected_on_noop(index, artifact, tmp_path):
    index.publish(artifact, tmp_path)
    index.client.set_payload(index.resolve(), {"text": "corrupted"}, points=[artifact["records"][0]["id"]])
    with pytest.raises(RetrievalError, match="payload integrity"):
        index.publish(artifact, tmp_path)


def test_recall_is_fraction_not_hit_rate():
    assert recall(["a", "b", "x", "c"], ["a", "b", "c", "d"], 3) == 0.5
    assert recall(["a", "a", "b"], ["a", "b"], 3) == 1.0
    with pytest.raises(RetrievalError):
        recall([], [], 3)


def test_frozen_labels_reference_available_sections(prepared):
    sections = {c["metadata"]["section"] for c in prepared[1]}
    labels = json.loads((ROOT / "tests/fixtures/retrieval-qrels-v1.1.json").read_bytes())
    assert len(labels["queries"]) == 13
    for case in labels["queries"]:
        assert set(case["relevant"]) <= sections
