import json
import shutil
from pathlib import Path

import pytest

from kbeauty_support.ingestion.audit import SourceValidationError, audit_bundle, load_catalog, main

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def bundle(tmp_path):
    target = tmp_path / "data"
    shutil.copytree(ROOT / "data", target)
    return target


def mutate_catalog(bundle, mutate):
    path = bundle / "products.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    mutate(catalog)
    path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")


def test_current_sources_are_valid_and_audit_is_read_only(bundle):
    before = {p.name: p.read_bytes() for p in bundle.iterdir()}
    result = audit_bundle(bundle)
    assert result["products"] == 9
    assert result["policy_sections"] == 11
    assert all(len(digest) == 64 for digest in result["source_sha256"].values())
    assert before == {p.name: p.read_bytes() for p in bundle.iterdir()}


def test_repeated_audit_is_deterministic(bundle):
    assert audit_bundle(bundle) == audit_bundle(bundle)


def test_source_change_updates_only_its_hash(bundle):
    before = audit_bundle(bundle)
    path = bundle / "delivery_and_returns.md"
    path.write_bytes(path.read_bytes() + "\n".encode())
    after = audit_bundle(bundle)
    assert before["source_sha256"]["delivery_and_returns.md"] != after["source_sha256"]["delivery_and_returns.md"]
    for name in ("products.json", "payment_and_loyalty.md"):
        assert before["source_sha256"][name] == after["source_sha256"][name]


@pytest.mark.parametrize("price", [True, False, "1790", -1, 0, 1.001, float("nan"), float("inf"), 1e100])
def test_invalid_price_is_rejected(bundle, price):
    mutate_catalog(bundle, lambda c: c["products"][0].update(price=price))
    with pytest.raises(SourceValidationError, match="Price"):
        load_catalog(bundle / "products.json")


def test_duplicate_product_is_rejected(bundle):
    mutate_catalog(bundle, lambda c: c["products"].append(c["products"][0].copy()))
    with pytest.raises(SourceValidationError, match="Duplicate"):
        audit_bundle(bundle)


def test_nonboolean_fragrance_is_rejected(bundle):
    mutate_catalog(bundle, lambda c: c["products"][0]["characteristics"].update(fragrance_free="false"))
    with pytest.raises(SourceValidationError, match="boolean"):
        audit_bundle(bundle)


@pytest.mark.parametrize("body", ["not json", "[]", "null", "true"])
def test_malformed_catalog_is_rejected(bundle, body):
    (bundle / "products.json").write_text(body, encoding="utf-8")
    with pytest.raises(SourceValidationError):
        audit_bundle(bundle)


def test_missing_policy_is_rejected(bundle):
    (bundle / "delivery_and_returns.md").unlink()
    with pytest.raises(SourceValidationError, match="Cannot read policy"):
        audit_bundle(bundle)


def test_missing_section_is_rejected(bundle):
    path = bundle / "delivery_and_returns.md"
    text = path.read_text(encoding="utf-8").replace("## DR-02.", "## Removed.")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SourceValidationError, match="sections"):
        audit_bundle(bundle)


def test_duplicate_section_is_rejected(bundle):
    path = bundle / "payment_and_loyalty.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n## PL-01. Duplicate\n", encoding="utf-8")
    with pytest.raises(SourceValidationError, match="sections"):
        audit_bundle(bundle)


def test_invalid_utf8_policy_is_rejected(bundle):
    (bundle / "payment_and_loyalty.md").write_bytes(b"\xff")
    with pytest.raises(SourceValidationError):
        audit_bundle(bundle)


def test_cli_exit_codes_and_machine_readable_errors(bundle, capsys):
    assert main(["--data-dir", str(bundle)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "valid"
    (bundle / "products.json").write_text("{", encoding="utf-8")
    assert main(["--data-dir", str(bundle)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"
