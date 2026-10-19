"""Validate the source bundle without indexing or external services."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


class SourceValidationError(ValueError):
    """A source bundle violates the ingestion input contract."""


def load_catalog(path: Path) -> dict:
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except (OSError, ValueError) as exc:
        raise SourceValidationError("Catalog cannot be read as UTF-8 JSON") from exc
    if not isinstance(catalog, dict):
        raise SourceValidationError("Catalog must be an object")
    if catalog.get("currency") != "RUB" or catalog.get("fictional") is not True:
        raise SourceValidationError("Expected a fictional RUB source bundle")
    products = catalog.get("products")
    if not isinstance(products, list) or not products:
        raise SourceValidationError("Catalog products must be a nonempty list")
    ids = set()
    for product in products:
        if not isinstance(product, dict):
            raise SourceValidationError("Product must be an object")
        product_id = product.get("id")
        if not isinstance(product_id, str) or not re.fullmatch(r"KB-\d{3}", product_id):
            raise SourceValidationError("Invalid product id")
        if product_id in ids:
            raise SourceValidationError("Duplicate product id")
        ids.add(product_id)
        price = product.get("price")
        if isinstance(price, bool) or not isinstance(price, (int, Decimal)):
            raise SourceValidationError("Price must be a JSON number")
        amount = Decimal(price)
        try:
            valid_price = amount.is_finite() and amount > 0 and amount == amount.quantize(Decimal("0.01"))
        except InvalidOperation:
            valid_price = False
        if not valid_price:
            raise SourceValidationError("Price must be positive, finite and exact to kopecks")
        attrs = product.get("characteristics")
        if not isinstance(attrs, dict) or not isinstance(attrs.get("fragrance_free"), bool):
            raise SourceValidationError("Product characteristics require a boolean fragrance_free")
        for key in ("name", "description"):
            if not isinstance(product.get(key), str) or not product[key].strip():
                raise SourceValidationError(f"Product requires {key}")
        if not isinstance(attrs.get("category"), str) or not attrs["category"].strip():
            raise SourceValidationError("Product requires category")
        for key in ("skin_types", "key_ingredients"):
            value = attrs.get(key)
            if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
                raise SourceValidationError(f"Product requires {key}")
    return catalog


def audit_bundle(data_dir: Path) -> dict:
    """Return counts and byte hashes; never modify source files or an index."""
    catalog = load_catalog(data_dir / "products.json")
    sections = []
    hashes = {}
    for filename, prefix, count in (
        ("delivery_and_returns.md", "DR", 6),
        ("payment_and_loyalty.md", "PL", 5),
    ):
        try:
            raw = (data_dir / filename).read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise SourceValidationError(f"Cannot read policy: {filename}") from exc
        found = re.findall(r"^## ((?:DR|PL)-\d{2})\.", text, re.MULTILINE)
        expected = [f"{prefix}-{i:02d}" for i in range(1, count + 1)]
        if found != expected:
            raise SourceValidationError(f"Missing, duplicate or out-of-order policy sections: {filename}")
        sections.extend(found)
        hashes[filename] = hashlib.sha256(raw).hexdigest()
    hashes["products.json"] = hashlib.sha256((data_dir / "products.json").read_bytes()).hexdigest()
    return {"products": len(catalog["products"]), "policy_sections": len(sections),
            "section_ids": sections, "source_sha256": hashes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the K-Beauty source bundle")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    try:
        result = audit_bundle(args.data_dir)
    except SourceValidationError as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "valid", **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
