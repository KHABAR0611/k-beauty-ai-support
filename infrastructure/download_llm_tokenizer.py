"""Download pinned tokenizer JSON files only; never execute remote model code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main() -> int:
    lock_path=ROOT/"src/kbeauty_support/generation/qwen3-tokenizer.lock.json"
    lock=json.loads(lock_path.read_bytes())
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"model-cache/qwen3-tokenizer"/lock["revision"])
    parser.add_argument("--direct",action="store_true")
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.output.is_symlink():raise ValueError("Invalid tokenizer cache")
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({})) if args.direct else urllib.request.build_opener()
    for name,spec in lock["files"].items():
        path=args.output/name;tmp=args.output/(name+".part")
        if path.is_symlink() or tmp.is_symlink():raise ValueError("Invalid tokenizer file")
        if path.exists() and len(path.read_bytes())==spec["size"] and hashlib.sha256(path.read_bytes()).hexdigest()==spec["sha256"]:
            continue
        with opener.open(f"https://huggingface.co/{lock['model_id']}/resolve/{lock['revision']}/{name}",timeout=60) as r:
            raw=r.read(spec["size"]+1)
        if len(raw)!=spec["size"] or hashlib.sha256(raw).hexdigest()!=spec["sha256"]:
            raise ValueError("Tokenizer integrity failure")
        tmp.write_bytes(raw);os.replace(tmp,path)
    (args.output/"download-manifest.json").write_bytes(lock_path.read_bytes())
    print("official tokenizer files verified")
    return 0


if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        print("tokenizer_download_failed category="+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
