"""Real loopback HTTP smoke with generation disabled; never a live-LLM e2e claim."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

import httpx

ROOT=Path(__file__).resolve().parents[1]


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("artifacts/api-smoke/report.json"))
    args=parser.parse_args()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    token=secrets.token_urlsafe(32)
    env=dict(os.environ,PYTHONPATH="src",API_ACCESS_KEY=token,LLM_PROVIDER="disabled",RERANK_ENABLED="false",PYTHONIOENCODING="utf8")
    logs=ROOT/"artifacts/api-smoke";logs.mkdir(parents=True,exist_ok=True)
    with (logs/"server.log").open("wb") as log:
        process=subprocess.Popen([sys.executable,"-m","uvicorn","kbeauty_support.api.app:app","--host","127.0.0.1",
                                  "--port",str(port),"--workers","1","--no-access-log"],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}",trust_env=False,timeout=10) as client:
                deadline=time.monotonic()+30
                while True:
                    try:
                        if client.get("/health").status_code==200:
                            probe=client.get("/ready")
                            if "dependencies" in probe.json():
                                break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic()>deadline or process.poll() is not None:
                        raise RuntimeError("API startup failed")
                    time.sleep(.1)
                records=[]
                for method,path,payload,code,auth in [
                    ("GET","/health",None,200,False),("GET","/ready",None,503,False),
                    ("POST","/chat",{"question":"Сколько стоит доставка в Москве?"},503,True),
                    ("POST","/chat",{"question":"Где заказ 12345?"},200,True),
                    ("POST","/chat",{"question":"Хочу оператора"},200,True),
                    ("POST","/chat",{"question":"Какой итог?"},200,True),
                    ("POST","/chat",{"question":"Доставка"},401,False),
                    ("GET","/metrics",None,200,True)]:
                    start=time.perf_counter()
                    r=client.request(method,path,json=payload,headers={"Authorization":"Bearer "+token} if auth else {})
                    assert r.status_code==code
                    records.append({"method":method,"path":path,"request":payload,"http_status":r.status_code,
                                    "latency_ms":(time.perf_counter()-start)*1000,"response":r.json()})
                assert records[2]["response"]["status"]=="system_error"
                assert records[3]["response"]["status"]=="requires_external_data"
                assert records[4]["response"]["handoff"]["created"] is False
                assert records[5]["response"]["status"]=="clarification_needed"
            result={"transport":"real loopback TCP, Uvicorn process","provider":"disabled","live_llm_verified":False,
                    "generation_success_claimed":False,"paid_calls":0,"records":records}
            raw=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
            assert token not in raw
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(raw,encoding="utf8")
            print("8 real HTTP checks passed; live generation not tested")
            return 0
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        print("api_smoke_failed category="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
