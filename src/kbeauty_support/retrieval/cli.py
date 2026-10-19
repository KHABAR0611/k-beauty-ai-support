"""Explicit CLI boundaries for offline embedding and Qdrant Server operations."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import logging
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from .dense import BgeM3Encoder, REVISION, RetrievalError, digest, encoded, embed, load_prepared, save_artifact
from .evaluation import evaluate
from .index import DenseIndex


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"level": record.levelname, "event": record.getMessage()}, ensure_ascii=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dense embedding, generation publishing and source search")
    parser.add_argument("command", choices=("tokens", "embed", "index", "search", "evaluate"))
    parser.add_argument("--prepared", type=Path, default=Path("artifacts/ingestion"))
    parser.add_argument("--model-dir", type=Path, default=Path("model-cache/bge-m3") / REVISION)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/dense"))
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--labels", type=Path, default=Path("tests/fixtures/retrieval-qrels-v1.1.json"))
    args = parser.parse_args(argv)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    try:
        if args.command == "index":
            if args.artifact is None:
                raise RetrievalError("--artifact is required")
            encoder = None
        else:
            encoder = BgeM3Encoder(args.model_dir)
        if args.command in ("tokens", "embed"):
            chunks, manifest = load_prepared(args.prepared)
            if args.command == "tokens":
                counts = encoder.token_counts([c["text"] for c in chunks])
                result = {"model": encoder.signature, "preparation_generation": manifest["fingerprint"],
                          "token_limit": encoder.signature["max_tokens"],
                          "chunks": [{"id": c["id"], "section": c["metadata"]["section"], "tokens": n} for c, n in zip(chunks, counts, strict=True)],
                          "all_fit": all(n <= encoder.signature["max_tokens"] for n in counts)}
                if not result["all_fit"]:
                    raise RetrievalError("Chunk exceeds model token limit")
            else:
                artifact = embed(chunks, manifest, encoder)
                save_artifact(artifact, args.output_dir)
                result = {"generation": artifact["generation"], "points": len(artifact["records"]),
                          "artifact": artifact["generation"] + ".json"}
        else:
            from qdrant_client import QdrantClient

            url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise RetrievalError("Invalid QDRANT_URL")
            if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
                raise RetrievalError("Remote Qdrant requires HTTPS")
            with closing(QdrantClient(url=url, api_key=os.environ.get("QDRANT_API_KEY"), timeout=30, trust_env=False)) as client:
                index = DenseIndex(client, alias=os.environ.get("QDRANT_COLLECTION_ALIAS", "kbeauty_active"))
                if args.command == "index":
                    artifact = json.loads(args.artifact.read_bytes())
                    result = index.publish(artifact, args.output_dir)
                elif args.command == "search":
                    if not args.query:
                        raise RetrievalError("--query is required")
                    result = index.search(args.query, encoder, limit=args.limit)
                else:
                    raw_labels = args.labels.read_bytes()
                    result = evaluate(index, encoder, json.loads(raw_labels))
                    result["labels_sha256"] = digest(raw_labels)
        sys.stdout.buffer.write(encoded(result))
        return 0
    except KeyboardInterrupt:
        logging.error("operation_interrupted")
        return 130
    except Exception as exc:
        # SDK errors may contain credentials, URLs or document content: log only the category.
        logging.error("operation_failed category=%s", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
