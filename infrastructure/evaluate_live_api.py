"""Twelve fixed real-HTTP checks. Requires a ready local Ollama-backed API, never a mock."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT/"tests"))


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",default="http://127.0.0.1:8090")
    parser.add_argument("--allow-local-inference",action="store_true",required=True)
    parser.add_argument("--output",type=Path,default=Path("artifacts/live-api-evaluation.json"))
    args=parser.parse_args()
    parsed=urlsplit(args.url)
    if (parsed.scheme!="http" or parsed.hostname not in ("127.0.0.1","localhost","::1") or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("","/")):
        raise ValueError("Evaluation requires a local API")
    token=os.environ["API_ACCESS_KEY"]
    from api_helpers import cases,assert_case
    from kbeauty_support.retrieval.evaluation import percentile
    records=[]
    with httpx.Client(base_url=args.url,trust_env=False,timeout=100,follow_redirects=False) as client:
        ready=client.get("/ready")
        if ready.status_code!=200 or ready.json()["dependencies"]["llm"].get("provider")!="ollama":
            raise ValueError("A real ready Ollama provider is required")
        for case in cases():
            started=time.perf_counter()
            r=client.post("/chat",json=case["request"],headers={"Authorization":"Bearer "+token})
            response=r.json();passed=False
            try:
                assert r.status_code==200
                assert_case(case,response)
                if response.get("diagnostics",{}).get("generation_performed"):
                    assert response["usage"]["provider"]=="ollama"
                passed=True
            except (AssertionError,KeyError,TypeError):
                pass
            records.append({"id":case["id"],"request":case["request"],"response":response,"http_status":r.status_code,
                            "http_latency_ms":(time.perf_counter()-started)*1000,"business_contract_passed":passed})
    result={"scope":"real HTTP with real ready Ollama; tools/control branches explicitly disclosed", "cases":records,
            "pass_count":sum(r["business_contract_passed"] for r in records),"case_count":12,
            "http_latency":{f"p{p}_ms":percentile([r["http_latency_ms"] for r in records],p) for p in (50,95)},
            "not_customer_resolution_rate":True}
    raw=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if token in raw:raise ValueError("Credential leak detected; report not saved")
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(raw,encoding="utf8")
    print(json.dumps({"pass_count":result["pass_count"],"case_count":12,"scope":result["scope"]}))
    return 0 if result["pass_count"]==12 else 1


if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        print("live_evaluation_failed category="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
