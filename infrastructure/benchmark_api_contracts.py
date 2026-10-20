"""Explicit contract benchmark: real Qdrant/BGE, provider double, NOT live LLM e2e."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-provider-double",action="store_true",required=True)
    parser.add_argument("--output",type=Path,default=Path("artifacts/block5-contract-benchmark.json"))
    args=parser.parse_args()
    from fastapi.testclient import TestClient
    from kbeauty_support.api.app import create_app
    from kbeauty_support.api.runtime import Settings,RuntimeRetriever
    from kbeauty_support.generation.context import Snapshot
    from kbeauty_support.generation.service import ChatService
    from kbeauty_support.retrieval.dense import digest
    from kbeauty_support.retrieval.evaluation import recall,reciprocal_rank,percentile
    from kbeauty_support.retrieval.rerank_evaluation import process_memory
    sys.path.insert(0,str(ROOT/"tests"))
    from api_helpers import EvidenceSelectorDouble,cases,assert_case

    cfg=replace(Settings.environment(),api_key="explicit-benchmark-only-key",rate_limit=1000,rerank_enabled=False)
    snapshot=Snapshot(cfg.data_dir);retriever=RuntimeRetriever(cfg,snapshot)
    milestones={"before_warmup":process_memory()}
    started=time.perf_counter();retriever.warm();warm=time.perf_counter()-started
    milestones["after_warmup"]=process_memory()
    raw=(ROOT/"tests/fixtures/retrieval-qrels-v1.1.json").read_bytes()
    assert digest(raw)=="d7b1bbd56f943e1f9e56255b6a7fa822965ec8b480a38c6ec7a4660f848573cd"
    retrieval=[]
    for case in json.loads(raw)["queries"]:
        samples=[]
        for _ in range(3):
            t=time.perf_counter();value=retriever.retrieve(case["query"])
            samples.append({"latency_ms":(time.perf_counter()-t)*1000,"top5":[h["metadata"]["section"] for h in value["hits"][:5]]})
        rankings=[s["top5"] for s in samples]
        retrieval.append({**case,"samples":samples,"recall_at_3":statistics.mean(recall(r,case["relevant"],3) for r in rankings),
                          "recall_at_5":statistics.mean(recall(r,case["relevant"],5) for r in rankings),
                          "mrr_at_5":statistics.mean(reciprocal_rank(r,case["relevant"]) for r in rankings)})
    service=ChatService(snapshot,retriever,EvidenceSelectorDouble())
    responses=[];cpu_start=time.process_time();wall_start=time.perf_counter()
    with TestClient(create_app(service,cfg)) as client:
        for case in cases():
            samples=[]
            for _ in range(3):
                t=time.perf_counter();r=client.post("/chat",json=case["request"],headers={"Authorization":"Bearer "+cfg.api_key})
                http_ms=(time.perf_counter()-t)*1000
                assert r.status_code==200
                response=r.json();assert_case(case,response)
                samples.append({"http_latency_ms":http_ms,"stages_ms":response["latency_ms"],"status":response["status"]})
            responses.append({"id":case["id"],"request":case["request"],"response":response,"samples":samples,
                              "business_contract_passed":True,"live_answer_quality":None})
        ready=client.get("/ready").json()
        metrics=service.metrics()
    cpu=time.process_time()-cpu_start;wall=time.perf_counter()-wall_start
    milestones["after_requests"]=process_memory()
    samples=[s for r in responses for s in r["samples"]]
    result={"scope":"real Qdrant Server/BGE + ASGI HTTP contracts, explicit provider double; NOT live LLM e2e",
        "live_llm_verified":False,"live_final_answer_quality":None,"paid_requests":0,"actual_llm_token_usage":None,
        "repetitions":3,"warmup_seconds":warm,"generation":value["generation"],"model":retriever.encoder.signature,
        "retrieval":{"labels_sha256":digest(raw),"query_count":13,"pool":20,"evaluated_cutoff":5,
            **{k:statistics.mean(r[k] for r in retrieval) for k in ("recall_at_3","recall_at_5","mrr_at_5")},"results":retrieval},
        "api_contracts":{"cases":responses,"pass_count":len(responses),"response_categories":metrics,
            "latency":{k:{f"p{p}_ms":percentile([s["stages_ms"][k] for s in samples],p) for p in (50,95)}
                       for k in ("retrieval","context","llm","answer_control","total")},
            "http_latency":{f"p{p}_ms":percentile([s["http_latency_ms"] for s in samples],p) for p in (50,95)}},
        "resources":{"memory":milestones,"process_cpu_seconds":cpu,"wall_seconds":wall,
            "process_cpu_percent_single_core_basis":100*cpu/wall,"host_total_cpu_measured":False},
        "readiness":ready,"limitations":["Provider-double latency is not LLM latency.","No live answer correctness or prompt-injection resistance measurement.",
            "Domain coverage expansion is not an improvement of top5 retrieval metrics.","Outcome shares describe this synthetic run, not resolved customer problems."]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"scope":result["scope"],"contracts_passed":12,"live_llm_verified":False,
                      "retrieval":{k:result["retrieval"][k] for k in ("recall_at_3","recall_at_5","mrr_at_5")}}))
    return 0


if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("benchmark_failed category="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
