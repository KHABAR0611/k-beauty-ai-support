"""Development-set defects; no final-case hints or expected answers in runtime."""
import pytest

pytest.importorskip('fastapi')
from kbeauty_support.api.models import ChatRequest,PricingInput
from kbeauty_support.generation.context import required_sections
from kbeauty_support.generation.control import AnswerControl


@pytest.mark.parametrize('question',['Сколько бонусы живут и когда появляются?','Когда начислят бонусы и какой срок действия?'])
def test_lifetime_question_does_not_load_unrelated_discount_and_delivery(question):
    assert required_sections(ChatRequest(question=question))=={'PL-03'}


def test_lifetime_optimization_does_not_drop_combined_redemption_rules():
    required=required_sections(ChatRequest(question='Когда начислят бонусы, сколько можно списать с промокодом?'))
    assert {'PL-02','PL-03','PL-04','PL-05'}.issubset(required)


def test_typed_money_always_keeps_complete_rules():
    required=required_sections(ChatRequest(question='Когда бонусы появляются?',pricing=PricingInput(subtotal_kopecks=200000)))
    assert {'DR-01','DR-02','PL-02','PL-03','PL-04','PL-05'}.issubset(required)


def test_cancel_shipping_refund_keeps_refund_terms_not_new_shipment_tariffs():
    required=required_sections(ChatRequest(question='До передачи перевозчику отменяю заказ. Вернут ли плату за доставку?'))
    assert required=={'DR-04','DR-06'}


def test_mixed_return_and_new_delivery_keeps_both_topics():
    required=required_sections(ChatRequest(question='Возврат товара и сколько стоит курьер в Москве?'))
    assert {'DR-01','DR-02','DR-04','DR-06'}.issubset(required)


@pytest.mark.parametrize('question',['Оплачу наличкой при получении?','Хочу оплатить через СБП'])
def test_payment_inflections_are_routed_to_payment(question):
    assert 'PL-01' in required_sections(ChatRequest(question=question))


@pytest.mark.parametrize('question',['Хочу сотрудника поддержки','Мне нужен человек','Позови сотрудника'])
def test_explicit_employee_request_routes_to_pending_handoff(question):
    decision=AnswerControl().decide(question=question)
    assert decision.status=='handoff_required'
    assert AnswerControl.handoff(decision.reason,'test-request')['created'] is False
