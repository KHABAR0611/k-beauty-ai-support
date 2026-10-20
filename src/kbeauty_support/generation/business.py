"""Approved version1.1 monetary logic; no money inferred by a language model."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from .errors import InsufficientContext


def calculate(value, products: dict) -> dict:
    missing = []
    if value.items is None and value.subtotal_kopecks is None:
        missing.append("pricing.items_or_subtotal_kopecks")
    if value.delivery is None:
        missing.append("pricing.delivery")
    if value.delivery == "pickup" and value.pickup_available is None:
        missing.append("pricing.pickup_available")
    if value.registered is None:
        missing.append("pricing.registered")
    if value.promo_code and value.first_order is None:
        missing.append("pricing.first_order")
    if value.bonus_requested not in (None, 0) and value.bonus_balance is None:
        missing.append("pricing.bonus_balance")
    if missing:
        raise InsufficientContext(missing)
    if value.delivery == "pickup" and not value.pickup_available:
        raise InsufficientContext(["available_delivery_method"])
    if value.promo_code and (not value.registered or not value.first_order):
        raise InsufficientContext(["promo_eligibility_not_satisfied"])
    if value.bonus_requested not in (None, 0) and not value.registered:
        raise InsufficientContext(["registered_account_required_for_bonus"])
    if value.items:
        if any(p.product_id not in products for p in value.items):
            raise InsufficientContext(["catalog_product_id"])
        subtotal = sum(products[p.product_id]["price_kopecks"]*p.quantity for p in value.items)
    else:
        subtotal = value.subtotal_kopecks
    if subtotal > 100_000_000:
        raise InsufficientContext(["supported_basket_limit"])
    if value.promo_code and subtotal < 150000:
        raise InsufficientContext(["promo_minimum_goods_1500_rub"])
    discount = int((Decimal(subtotal)*Decimal("0.10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if value.promo_code else 0
    discounted = subtotal-discount
    cap = discounted*20//10000
    requested = value.bonus_balance if value.bonus_requested == "maximum" else (value.bonus_requested or 0)
    spent = min(value.bonus_balance or 0, requested, cap) if value.registered else 0
    goods = discounted-spent*100
    threshold, fee = {"pickup":(250000,25000),"moscow_courier":(350000,35000),"spb_courier":(350000,40000)}[value.delivery]
    delivery = 0 if goods >= threshold else fee
    return {"rules_version":"1.1","input_basis":"catalog" if value.items else "user_declared_subtotal",
            "subtotal_kopecks":subtotal,"discount_kopecks":discount,"after_promo_kopecks":discounted,
            "bonus_cap":cap,"bonuses_spent":spent,"goods_cash_kopecks":goods,"delivery_kopecks":delivery,
            "total_kopecks":goods+delivery,"bonuses_earned":goods*5//10000 if value.registered else 0,
            "conditional_estimate":True}


def pricing_options(value, products: dict) -> dict:
    result = calculate(value, products)
    if value.compare_options:
        result["options"] = {
            "promo_only":calculate(value.model_copy(update={"bonus_requested":0,"compare_options":False}),products),
            "bonus_only":calculate(value.model_copy(update={"promo_code":None,"compare_options":False}),products)}
    return result


def rubles(kopecks: int) -> str:
    return f"{kopecks//100:,}".replace(","," ")+f",{kopecks%100:02d} ₽"


def calculation_text(result: dict) -> str:
    parts=["Расчётный пример по переданным условиям. Реальный заказ, право на промокод и баланс не проверены.",
        f"Товары: {rubles(result['subtotal_kopecks'])}; скидка: {rubles(result['discount_kopecks'])}; списание: {result['bonuses_spent']} бонусов.",
        f"Оплата товаров деньгами: {rubles(result['goods_cash_kopecks'])}; доставка: {rubles(result['delivery_kopecks'])}; итого: {rubles(result['total_kopecks'])}.",
        f"Будущее начисление: {result['bonuses_earned']} бонусов при соблюдении правил получения и отсутствия возврата."]
    if result.get('options'):
        parts.append(f"Только промокод: {rubles(result['options']['promo_only']['total_kopecks'])}; только бонусы: {rubles(result['options']['bonus_only']['total_kopecks'])}.")
    return "\n".join(parts)


def catalog_search(query, products: dict) -> dict:
    def normalized(text):
        return text.casefold().replace("ё","е")
    matches, alternatives = [], []
    for sku, record in products.items():
        p=record["product"]; c=p["characteristics"]
        if query.category and normalized(c["category"]) != normalized(query.category):
            continue
        if query.skin_type and query.skin_type not in c["skin_types"] and "все типы" not in c["skin_types"]:
            continue
        if query.fragrance_free is not None and c["fragrance_free"] != query.fragrance_free:
            continue
        if query.ingredient and normalized(query.ingredient) not in normalized(" ".join(c["key_ingredients"])):
            continue
        entry={"product_id":sku,"name":p["name"],"price_kopecks":record["price_kopecks"],"characteristics":c}
        if query.max_price_kopecks is not None and entry["price_kopecks"]>query.max_price_kopecks:
            alternatives.append({**entry,"budget_excess_kopecks":entry["price_kopecks"]-query.max_price_kopecks})
        else:
            matches.append(entry)
    return {"catalog_version":"1.1","catalog_size":len(products),"matches":matches,
            "over_budget_alternatives":sorted(alternatives,key=lambda x:(x["price_kopecks"],x["product_id"])),
            "availability_verified":False,"medical_effect_verified":False,"future_supply_known":False}
