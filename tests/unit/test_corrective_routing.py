"""Domain safety regressions, with explicitly isolated retrieval/provider doubles."""
import sys
from pathlib import Path
import pytest
pytest.importorskip('fastapi')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api_helpers import make_service
from kbeauty_support.api.models import ChatRequest,ProviderDraft,Selection
from kbeauty_support.generation.intent import analyze,verify_coverage
from kbeauty_support.generation.provider import Generation
from kbeauty_support.generation.errors import ServiceError


@pytest.mark.parametrize('question,required',[
 ('Прислали не тот товар, кто оплатит пересылку обратно?',{'DR-05'}),
 ('Ошибка комплектации, нужен возврат за весь заказ и срок денег',{'DR-05','DR-06'}),
 ('При дефекте всей посылки возврат денег включает исходную доставку?',{'DR-05','DR-06'}),
 ('Пломба целая, верну товар. Когда деньги?',{'DR-04','DR-06'}),
 ('Где взять трек и сколько хранится посылка?',{'DR-03'}),
 ('WELCOME10 для второго заказа и доставки?',{'PL-02'}),
 ('Курьер после оплаты: сборка и перевозка?',{'DR-01','DR-02'}),
 ('Бонусы когда начисляются и когда сгорят?',{'PL-03'}),
 ('Потолок 20 процентов списания бонусов до промокода или после?',{'PL-02','PL-04','PL-05'}),
])
def test_obligations(question,required):
    assert analyze(question).sections==required


@pytest.mark.parametrize('question,status',[
 ('Где взять трек после отправки?','answered'),
 ('Заказ 12345 приехал или ещё едет?','requires_external_data'),
 ('А у него отдушка есть?','clarification_needed'),
 ('Мне нужна маска для сухой кожи','clarification_needed'),
 ('Хочу средство для волос','clarification_needed'),
 ('Сколько хранится посылка?','answered'),
])
def test_route_contract(question,status):
    code,response=make_service().chat(ChatRequest(question=question),'test')
    assert code==200 and response.status==status


def test_payment_source_does_not_support_defect_question_even_if_context_claims_coverage():
    assert verify_coverage('Не тот товар, кто оплатит пересылку обратно?',{'PL-01'})==(False,['DR-05'])
    assert verify_coverage('Когда вернут деньги за брак всего заказа?',{'DR-05'})[0] is False


def test_partial_selection_has_diagnostic_coverage_and_never_answered():
    service=make_service()
    def incomplete(q,e,t):
        unit=next(x for x in e if x['section']=='DR-05')
        return Generation(ProviderDraft(abstain=False,selections=[Selection(source_id=unit['source_id'],evidence_id=unit['evidence_id'])]),{})
    service.provider.generate=incomplete
    _,response=service.chat(ChatRequest(question='Брак всего заказа: когда вернут деньги?'),'test')
    assert response.status=='insufficient_context'
    assert response.diagnostics['selected_sections']==['DR-05']
    assert response.diagnostics['missing_obligation_sections']==['DR-06']
    assert response.diagnostics['model_abstained'] is False


def test_timeout_is_error_with_attempt_trace_no_retry_or_success():
    service=make_service();calls=[]
    def timeout(*args):
        calls.append(1);raise ServiceError('llm_timeout',504)
    service.provider.generate=timeout
    code,response=service.chat(ChatRequest(question='Доставка курьером'),'test')
    assert code==504 and response.status=='system_error' and not response.sources
    assert response.diagnostics['llm_attempted'] and len(calls)==1


def test_unknown_question_cannot_become_answered_from_retrieval_alone():
    assert not verify_coverage('Почему небо голубое?',{'PL-01','DR-02'})[0]
