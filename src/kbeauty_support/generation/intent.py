"""Bounded domain intents and question obligations; no classifier model or scores."""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class Intent:
    facets: tuple[str, ...]
    sections: frozenset[str]
    clarification: str | None = None
    external: bool = False


def analyze(question: str) -> Intent:
    q=unicodedata.normalize('NFKC',question).casefold().replace('ё','е')
    def has(pattern: str) -> bool:
        return bool(re.search(pattern,q))
    sections=set(re.findall(r'\bKB-\d{3}\b',q.upper()))
    facets=[]
    def need(name: str, *units: str):
        facets.append(name);sections.update(units)
    # Personal order references distinguish transactions from general tracking instructions.
    personal=has(r'заказ\w*\s*[№#]?\s*\d+|(?:мой|моего|моему|наш)\s+заказ|трек\w*\s*[№#]?\s*\d+')
    external=(personal and has(r'где|статус|проверь|отслед|найди|приеха|едет|дош[ео]л|получ|оплачен|прибы|выдач')) or has(r'верни.{0,30}деньг|оформи.{0,30}возврат')
    defect=has(r'брак|поврежд|разбит|дефект|не\s+тот\s+товар|неверн\w*\s+товар|ошибк\w*\s+комплектац|перепут|48\s*час')
    negative=re.sub(r'(?:брака|дефекта|повреждений)\s+нет|(?:без|нет)\s+(?:брака|дефектов|повреждений)','',q)
    if negative!=q:
        defect=bool(re.search(r'брак|поврежд|разбит|дефект|не\s+тот\s+товар|48\s*час',negative))
    refund=has(r'отмен|возврат|вернут|вернуть|верну|верни|пломб|вскры|пересылк|отправ.{0,20}обратно')
    if defect:
        need('defect_or_wrong_item','DR-05')
        if has(r'когда|срок|перечисл|за\s+весь\s+заказ|денежн|ден[еь]г'):
            need('refund_amount_and_deadline','DR-06')
    elif refund:
        need('quality_return_or_cancellation','DR-04','DR-06')
        if has(r'верни.*деньг|оформи.*возврат'):
            need('requested_refund_action','DR-05')
    storage=has(r'хран|посылк.{0,20}лежит|лежит.{0,20}(?:пункт|пвз)|трек|отслеж')
    if storage:
        need('storage_or_tracking_instructions','DR-03')
    shipping=has(r'достав|курьер|пвз|сборк|отправк|перевоз|привез|привез|самовывоз|пункт.{0,12}выдач')
    promo_only_shipping=has(r'welcome|промокод') and not has(r'курьер|пвз|тариф|стоим|стоит|сборк|перевоз|бесплат')
    if shipping and not promo_only_shipping and not (storage and not has(r'тариф|стоит|стоим|бесплат|перевоз|курьер|сборк|достав')) and (not refund or external or has(r'курьер|сборк|сколько.*стоит')):
        need('delivery_geography_and_transit','DR-01','DR-02')
    bonus=has(r'бонус|балл')
    promo=has(r'welcome|промокод|скидочн\w*\s+код')
    lifetime=bonus and has(r'срок|жив|сгор|начисл|появ|действ|протух|поступ') and not has(r'спис|промокод|welcome|итог|рассчит|лимит|процент')
    if lifetime:
        need('bonus_accrual_and_expiry','PL-03')
    elif bonus:
        if has(r'спис|лимит|потолок|20\s*(?:%|процент)|совмещ'):
            need('bonus_redemption_and_calculation','PL-02','PL-04','PL-05')
            if has(r'начисл|появ|сгор|срок.*бонус'):
                need('bonus_accrual_and_expiry','PL-03')
        else:
            need('bonus_rules_unspecified','PL-02','PL-03','PL-04','PL-05')
    elif promo:
        need('promo_eligibility','PL-02')
    # Paying for a return shipment is not a checkout payment-method question.
    payment_method=has(r'наличн|наличк|cvv|cvc|сбп|карт|чек|рассроч|кошелек')
    payment_event=has(r'оплат|оплач|списал.{0,15}деньг') and not (shipping or bonus or promo)
    if ((payment_method or payment_event) and not (refund or defect)) or has(r'сбп|наличн|наличк|cvv|cvc'):
        need('checkout_payment','PL-01')
    product_topic=has(r'крем|тонер|сыворот|маск|бальзам|флюид|spf|ретинол|ингредиент|ниацинамид|han river|bomi lab|отдуш|кож|умыван|очищ|пенк|волос')
    clarification=None
    if not sections and has(r'\bон\b|\bона\b|\bнего\b|\bнее\b|\bэтот\b|\bэтого\b') and product_topic:
        clarification='product_reference'
    elif not sections and product_topic:
        clarification='catalog_query'
    if sections and any(s.startswith('KB-') for s in sections):facets.append('identified_product')
    if external and not sections:
        need('external_order_capability','DR-03')
    return Intent(tuple(facets),frozenset(sections),clarification,external)


def verify_coverage(question: str, selected_sections: set[str], *, tool: bool = False) -> tuple[bool,list[str]]:
    """Re-evaluate obligations against actual output, never trust context.required_sections alone.

    This is a finite-domain safety check, not a universal semantic entailment model.
    Unknown intents cannot acquire evidence simply through a high retrieval score.
    """
    intent=analyze(question)
    missing=sorted(intent.sections-selected_sections)
    return bool(tool or (intent.sections and not intent.clarification and not missing)),missing
