"""Pinned official Qwen tokenizer; counts are estimates until verified by Ollama usage."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from kbeauty_support.ingestion.sources import reject_links
from .errors import ServiceError

REVISION="c1899de289a04d12100db370d81485cdf75e47ca"


class QwenTokenCounter:
    def __init__(self, directory: Path):
        from tokenizers import Tokenizer
        lock=json.loads(Path(__file__).with_name("qwen3-tokenizer.lock.json").read_bytes())
        reject_links(directory)
        reject_links(directory/"download-manifest.json")
        if json.loads((directory/"download-manifest.json").read_bytes())!=lock:
            raise ServiceError("unapproved_llm_tokenizer")
        for name,spec in lock["files"].items():
            path=directory/name;reject_links(path)
            with path.open("rb") as stream:
                if path.stat().st_size!=spec["size"] or hashlib.file_digest(stream,"sha256").hexdigest()!=spec["sha256"]:
                    raise ServiceError("llm_tokenizer_integrity_failure")
        self.tokenizer=Tokenizer.from_file(str(directory/"tokenizer.json"))
        self.tokenizer.no_truncation();self.tokenizer.no_padding()

    def __call__(self,text: str) -> int:
        return len(self.tokenizer.encode(text).ids)
