"""Command line source preparation with structured diagnostic events."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from uuid import uuid4

from .audit import SourceValidationError
from .pipeline import ExportError, export, prepare

LOGGER = logging.getLogger("kbeauty.ingestion")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare K-Beauty sources for indexing")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/ingestion"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not LOGGER.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    job_id = uuid4().hex

    def event(name: str, **fields: object) -> None:
        LOGGER.info(json.dumps({"event": name, "job_id": job_id,
                                "timestamp": datetime.now(timezone.utc).isoformat(), **fields}))

    event("started", stage="source_preparation", dry_run=args.dry_run)
    try:
        bundle = prepare(args.data_dir)
        if not args.dry_run:
            export(bundle, args.output_dir, args.data_dir)
        summary = {"status": "validated", "chunks": len(bundle.chunks),
                   "fingerprint": bundle.fingerprint, "dry_run": args.dry_run, "embedding_ready": False}
        print(json.dumps(summary))
        event("completed", **summary)
        return 0
    except SourceValidationError as exc:
        event("failed", error_code="invalid_source_or_config", detail=str(exc))
        return 2
    except (ExportError, OSError):
        event("failed", error_code="export_io_or_lock")
        return 3
    except KeyboardInterrupt:
        event("interrupted", error_code="interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
