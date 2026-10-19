from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from uuid import UUID

import pytest

from kbeauty_support.ingestion import cli, pipeline, sources
from kbeauty_support.ingestion.audit import SourceValidationError

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data", data)
    return data


def update_catalog(data: Path, change) -> None:
    path = data / "products.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    change(catalog)
    path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")


def records(prepared: pipeline.PreparedBundle) -> dict[str, dict]:
    return {c["metadata"]["section"]: c for c in prepared.chunks}


def test_complete_inventory_and_exact_product_isolation(bundle):
    prepared = pipeline.prepare(bundle)
    catalog = json.loads((bundle / "products.json").read_text(encoding="utf-8"))
    products = [c for c in prepared.chunks if c["metadata"]["type"] == "product"]
    assert len(prepared.chunks) == 20
    assert len(products) == 9
    assert len({c["id"] for c in prepared.chunks}) == 20
    assert {c["metadata"]["product_id"] for c in products} == {p["id"] for p in catalog["products"]}
    for chunk in products:
        expected = next(p for p in catalog["products"] if p["id"] == chunk["metadata"]["product_id"])
        assert chunk["product"] == expected
        assert chunk["price_kopecks"] == expected["price"] * 100
        assert json.loads(chunk["text"].split("\n\n", 1)[1]) == {"currency": "RUB", **expected}


def test_all_chunks_have_stable_typed_metadata(bundle):
    prepared = pipeline.prepare(bundle)
    for chunk in prepared.chunks:
        assert UUID(chunk["id"]).version == 5
        meta = chunk["metadata"]
        assert meta["source"].startswith("data/") and not Path(meta["source"]).is_absolute()
        assert meta["section"] and meta["document_version"] == "1.1"
        assert meta["type"] in {"policy", "product"}
        assert meta["language"] == "ru"
        assert meta["preparation_generation"] == prepared.fingerprint
        assert len(meta["source_sha256"]) == len(meta["chunk_sha256"]) == 64
        assert meta["token_count"] is None
        assert ("product_id" in meta) == (meta["type"] == "product")


def test_every_policy_body_survives_without_truncation(bundle):
    prepared = records(pipeline.prepare(bundle))
    for filename, identity, prefix, count in (
        ("delivery_and_returns.md", "delivery_returns", "DR", 6),
        ("payment_and_loyalty.md", "payment_loyalty", "PL", 5),
    ):
        _, preamble, sections = sources.parse_policy((bundle / filename).read_bytes(), identity, prefix, count)
        for section, _, body in sections:
            assert prepared[section]["text"] == preamble + "\n\n" + body
    assert "| Москва | Курьер | 350 ₽ | 3 500 ₽ |" in prepared["DR-02"]["text"]
    assert "после применения промокода и списания бонусов" in prepared["DR-02"]["text"]
    assert "не автоматическое основание отказать позже" in prepared["DR-05"]["text"]
    assert "можно совмещать со списанием бонусов" in prepared["PL-02"]["text"]
    assert "Доставку бонусами оплатить нельзя" in prepared["PL-04"]["text"]
    assert "6. Будущее начисление" in prepared["PL-05"]["text"]


def test_export_is_byte_deterministic_and_idempotent(bundle, tmp_path):
    first, second = pipeline.prepare(bundle), pipeline.prepare(bundle)
    assert first.fingerprint == second.fingerprint and first.files == second.files
    output = tmp_path / "output"
    target = pipeline.export(first, output, bundle)
    assert pipeline.export(second, output, bundle) == target
    assert [p.name for p in (output / "generations").iterdir()] == [first.fingerprint]
    assert (output / "CURRENT").read_text().strip() == first.fingerprint
    for name, content in first.files.items():
        assert (target / name).read_bytes() == content
    manifest = json.loads(first.files["manifest.json"])
    assert manifest["stage"] == "source_preparation" and not manifest["embedding_ready"]
    for name, expected in manifest["files_sha256"].items():
        assert pipeline.digest((target / name).read_bytes()) == expected


