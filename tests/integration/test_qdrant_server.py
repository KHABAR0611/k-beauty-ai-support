"""Explicit real-server suite; requires a verified embedding artifact and isolated server."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from uuid import uuid4

import pytest

from kbeauty_support.retrieval.dense import digest, encoded, validate_artifact
from kbeauty_support.retrieval.index import DenseIndex

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def server():
    if not os.environ.get("KBEAUTY_SERVER_TESTS"):
        pytest.skip("Explicit Qdrant Server integration opt-in required")
    from qdrant_client import QdrantClient
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"], timeout=30, trust_env=False)
    artifact = json.loads(Path(os.environ["KBEAUTY_EMBEDDING_ARTIFACT"]).read_bytes())
    validate_artifact(artifact)
    assert len(artifact["records"]) == 20
    assert artifact["descriptor"]["model"]["model_id"] == "BAAI/bge-m3"
    index = DenseIndex(client, alias="kbeauty_it_" + uuid4().hex)
    try:
        yield client, index, artifact
    finally:
        client.close()


def health(path):
    request = urllib.request.Request(os.environ["QDRANT_URL"] + path, headers={"api-key": os.environ["QDRANT_API_KEY"]})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        return response.status


def modified(artifact):
    # A separate test generation, never the product alias or source files.
    changed = copy.deepcopy(artifact)
    changed["descriptor"]["preparation_generation"] = digest(uuid4().bytes)
    changed["generation"] = digest(encoded(changed["descriptor"]))
    changed["records"] = changed["records"][:-1]
    for record in changed["records"]:
        record["payload"]["index"] = {**changed["descriptor"], "generation": changed["generation"]}
        record["payload"]["metadata"]["preparation_generation"] = changed["descriptor"]["preparation_generation"]
    changed["records"][0]["payload"]["text"] += "\nIndex contract test revision."
    payload = changed["records"][0]["payload"]
    payload["metadata"]["chunk_sha256"] = digest(payload["text"].encode())
    changed["content_sha256"] = digest(encoded({k:v for k,v in changed.items() if k != "content_sha256"}))
    return changed


def test_health_and_readiness(server):
    assert health("/healthz") == health("/readyz") == 200


def test_real_vectors_full_payload_and_idempotency(server, tmp_path):
    client, index, artifact = server
    first = index.publish(artifact, tmp_path)
    assert first["points"] == 20
    assert index.publish(artifact, tmp_path)["status"] == "noop"
    points, _ = client.scroll(index.resolve(), limit=64, with_payload=True, with_vectors=True)
    assert len(points) == 20
    assert len([p for p in points if p.payload.get("product")]) == 9
    assert all(len(p.vector["dense"]) == 1024 for p in points)


def test_partial_upsert_never_publishes_and_can_resume(server, tmp_path, monkeypatch):
    client, index, artifact = server
    index.publish(artifact, tmp_path)
    previous = index.resolve()
    changed = modified(artifact)
    real_upsert = client.upsert
    calls = 0

    def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ConnectionError("Injected interrupted update")
        return real_upsert(*args, **kwargs)

    monkeypatch.setattr(client, "upsert", fail)
    with pytest.raises(ConnectionError):
        index.publish(changed, tmp_path)
    assert index.resolve() == previous
    assert client.count(previous, exact=True).count == 20
    assert client.count("kbeauty_dense_" + changed["generation"], exact=True).count == 4
    monkeypatch.setattr(client, "upsert", real_upsert)
    assert index.publish(changed, tmp_path)["points"] == 19
    points, _ = client.scroll(index.resolve(), limit=64)
    assert artifact["records"][-1]["id"] not in {str(p.id) for p in points}
    assert any("Index contract test revision" in p.payload["text"] for p in points)
    index.publish(artifact, tmp_path)


def test_verification_failure_leaves_alias_unchanged(server, tmp_path, monkeypatch):
    client, index, artifact = server
    index.publish(artifact, tmp_path)
    before = index.resolve()
    monkeypatch.setattr(index, "_verify", lambda *args: (_ for _ in ()).throw(RuntimeError("Injected readback failure")))
    with pytest.raises(RuntimeError):
        index.publish(modified(artifact), tmp_path)
    assert index.resolve() == before


def test_restart_preserves_real_vectors_payload_and_alias(server, tmp_path):
    if os.environ.get("KBEAUTY_ALLOW_SMOKE_RESTART") != "1":
        pytest.skip("Restart requires explicit isolated Compose opt-in")
    assert os.environ["QDRANT_URL"] == "http://127.0.0.1:6394"
    client, index, artifact = server
    index.publish(artifact, tmp_path)
    before = index.resolve()
    env = dict(os.environ, QDRANT_HTTP_PORT="6394")
    subprocess.run(["docker", "compose", "-p", "kbeauty-review-check", "restart", "qdrant"], cwd=ROOT, env=env, check=True, capture_output=True, timeout=60)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            if health("/readyz") == 200:
                break
        except OSError:
            pass
        time.sleep(1)
    assert health("/readyz") == 200
    assert index.resolve() == before
    assert index.publish(artifact, tmp_path)["status"] == "noop"
