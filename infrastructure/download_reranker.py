"""Fetch the pinned official ONNX cross-encoder without executing remote code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1427fd652930e4ba29e8149678df786c240d8825"


def download(output: Path, *, direct: bool = False) -> None:
    lock_path = ROOT / "src/kbeauty_support/retrieval/reranker.lock.json"
    lock = json.loads(lock_path.read_bytes())
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError("Model cache must not be a symlink")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct else urllib.request.build_opener()
    for name, spec in lock["files"].items():
        dest = output / name
        tmp = output / (name + ".part")
        if dest.is_symlink() or tmp.is_symlink():
            raise ValueError("Model file must not be a symlink")
        if dest.exists():
            with dest.open("rb") as stream:
                if dest.stat().st_size == spec["size"] and hashlib.file_digest(stream, "sha256").hexdigest() == spec["sha256"]:
                    continue
        print("downloading " + name, file=sys.stderr)
        started = time.monotonic()
        url = f"https://huggingface.co/{lock['model_id']}/resolve/{lock['revision']}/{spec['remote_path']}"
        with opener.open(url, timeout=60) as response, tmp.open("wb") as stream:
            checksum = hashlib.sha256()
            size = 0
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > spec["size"] or time.monotonic() - started > 1800:
                    raise ValueError("Model download size or time limit exceeded")
                stream.write(block)
                checksum.update(block)
            if size != spec["size"] or checksum.hexdigest() != spec["sha256"]:
                raise ValueError("Model integrity failure")
        os.replace(tmp, dest)
    (output / "download-manifest.json").write_bytes(lock_path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "model-cache/mmarco-minilm" / REVISION)
    parser.add_argument("--direct", action="store_true", help="Bypass proxy for this process only")
    args = parser.parse_args()
    try:
        download(args.output, direct=args.direct)
        print("reranker files verified")
        return 0
    except Exception as exc:
        print("download_failed category=" + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
