"""Real Qdrant/BGE + HTTP API with an explicitly injected non-LLM provider double."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api_helpers import EvidenceSelectorDouble, cases, assert_case, ROOT
from kbeauty_support.api.app import create_app
from kbeauty_support.api.runtime import RuntimeRetriever, Settings
from kbeauty_support.generation.context import Snapshot
from kbeauty_support.generation.service import ChatService


@pytest.fixture(scope="module")
def runtime():
    if os.getenv("KBEAUTY_API_SERVER_TESTS")!="1":
        pytest.skip("Explicit real Server API test opt-in required; LLM remains a double")
    cfg=Settings(api_key="contract-only-access-key",qdrant_url=os.environ["QDRANT_URL"],qdrant_key=os.environ["QDRANT_API_KEY"],
                 data_dir=ROOT/"data",model_dir=Path(os.environ["KBEAUTY_MODEL_DIR"]),rate_limit=100)
    snapshot=Snapshot(cfg.data_dir);retriever=RuntimeRetriever(cfg,snapshot);retriever.warm()
    service=ChatService(snapshot,retriever,EvidenceSelectorDouble())
    with TestClient(create_app(service,cfg)) as client:
        yield client,service


@pytest.mark.parametrize("case",cases(),ids=lambda c:c["id"])
def test_real_qdrant_api_business_contract_provider_double(runtime,case):
    client,service=runtime
    response=client.post("/chat",json=case["request"],headers={"Authorization":"Bearer contract-only-access-key"})
    assert response.status_code==200,response.text
    assert_case(case,response.json())
    if case.get("input") or case["request"].get("catalog_query") or case["id"] in ("T10","T11"):
        assert response.json()["usage"] is None and not response.json()["diagnostics"]["generation_performed"]
    else:
        assert response.json()["usage"]["provider"]=="explicit_test_double"
    assert response.json()["index_generation"].startswith("c21eec8f24a008")


def test_real_server_readiness_and_state_coverage(runtime):
    client,_=runtime
    assert client.get("/health").status_code==200
    r=client.get("/ready")
    assert r.status_code==200 and r.json()["dependencies"]["retrieval"]["points"]==20
    assert r.json()["dependencies"]["llm"]["test_double"] is True
