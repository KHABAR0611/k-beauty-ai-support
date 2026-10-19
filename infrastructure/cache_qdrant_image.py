"""Bounded Registry download with digest verification; preserves existing Docker data."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

MANIFEST = "sha256:2bd6b052a39abc720f219158ec7b71533fa3204b8aa3c10a2e2f6e0bf80ee6ff"
CONFIG = "sha256:da4c45d5134bc5acad75fb885a46edb432734ed07aae836e4f93d603af28c380"
IMAGE = "qdrant/qdrant:v1.15.1"


def verify_loaded_image(actual: dict, official: dict) -> None:
    # Containerd may synthesize a different image ID during docker-save import.
    if (actual["Os"], actual["Architecture"]) != (official["os"], official["architecture"]):
        raise ValueError("Loaded image platform mismatch")
    if actual["RootFS"]["Layers"] != official["rootfs"]["diff_ids"]:
        raise ValueError("Loaded image RootFS mismatch")
    if any(actual["Config"].get(key) != value for key, value in official["config"].items()):
        raise ValueError("Loaded image runtime config mismatch")


def cache_image(cache: Path, *, direct: bool = False) -> None:
    import requests

    cache.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        session.trust_env = not direct
        response = session.get("https://auth.docker.io/token", params={"service": "registry.docker.io", "scope": "repository:qdrant/qdrant:pull"}, timeout=30)
        response.raise_for_status()
        headers = {"Authorization": "Bearer " + response.json()["token"],
                   "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json"}
        base = "https://registry-1.docker.io/v2/qdrant/qdrant/"
        response = session.get(base + "manifests/" + MANIFEST, headers=headers, timeout=30)
        response.raise_for_status()
        if "sha256:" + hashlib.sha256(response.content).hexdigest() != MANIFEST:
            raise ValueError("Registry manifest digest mismatch")
        manifest = response.json()
        if manifest["config"]["digest"] != CONFIG:
            raise ValueError("Registry config digest mismatch")
        for item in [manifest["config"], *manifest["layers"]]:
            sha = item["digest"].split(":")[1]
            if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("Invalid registry object identity")
            dest = cache / sha
            if dest.is_symlink():
                raise ValueError("Cache symlinks are forbidden")
            if dest.exists():
                with dest.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() == sha:
                        continue
            # Authorization is stripped by requests on redirects to CDN hosts.
            with session.get(base + "blobs/" + item["digest"], headers=headers, stream=True, timeout=(20, 60)) as response:
                response.raise_for_status()
                with dest.open("wb") as stream:
                    for block in response.iter_content(1024*1024):
                        stream.write(block)
                        if stream.tell() > item["size"]:
                            raise ValueError("Registry blob exceeds declared size")
            with dest.open("rb") as stream:
                if dest.stat().st_size != item["size"] or hashlib.file_digest(stream, "sha256").hexdigest() != sha:
                    raise ValueError("Registry blob digest mismatch")
    config = CONFIG.split(":")[1]
    with tarfile.open(cache / "qdrant.tar", "w") as tar:
        def add(name: str, content: bytes) -> None:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        tar.add(cache / config, arcname=config + ".json")
        layers = []
        for item in manifest["layers"]:
            sha = item["digest"].split(":")[1]
            content = (cache / sha).read_bytes()
            if content[:2] == b"\x1f\x8b":
                content = gzip.decompress(content)
            name = sha + "/layer.tar"
            add(name, content)
            layers.append(name)
        add("manifest.json", json.dumps([{"Config": config + ".json", "RepoTags": [IMAGE], "Layers": layers}]).encode())
    result = subprocess.run(["docker", "load", "--input", str(cache / "qdrant.tar")], capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError("Docker image load failed")
    result = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Loaded image identity mismatch")
    actual = json.loads(result.stdout)[0]
    verify_loaded_image(actual, json.loads((cache / config).read_bytes()))
    (cache / "provenance.json").write_text(json.dumps({"image": IMAGE, "manifest_digest": MANIFEST,
        "config_digest": CONFIG, "all_blobs_sha256_verified": True,
        "loaded_image_id": actual["Id"], "rootfs_and_runtime_config_verified": True}, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path("artifacts/docker-image"))
    parser.add_argument("--direct", action="store_true", help="Bypass proxy in this download process only")
    args = parser.parse_args()
    try:
        cache_image(args.cache, direct=args.direct)
        print("official amd64 Qdrant image verified and cached")
        return 0
    except Exception as exc:
        # Avoid disclosing bearer tokens or signed CDN redirects in tracebacks.
        print("image_cache_failed category=" + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
