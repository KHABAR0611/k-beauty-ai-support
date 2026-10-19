"""Independently verify numeric acceptance references against source prices.

These checks do not exercise a calculator or a RAG service, neither exists yet.
"""

import json
import re
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "data/products.json").read_text(encoding="utf-8"))
PRICES = {p["id"]: Decimal(p["price"]) for p in CATALOG["products"]}


def test_reference_baskets_t01_t06():
    # Independent arithmetic for the documented acceptance amounts.
    assert Decimal(3400) + 350 == 3750
    assert sum(PRICES[p] for p in ["KB-001", "KB-006", "KB-009"]) == 2870
    basket = PRICES["KB-003"] + PRICES["KB-004"]
    net = basket * Decimal("0.90")
    assert basket == 3380 and net == 3042 and net + 400 == 3442
    assert (net * Decimal("0.05")).to_integral_value(rounding=ROUND_DOWN) == 152
    basket = PRICES["KB-001"] + PRICES["KB-008"]
    spent = (basket * Decimal("0.20")).to_integral_value(rounding=ROUND_DOWN)
    assert spent == 444 and basket - spent + 250 == 2026
    assert ((basket - spent) * Decimal("0.05")).to_integral_value(rounding=ROUND_DOWN) == 88
    assert Decimal(2500) * Decimal("0.90") + 250 == 2500
    assert Decimal(2500) - 500 == 2000
    assert (Decimal(2250) * Decimal("0.05")).to_integral_value(rounding=ROUND_DOWN) == 112
    assert Decimal(2000) * Decimal("0.05") == 100
    assert Decimal(3500) * Decimal("0.20") == 700
    assert Decimal(3500) - 700 == 2800 and Decimal(2800) * Decimal("0.05") == 140


def test_t09_exact_product_constraints():
    matches = [p for p in CATALOG["products"] if p["price"] <= 1800
               and p["characteristics"]["category"] == "крем"
               and p["characteristics"]["fragrance_free"]
               and "сухая" in p["characteristics"]["skin_types"]]
    assert [p["id"] for p in matches] == ["KB-004"]
    assert matches[0]["characteristics"]["volume_ml"] == 50


def test_acceptance_case_ids_and_sources_are_consistent():
    text = (ROOT / "tests/acceptance-tests.md").read_text(encoding="utf-8")
    assert re.findall(r"^\| (T\d{2}) \|", text, re.MULTILINE) == [f"T{i:02d}" for i in range(1, 13)]
    policy = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "data").glob("*.md"))
    defined = set(re.findall(r"^## ((?:DR|PL)-\d{2})\.", policy, re.MULTILINE))
    assert set(re.findall(r"(?:DR|PL)-\d{2}", text)) <= defined


def test_migration_preserves_commercial_terms():
    text = (ROOT / "data/payment_and_loyalty.md").read_text(encoding="utf-8")
    assert "нельзя совмещать со списанием бонусов" in text
    assert "округляется вниз" in text
    delivery = (ROOT / "data/delivery_and_returns.md").read_text(encoding="utf-8")
    assert "после промокода, но до списания бонусов" in delivery
    assert "не автоматическое основание отказать позже" in delivery
