"""Deterministic source preparation; no model calls or vector-store writes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import os
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from .audit import SourceValidationError
from .sources import ALLOWLIST, canonical, parse_catalog, parse_policy, read_source, reject_links

SCHEMA_VERSION = "1.0"
CHUNKER_VERSION = "structure-v1"
MAX_CHUNK_CHARS = 12000


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: Any) -> bytes:
    return (canonical(value) + "\n").encode("utf-8")


@dataclass(frozen=True)
class PreparedBundle:
    fingerprint: str
    chunks: tuple[dict[str, Any], ...]
    files: dict[str, bytes]


def prepare(data_dir: Path, *, max_chunk_chars: int = MAX_CHUNK_CHARS) -> PreparedBundle:
    if isinstance(max_chunk_chars, bool) or not isinstance(max_chunk_chars, int) or max_chunk_chars < 1:
        raise SourceValidationError("Invalid character safety limit")
    raw = {name: read_source(data_dir, name) for name in ALLOWLIST}
    catalog = parse_catalog(raw["products.json"])
    source_hashes = {name: digest(content) for name, content in raw.items()}
    chunks: list[dict[str, Any]] = []

    def add(name: str, meta: dict[str, Any], section: str, title: str, text: str, kind: str, product: dict | None = None) -> None:
        if len(text) > max_chunk_chars:
            raise SourceValidationError("Semantic unit exceeds the character safety limit; split requires a schema decision")
        identity = meta.get("document_id", meta.get("catalog_id"))
        source = f"data/{name}"
        logical_id = f"{source}|{identity}|{section}|{SCHEMA_VERSION}|{CHUNKER_VERSION}"
        chunk_id = str(uuid5(NAMESPACE_URL, logical_id))
        record: dict[str, Any] = {
            "id": chunk_id, "text": text,
            "metadata": {"source": source, "section": section, "type": kind,
                         "document_id": identity, "document_version": meta["version"],
                         "effective_date": meta["effective_date"], "language": "ru", "data_origin": "fictional",
                         "title": title, "logical_id": logical_id, "parent_id": chunk_id,
                         "source_sha256": source_hashes[name], "chunk_sha256": digest(text.encode("utf-8")),
                         "schema_version": SCHEMA_VERSION, "chunker_version": CHUNKER_VERSION,
                         "token_count": None, "tokenizer_id": None},
        }
        if product is not None:
            record["metadata"]["product_id"] = product["id"]
            record["product"] = product
            record["price_kopecks"] = int(Decimal(product["price"]) * 100)
            record["currency"] = "RUB"
        chunks.append(record)

    versions = {(catalog["version"], catalog["effective_date"], catalog["language"])}
    for name, identity, prefix, count in (
        ("delivery_and_returns.md", "delivery_returns", "DR", 6),
        ("payment_and_loyalty.md", "payment_loyalty", "PL", 5),
    ):
        meta, preamble, sections = parse_policy(raw[name], identity, prefix, count)
        versions.add((meta["version"], meta["effective_date"], meta["language"]))
        for section, title, body in sections:
            add(name, meta, section, title, preamble + "\n\n" + body, "policy")
    if len(versions) != 1:
        raise SourceValidationError("Source bundle versions, effective dates or languages disagree")
    for product in sorted(catalog["products"], key=lambda p: p["id"]):
        text = f"# {product['id']}: {product['name']}\n\n" + canonical({"currency": "RUB", **product})
        add("products.json", catalog, product["id"], product["name"], text, "product", product)
    config = {"schema_version": SCHEMA_VERSION, "chunker_version": CHUNKER_VERSION,
              "max_chunk_chars": max_chunk_chars, "source_sha256": source_hashes,
              "chunk_sha256": {c["id"]: c["metadata"]["chunk_sha256"] for c in chunks},
              "tokenizer_id": None, "dense_model_id": None, "analyzer_fingerprint": None}
    fingerprint = digest(encoded(config))
    for chunk in chunks:
        chunk["metadata"]["preparation_generation"] = fingerprint
    files = {
        "chunks.jsonl": b"".join(encoded(c) for c in chunks),
        "catalog.snapshot.json": encoded(catalog),
        "validation.json": encoded({"status": "validated", "products": len(catalog["products"]),
                                     "policy_sections": 11, "chunks": len(chunks),
                                     "embedding_ready": False, "required_next_gate": "model_tokenizer_limit_check"}),
    }
    files["manifest.json"] = encoded({**config, "fingerprint": fingerprint, "status": "validated",
                                      "stage": "source_preparation", "embedding_ready": False,
                                      "chunk_count": len(chunks), "product_count": len(catalog["products"]),
                                      "files_sha256": {name: digest(content) for name, content in files.items()}})
    return PreparedBundle(fingerprint, tuple(chunks), files)


class ExportError(OSError):
    """Export failed without replacing the previous CURRENT pointer."""


def write_file(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def export(bundle: PreparedBundle, output_dir: Path, data_dir: Path) -> Path:
    """Publish an immutable generation and atomically update its CURRENT pointer."""
    reject_links(output_dir)
    output = output_dir.resolve()
    source = data_dir.resolve()
    if output == source or source in output.parents or output in source.parents:
        raise SourceValidationError("Output and input directories must not overlap")
    lock_fd: int | None = None
    lock = output / ".ingest.lock"
    try:
        output.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        generations = output / "generations"
        reject_links(generations)
        generations.mkdir(exist_ok=True)
        target = generations / bundle.fingerprint
        reject_links(target)
        if target.exists():
            if {p.name for p in target.iterdir()} != set(bundle.files):
                raise ExportError("Existing generation is incomplete or has unexpected files")
            for name, expected in bundle.files.items():
                reject_links(target / name)
                if (target / name).read_bytes() != expected:
                    raise ExportError("Existing generation failed integrity verification")
        else:
            staging = generations / (".tmp-" + uuid4().hex)
            staging.mkdir()
            for name, content in bundle.files.items():
                write_file(staging / name, content)
            os.replace(staging, target)
        pointer = output / (".current-" + uuid4().hex)
        write_file(pointer, (bundle.fingerprint + "\n").encode("ascii"))
        os.replace(pointer, output / "CURRENT")
        return target
    except OSError as exc:
        raise ExportError("Cannot publish prepared generation (I/O or writer lock)") from exc
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
            lock.unlink(missing_ok=True)
