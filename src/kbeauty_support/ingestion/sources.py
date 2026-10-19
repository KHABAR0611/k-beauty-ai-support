"""Strict, bounded readers for the versioned source bundle."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re
from typing import Any

import yaml

from .audit import SourceValidationError

ALLOWLIST = ("delivery_and_returns.md", "payment_and_loyalty.md", "products.json")
MAX_SOURCE_BYTES = 5 * 1024 * 1024


def reject_links(path: Path) -> None:
    for part in (path.absolute(), *path.absolute().parents):
        if part.is_symlink() or part.is_junction():
            raise SourceValidationError("Symlinks and junctions are not accepted")


def read_source(root: Path, name: str) -> bytes:
    if name not in ALLOWLIST:
        raise SourceValidationError("Source is outside the allowlist")
    path = root / name
    reject_links(path)
    try:
        if path.resolve(strict=True).parent != root.resolve(strict=True):
            raise SourceValidationError("Source escapes the bundle directory")
        if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
            raise SourceValidationError("Source is not a file or exceeds the size limit")
        with path.open("rb") as stream:
            raw = stream.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise SourceValidationError("Source exceeds the size limit")
        raw.decode("utf-8")
        return raw
    except (OSError, UnicodeError) as exc:
        raise SourceValidationError("Source cannot be read as UTF-8") from exc


def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SourceValidationError("Duplicate mapping key")
        result[key] = value
    return result


class UniqueLoader(yaml.SafeLoader):
    pass


def yaml_mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict[str, Any]:
    return unique_pairs([(loader.construct_object(k), loader.construct_object(v)) for k, v in node.value])


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, yaml_mapping)


def metadata(meta: dict[str, Any]) -> None:
    if not isinstance(meta.get("version"), str) or not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", meta["version"]):
        raise SourceValidationError("A string document version is required")
    if meta.get("language") != "ru":
        raise SourceValidationError("The bundle language must be ru")
    try:
        if not isinstance(meta.get("effective_date"), str):
            raise ValueError
        date.fromisoformat(meta["effective_date"])
    except ValueError as exc:
        raise SourceValidationError("Invalid ISO effective_date") from exc


def parse_policy(raw: bytes, document_id: str, prefix: str, count: int) -> tuple[dict[str, Any], str, list[tuple[str, str, str]]]:
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise SourceValidationError("Policy requires YAML front matter")
    try:
        meta = yaml.load(match[1], Loader=UniqueLoader)
    except (yaml.YAMLError, TypeError, RecursionError) as exc:
        raise SourceValidationError("Invalid policy front matter") from exc
    if not isinstance(meta, dict):
        raise SourceValidationError("Policy metadata must be a mapping")
    metadata(meta)
    if meta.get("document_id") != document_id or meta.get("status") != "fictional_reference":
        raise SourceValidationError("Unexpected policy identity or provenance")
    body = text[match.end():].strip()
    headings = list(re.finditer(r"^## (.+)$", body, re.MULTILINE))
    sections = []
    for index, heading in enumerate(headings):
        label = re.fullmatch(r"((?:DR|PL)-\d{2})\. (\S.*)", heading[1])
        if not label:
            raise SourceValidationError("Unsupported policy section heading")
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        section_body = body[heading.end():end].strip()
        if not section_body:
            raise SourceValidationError("Empty policy section")
        sections.append((label[1], label[2], body[heading.start():end].strip()))
    if [s[0] for s in sections] != [f"{prefix}-{n:02d}" for n in range(1, count + 1)]:
        raise SourceValidationError("Missing, duplicate or unexpected policy sections")
    preamble = body[:headings[0].start()].strip()
    if not preamble.startswith("# "):
        raise SourceValidationError("Policy requires a document title")
    return meta, preamble, sections


def no_constant(value: str) -> None:
    raise SourceValidationError("Non-finite JSON numbers are invalid")


def parse_catalog(raw: bytes) -> dict[str, Any]:
    try:
        catalog = json.loads(raw, parse_float=Decimal, parse_constant=no_constant, object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SourceValidationError("Invalid catalog JSON") from exc
    if not isinstance(catalog, dict):
        raise SourceValidationError("Catalog must be an object")
    metadata(catalog)
    if not isinstance(catalog.get("catalog_id"), str) or not catalog["catalog_id"].strip():
        raise SourceValidationError("Catalog identity is required")
    if catalog.get("currency") != "RUB" or catalog.get("fictional") is not True:
        raise SourceValidationError("Expected fictional RUB catalog")
    products = catalog.get("products")
    if not isinstance(products, list) or not products:
        raise SourceValidationError("Products must be a nonempty list")
    ids: set[str] = set()
    for product in products:
        if not isinstance(product, dict):
            raise SourceValidationError("Product must be an object")
        product_id = product.get("id")
        if not isinstance(product_id, str) or not re.fullmatch(r"KB-\d{3}", product_id) or product_id in ids:
            raise SourceValidationError("Invalid or duplicate product id")
        ids.add(product_id)
        price = product.get("price")
        try:
            if isinstance(price, bool) or not isinstance(price, (int, Decimal)):
                raise InvalidOperation
            amount = Decimal(price)
            if not amount.is_finite() or not 0 < amount <= Decimal("1000000000") or amount != amount.quantize(Decimal("0.01")):
                raise InvalidOperation
        except InvalidOperation as exc:
            raise SourceValidationError("Invalid product price") from exc
        for field in ("name", "description"):
            if not isinstance(product.get(field), str) or not product[field].strip():
                raise SourceValidationError("Product name and description are required")
        attrs = product.get("characteristics")
        if not isinstance(attrs, dict) or not isinstance(attrs.get("fragrance_free"), bool):
            raise SourceValidationError("Invalid product characteristics")
        if not isinstance(attrs.get("category"), str) or not attrs["category"].strip():
            raise SourceValidationError("Product category is required")
        for key in ("skin_types", "key_ingredients"):
            values = attrs.get(key)
            if not isinstance(values, list) or not values or not all(isinstance(v, str) and v.strip() for v in values):
                raise SourceValidationError("Product characteristics require nonempty string lists")
    return catalog


def canonical(value: Any) -> str:
    """Canonical JSON retaining exact Decimal numbers, without binary floats."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        if abs(value) > 10**24:
            raise SourceValidationError("Numeric value exceeds supported bounds")
        return str(value)
    if isinstance(value, Decimal):
        if not value.is_finite() or abs(value.adjusted()) > 24 or len(value.as_tuple().digits) > 24:
            raise SourceValidationError("Numeric value exceeds supported bounds")
        return format(value, "f")
    if isinstance(value, list):
        return "[" + ",".join(canonical(v) for v in value) + "]"
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return "{" + ",".join(canonical(k) + ":" + canonical(value[k]) for k in sorted(value)) + "}"
    raise SourceValidationError("Unsupported JSON value")
