"""Download only the approved official model files; never execute remote Python."""
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


def download(output: Path, *, direct: bool = False) -> None:
    lock_path = ROOT / "src/kbeauty_support/retrieval/bge-m3.lock.json"
    lock = json.loads(lock_path.read_bytes())
    output.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if direct else urllib.request.build_opener()
    for name, spec in lock["files"].items():
        dest = output / name
        if dest.is_symlink():
            raise ValueError("Model cache must not contain symlinks")
        if dest.exists():
            with dest.open("rb") as stream:
                if dest.stat().st_size == spec["size"] and hashlib.file_digest(stream, "sha256").hexdigest() == spec["sha256"]:
                    continue
        print("downloading " + name, file=sys.stderr)
        url = f"https://huggingface.co/{lock['model_id']}/resolve/{lock['revision']}/onnx/{name}"
        tmp = dest.with_suffix(dest.suffix + ".part")
        started = time.monotonic()
        with opener.open(url, timeout=60) as response, tmp.open("wb") as stream:
            size = 0
            checksum = hashlib.sha256()
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
    parser.add_argument("--output", type=Path, default=ROOT / "model-cache/bge-m3/5617a9f61b028005a4858fdac845db406aefb181")
    parser.add_argument("--direct", action="store_true", help="Bypass environment proxy for this download only")
    args = parser.parse_args()
    try:
        download(args.output, direct=args.direct)
        print("model files verified")
        return 0
    except Exception as exc:
        print("download_failed category=" + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