def test_document_update_keeps_logical_ids_but_changes_output(bundle, tmp_path):
    before = pipeline.prepare(bundle)
    path = bundle / "delivery_and_returns.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Срочная доставка не предусмотрена.", "Срочная доставка не предусмотрена. Дополнительный проверочный текст."), encoding="utf-8")
    after = pipeline.prepare(bundle)
    assert before.fingerprint != after.fingerprint
    left, right = records(before), records(after)
    assert left.keys() == right.keys()
    assert {c["id"] for c in before.chunks} == {c["id"] for c in after.chunks}
    assert left["DR-02"]["metadata"]["chunk_sha256"] != right["DR-02"]["metadata"]["chunk_sha256"]
    assert left["PL-02"]["text"] == right["PL-02"]["text"]
    output = tmp_path / "output"
    old_path = pipeline.export(before, output, bundle)
    pipeline.export(after, output, bundle)
    assert (output / "CURRENT").read_text().strip() == after.fingerprint
    assert (old_path / "chunks.jsonl").read_bytes() == before.files["chunks.jsonl"]


def test_deleted_product_leaves_no_ghost_record(bundle):
    before = pipeline.prepare(bundle)
    update_catalog(bundle, lambda c: c["products"].pop())
    after = pipeline.prepare(bundle)
    assert len(after.chunks) == 19
    assert "KB-009" not in records(after)
    assert b'"KB-009"' not in after.files["catalog.snapshot.json"]
    assert before.fingerprint != after.fingerprint


def test_decimal_price_and_unknown_characteristics_survive_exactly(bundle):
    path = bundle / "products.json"
    text = path.read_text(encoding="utf-8").replace('"price":890', '"price":890.15')
    path.write_text(text, encoding="utf-8")
    prepared = pipeline.prepare(bundle)
    assert records(prepared)["KB-001"]["price_kopecks"] == 89015
    assert b'"price":890.15' in prepared.files["catalog.snapshot.json"]


@pytest.mark.parametrize("text", ['{', '[]', '{"products":NaN}', '{"products":Infinity}', '{"currency":"RUB","currency":"USD"}'])
def test_invalid_json_never_exports(bundle, tmp_path, text):
    (bundle / "products.json").write_text(text, encoding="utf-8")
    with pytest.raises(SourceValidationError):
        pipeline.prepare(bundle)
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("mutate", [
    lambda c: c["products"].append(c["products"][0].copy()),
    lambda c: c["products"][0].update(price=True),
    lambda c: c["products"][0].update(price=-1),
    lambda c: c["products"][0].update(price="890"),
    lambda c: c["products"][0].update(price=0.001),
    lambda c: c["products"][0]["characteristics"].update(fragrance_free="false"),
    lambda c: c.update(version="2.0"),
    lambda c: c.update(effective_date="2026-02-30"),
])
def test_invalid_schema_or_bundle_versions_fail(bundle, mutate):
    update_catalog(bundle, mutate)
    with pytest.raises(SourceValidationError):
        pipeline.prepare(bundle)


