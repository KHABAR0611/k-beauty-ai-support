"""Isolated infrastructure smoke test; never reads the business source bundle."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "kbeauty-review-check"
PORT = 6394
OUTPUT = ROOT / "artifacts/docker-review"


def safe_diagnostic(text: str, api_key: str) -> str:
    def redact_url(match: re.Match) -> str:
        value = urlsplit(match[0])
        host = value.hostname or "redacted"
        if value.port:
            host += ":" + str(value.port)
        return urlunsplit((value.scheme, host, value.path, "[redacted]" if value.query else "", ""))
    return re.sub(r'https?://[^\s"<>]+', redact_url, text.replace(api_key, "[redacted]"))


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    key_path = OUTPUT / "connection.env"
    if key_path.exists():
        key = key_path.read_text(encoding="utf-8").strip().removeprefix("QDRANT_API_KEY=")
    else:
        key = secrets.token_urlsafe(32)
        fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("QDRANT_API_KEY=" + key + "\n")
    env = dict(os.environ, QDRANT_API_KEY=key, QDRANT_HTTP_PORT=str(PORT))
    result: dict = {"project": PROJECT, "port": PORT, "business_data_loaded": False,
                    "model_embeddings_created": False, "health_checks_performed": False,
                    "persistence_check_performed": False}

    def run(args: list[str], timeout: int = 120) -> str:
        p = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=timeout)
        if p.returncode:
            result["failed_command"] = args
            result["diagnostic"] = safe_diagnostic(p.stderr.decode("utf-8", errors="replace")[-1800:], key)
            raise RuntimeError("Docker command failed: " + args[1])
        return p.stdout.decode("utf-8", errors="replace").strip()

    def request(method: str, path: str, body: dict | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}" + path, data=data, method=method,
                                     headers={"api-key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw.startswith(b"{") else raw.decode()

    def ready() -> int:
        for _ in range(45):
            try:
                if request("GET", "/readyz")[0] == 200:
                    return 200
            except (OSError, ValueError):
                pass
            time.sleep(1)
        raise RuntimeError("Qdrant readiness deadline exceeded")

    try:
        result["engine_version"] = run(["docker", "version", "--format", "{{.Server.Version}}"])
        result["compose_version"] = run(["docker", "compose", "version"])
        compose = ["docker", "compose", "-p", PROJECT]
        run(compose + ["config", "--quiet"])
        result["compose_config_valid"] = True
        run(compose + ["up", "-d", "qdrant"])
        result["readiness_before_restart"] = ready()
        result["health_before_restart"] = request("GET", "/healthz")[0]
        result["health_checks_performed"] = True
        result["qdrant_version"] = request("GET", "/")[1]["version"]
        collection = "infra_smoke_" + uuid4().hex
        result["collection"] = collection
        # Unique collection, explicit refusal to touch an existing collection.
        try:
            request("GET", "/collections/" + collection)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        else:
            raise RuntimeError("Synthetic collection collision")
        request("PUT", "/collections/" + collection, {"vectors": {"size": 1, "distance": "Cosine"}})
        marker = uuid4().hex
        payload = {"purpose": "infrastructure-persistence-smoke", "marker": marker}
        # A literal sentinel vector is test data, not a model embedding.
        request("PUT", "/collections/" + collection + "/points?wait=true",
                {"points": [{"id": 1, "vector": [1.0], "payload": payload}]})
        retrieve = {"ids": [1], "with_payload": True, "with_vector": True}
        before = request("POST", "/collections/" + collection + "/points", retrieve)[1]["result"][0]
        if before["payload"] != payload or before["vector"] != [1.0]:
            raise RuntimeError("Synthetic point write verification failed")
        container = run(compose + ["ps", "-q", "qdrant"])
        mounts = json.loads(run(["docker", "inspect", "--format", "{{json .Mounts}}", container]))
        volume = next(m for m in mounts if m["Destination"] == "/qdrant/storage")
        if volume["Type"] != "volume" or not volume["Name"].startswith(PROJECT + "_"):
            raise RuntimeError("Unexpected persistence volume")
        result["volume"] = volume["Name"]
        run(compose + ["restart", "qdrant"])
        result["readiness_after_restart"] = ready()
        result["health_after_restart"] = request("GET", "/healthz")[0]
        after = request("POST", "/collections/" + collection + "/points", retrieve)[1]["result"][0]
        if after["payload"] != payload or after["vector"] != [1.0]:
            raise RuntimeError("Synthetic data failed persistence check")
        result["synthetic_point_preserved"] = True
        result["persistence_check_performed"] = True
        result["point_id"] = 1
        result["status"] = "passed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyError, StopIteration) as exc:
        result["status"] = "failed"
        result["error_type"] = type(exc).__name__
        # Avoid dumping command environments, API keys or provider output.
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
