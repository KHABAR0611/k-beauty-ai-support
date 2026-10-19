"""Owner-approved business baseline, independent of model/retrieval output.

The pricing reference below verifies acceptance expectations, not a production
calculator. No API, embeddings or model answers are exercised here.
"""
from decimal import Decimal, ROUND_DOWN
import json
from pathlib import Path
import re

import pytest

from kbeauty_support.ingestion.pipeline import prepare

ROOT = Path(__file__).resolve().parents[2]
BASELINE = json.loads((ROOT / "tests/fixtures/business-acceptance-v1.1.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "data/products.json").read_text(encoding="utf-8"))
PRICES = {p["id"]: Decimal(p["price"]) for p in CATALOG["products"]}


def reference(input_values):
    subtotal = Decimal(input_values["subtotal"]) if "subtotal" in input_values else sum(
        PRICES[sku] * quantity for sku, quantity in input_values["products"].items())
    discounted = subtotal * (Decimal("0.9") if input_values.get("promo") else Decimal(1))
    spent = min(input_values.get("balance", 0), input_values.get("requested", 0),
                int((discounted * Decimal("0.2")).to_integral_value(rounding=ROUND_DOWN)))
    goods_cash = discounted - spent
    threshold, fee = {"pickup": (2500, 250), "moscow_courier": (3500, 350), "spb_courier": (3500, 400)}[input_values["delivery"]]
    delivery = Decimal(0 if goods_cash >= threshold else fee)
    return {"goods_cash": f"{goods_cash:.2f}", "delivery": f"{delivery:.2f}",
            "total": f"{goods_cash+delivery:.2f}",
            "bonuses": int((goods_cash * Decimal("0.05")).to_integral_value(rounding=ROUND_DOWN))}


@pytest.mark.parametrize("case", [c for c in BASELINE["cases"] if "input" in c], ids=lambda c: c["id"])
def test_numeric_scenario_matches_independent_owner_baseline(case):
    assert reference(case["input"]) == case["expected"]


@pytest.mark.parametrize("sku,price", BASELINE["prices"].items())
def test_owner_approved_prices_and_prepared_payload(sku, price):
    assert PRICES[sku] == price
    chunk = next(c for c in prepare(ROOT / "data").chunks if c["metadata"].get("product_id") == sku)
    assert chunk["product"]["price"] == price
    assert chunk["price_kopecks"] == price * 100


@pytest.mark.parametrize("method,threshold,fee", [("pickup",2500,250),("moscow_courier",3500,350),("spb_courier",3500,400)])
def test_bonus_redemption_can_remove_free_delivery(method, threshold, fee):
    assert reference({"subtotal": threshold,"delivery": method})["delivery"] == "0.00"
    assert reference({"subtotal": threshold,"delivery": method,"balance":1,"requested":1})["delivery"] == f"{fee:.2f}"
    # Inclusive threshold after a real redemption, not the original basket.
    assert reference({"subtotal":threshold+100,"delivery":method,"balance":100,"requested":100})["delivery"] == "0.00"


def test_promo_and_bonus_are_combined_with_cap_after_discount():
    result = reference({"subtotal":2500,"promo":True,"balance":500,"requested":500,"delivery":"pickup"})
    assert result == {"goods_cash":"1800.00","delivery":"250.00","total":"2050.00","bonuses":90}
    assert reference({"subtotal":2500,"promo":True,"delivery":"pickup"})["total"] == "2500.00"
    assert reference({"subtotal":2500,"balance":500,"requested":500,"delivery":"pickup"})["total"] == "2250.00"


@pytest.mark.parametrize("balance,requested,expected_cash", [(999,999,"1800.90"),(10,500,"2240.90"),(999,7,"2243.90")])
def test_discounted_cap_rounds_down_and_respects_available_and_requested_bonus(balance,requested,expected_cash):
    result = reference({"subtotal":2501,"promo":True,"balance":balance,"requested":requested,"delivery":"pickup"})
    assert result["goods_cash"] == expected_cash


def test_published_chunk_examples_and_manifest_are_current():
    prepared = prepare(ROOT / "data")
    current = {c["id"]:c for c in prepared.chunks}
    samples = [json.loads(line) for line in (ROOT / "examples/prepared-chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(samples) == 7
    assert all(sample == current[sample["id"]] for sample in samples)
    assert json.loads((ROOT / "examples/manifest.json").read_text())["fingerprint"] == prepared.fingerprint


def test_corrected_policy_conditions_reach_chunks():
    chunks = {c["metadata"]["section"]:c for c in prepare(ROOT / "data").chunks}
    assert "после применения промокода и списания бонусов" in chunks["DR-02"]["text"]
    assert "WELCOME10 можно совмещать со списанием бонусов" in chunks["PL-02"]["text"]
    assert "20% стоимости товаров после применения промокода" in chunks["PL-04"]["text"]
    assert "после промокода и списания бонусов" in chunks["PL-05"]["text"]
    for chunk in chunks.values():
        assert chunk["metadata"]["document_version"] == BASELINE["version"]


@pytest.mark.parametrize("case", [c for c in BASELINE["cases"] if "source_fragments" in c], ids=lambda c:c["id"])
def test_nonfinancial_scenarios_have_supporting_source_facts(case):
    chunks = {c["metadata"]["section"]:c["text"] for c in prepare(ROOT / "data").chunks}
    source_text = "\n".join(chunks[source] for source in case["sources"] if source in chunks)
    assert all(fragment in source_text for fragment in case["source_fragments"])


def test_t09_has_no_matching_cream_under_budget():
    case = next(c for c in BASELINE["cases"] if c["id"] == "T09")
    matches = [p["id"] for p in CATALOG["products"] if p["price"] <= 1800
               and p["characteristics"]["category"] == "крем"
               and p["characteristics"]["fragrance_free"]
               and "сухая" in p["characteristics"]["skin_types"]]
    assert matches == case["expected"]["exact_matches"]
    assert PRICES["KB-004"]-1800 == case["expected"]["budget_excess"]


def test_all_twelve_scenarios_have_current_expectations_and_existing_sources():
    table = (ROOT / "tests/acceptance-tests.md").read_text(encoding="utf-8")
    expected_ids = [f"T{i:02d}" for i in range(1,13)]
    assert [c["id"] for c in BASELINE["cases"]] == expected_ids
    assert re.findall(r"^\| (T\d{2}) \|",table,re.MULTILINE) == expected_ids
    available = {c["metadata"]["section"] for c in prepare(ROOT / "data").chunks} | {"products.json"}
    for case in BASELINE["cases"]:
        assert case["expected"] and set(case["sources"]) <= available
        if "total" in case["expected"]:
            row = next(line for line in table.splitlines() if line.startswith(f"| {case['id']} |"))
            amount = f"{int(Decimal(case['expected']['total'])):,}".replace(","," ")
            assert amount in row


def test_t11_and_t12_remain_future_service_requirements_not_fake_e2e_results():
    cases = {c["id"]:c for c in BASELINE["cases"]}
    assert not any(cases["T11"]["expected"].values())
    assert not any(cases["T12"]["expected"].values())
    assert "ретинол" not in (ROOT / "data/products.json").read_text(encoding="utf-8").lower()