@pytest.mark.parametrize("change", [
    lambda t: t.replace('version: "1.1"', 'version: "1.1"\nversion: "2.0"'),
    lambda t: t.replace("language: ru", "language: en"),
    lambda t: t.replace('effective_date: "2026-10-19"', 'effective_date: "not-a-date"'),
    lambda t: t.replace("## DR-02.", "## DR-99."),
    lambda t: t + "\n## DR-01. duplicate\ntext",
    lambda t: t[:t.index("## DR-06.")] + "## DR-06. Empty\n",
    lambda t: t.replace("---", "bad", 1),
])
def test_invalid_front_matter_and_sections_fail(bundle, change):
    path = bundle / "delivery_and_returns.md"
    path.write_text(change(path.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(SourceValidationError):
        pipeline.prepare(bundle)


def test_invalid_utf8_and_oversized_sources_fail(bundle, monkeypatch):
    path = bundle / "delivery_and_returns.md"
    path.write_bytes(b"\xff")
    with pytest.raises(SourceValidationError):
        pipeline.prepare(bundle)
    path.write_bytes(b"abcde")
    monkeypatch.setattr(sources, "MAX_SOURCE_BYTES", 4)
    with pytest.raises(SourceValidationError, match="size limit"):
        pipeline.prepare(bundle)


def test_non_allowlisted_path_and_input_output_overlap_fail(bundle):
    with pytest.raises(SourceValidationError, match="allowlist"):
        sources.read_source(bundle, "../secret.txt")
    with pytest.raises(SourceValidationError, match="overlap"):
        pipeline.export(pipeline.prepare(bundle), bundle / "generated", bundle)


def test_linked_source_is_rejected(bundle, tmp_path):
    if os.name == "nt":
        import _winapi
        linked = tmp_path / "linked-data"
        _winapi.CreateJunction(str(bundle), str(linked))
        with pytest.raises(SourceValidationError, match="junctions"):
            pipeline.prepare(linked)
        return
    real = bundle / "products.json"
    other = tmp_path / "outside.json"
    other.write_bytes(real.read_bytes())
    real.unlink()
    try:
        real.symlink_to(other)
    except OSError:
        pytest.skip("Host requires a symlink creation privilege")
    with pytest.raises(SourceValidationError, match="Symlinks"):
        pipeline.prepare(bundle)


def test_long_semantic_unit_fails_instead_of_truncating(bundle):
    with pytest.raises(SourceValidationError, match="safety limit"):
        pipeline.prepare(bundle, max_chunk_chars=100)


def test_line_endings_normalize_text_without_hiding_source_changes(bundle):
    before = pipeline.prepare(bundle)
    path = bundle / "delivery_and_returns.md"
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    after = pipeline.prepare(bundle)
    assert [c["text"] for c in before.chunks] == [c["text"] for c in after.chunks]
    assert before.fingerprint != after.fingerprint


def test_writer_lock_is_not_stolen(bundle, tmp_path):
    prepared = pipeline.prepare(bundle)
    output = tmp_path / "output"
    output.mkdir()
    lock = output / ".ingest.lock"
    lock.write_text("another-writer")
    with pytest.raises(pipeline.ExportError):
        pipeline.export(prepared, output, bundle)
    assert lock.read_text() == "another-writer"
    assert not (output / "CURRENT").exists()


@pytest.mark.parametrize("failure", [PermissionError, OSError, KeyboardInterrupt])
def test_write_failure_or_interrupt_keeps_previous_generation(bundle, tmp_path, monkeypatch, failure):
    output = tmp_path / "output"
    before = pipeline.prepare(bundle)
    target = pipeline.export(before, output, bundle)
    update_catalog(bundle, lambda c: c["products"][0].update(price=891))
    after = pipeline.prepare(bundle)
    actual_write = pipeline.write_file
    calls = 0

    def fail_during_export(path, data):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise failure("injected write failure")
        actual_write(path, data)

    monkeypatch.setattr(pipeline, "write_file", fail_during_export)
    with pytest.raises(KeyboardInterrupt if failure is KeyboardInterrupt else pipeline.ExportError):
        pipeline.export(after, output, bundle)
    assert (output / "CURRENT").read_text().strip() == before.fingerprint
    assert (target / "manifest.json").read_bytes() == before.files["manifest.json"]
    assert not (output / ".ingest.lock").exists()
    monkeypatch.setattr(pipeline, "write_file", actual_write)
    pipeline.export(after, output, bundle)
    assert (output / "CURRENT").read_text().strip() == after.fingerprint


def test_corrupt_existing_generation_is_not_reused(bundle, tmp_path):
    prepared = pipeline.prepare(bundle)
    output = tmp_path / "output"
    target = pipeline.export(prepared, output, bundle)
    (target / "chunks.jsonl").write_bytes(b"corrupted")
    with pytest.raises(pipeline.ExportError):
        pipeline.export(prepared, output, bundle)


def test_pointer_replace_failure_keeps_previous_current_and_can_retry(bundle, tmp_path, monkeypatch):
    output = tmp_path / "output"
    before = pipeline.prepare(bundle)
    pipeline.export(before, output, bundle)
    update_catalog(bundle, lambda c: c["products"][0].update(price=892))
    after = pipeline.prepare(bundle)
    actual_replace = pipeline.os.replace

    def fail_pointer(source, destination):
        if Path(destination).name == "CURRENT":
            raise OSError("injected pointer replacement failure")
        return actual_replace(source, destination)

    monkeypatch.setattr(pipeline.os, "replace", fail_pointer)
    with pytest.raises(pipeline.ExportError):
        pipeline.export(after, output, bundle)
    assert (output / "CURRENT").read_text().strip() == before.fingerprint
    monkeypatch.setattr(pipeline.os, "replace", actual_replace)
    pipeline.export(after, output, bundle)
    assert (output / "CURRENT").read_text().strip() == after.fingerprint


def test_cli_dry_run_writes_nothing_and_error_codes_are_explicit(bundle, tmp_path, capsys):
    output = tmp_path / "output"
    args = ["--data-dir", str(bundle), "--output-dir", str(output)]
    assert cli.main(args + ["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["chunks"] == 20
    assert not output.exists()
    assert cli.main(args) == 0
    (output / ".ingest.lock").write_text("another-writer")
    assert cli.main(args) == 3
    (bundle / "products.json").write_text("{", encoding="utf-8")
    assert cli.main(args) == 2
