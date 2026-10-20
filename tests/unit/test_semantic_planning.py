"""Semantic adapter and exact support contracts; all doubles are explicit."""
from pathlib import Path
import copy,hashlib,sys
import pytest
pytest.importorskip('fastapi')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api_helpers import make_service
from kbeauty_support.api.models import ChatRequest,ProviderDraft,Selection
from kbeauty_support.generation.planning import CAPABILITIES,bind_claims,support_bundle,override_sections
from kbeauty_support.generation.provider import Generation
from kbeauty_support.generation.errors import ServiceError

class SemanticDouble:
    def __init__(self,mode='information',topic='payment',margin=.2):
        self.mode,self.topic,self.margin=mode,topic,margin
    def classify(self,q):
        return {'mode':self.mode,'margin':self.margin,'topic':self.topic,'topic_margin':.12,
                'topics':[{'topic':self.topic,'similarity':.8}],'score_is_probability':False}

@pytest.mark.parametrize('mode,question,status',[
 ('calculate','Посчитайте корзину','clarification_needed'),
 ('recommend','Нужно средство для кожи','clarification_needed'),
 ('human','Живой консультант нужен','handoff_required'),
 ('information','Как оплачивать картой','answered'),
])
def test_action_contract_separate_from_source_selection(mode,question,status):
    service=make_service();service.semantic=SemanticDouble(mode)
    code,r=service.chat(ChatRequest(question=question),'test')
    assert code==200 and r.status==status

@pytest.mark.parametrize('section,topic',[('DR-01','delivery'),('DR-03','tracking'),('DR-05','defect'),('PL-01','payment')])
def test_semantic_fallback_uses_real_retrieved_source_family(section,topic):
    service=make_service();request=ChatRequest(question='Новая формулировка')
    hits=sorted(service.retriever.hits,key=lambda r:r['metadata']['section']!=section)
    feature=SemanticDouble(topic=topic).classify(request.question)
    assert override_sections(request,hits,feature)
    feature['topics'][0]['similarity']=.1
    assert override_sections(request,hits,feature) is None

def test_semantic_fallback_does_not_promote_incompatible_source():
    service=make_service();hits=sorted(service.retriever.hits,key=lambda r:r['metadata']['section']!='DR-01')
    assert override_sections(ChatRequest(question='Новая формулировка'),hits,SemanticDouble(topic='payment').classify('x')) is None

def test_source_bound_claim_spans_and_bundle_determinism():
    service=make_service();record=service.snapshot.sections['PL-01'];bindings=bind_claims([record],service.snapshot)
    for b in bindings:
        assert record['text'][b['start']:b['end']]==b['anchor']
        assert hashlib.sha256(b['anchor'].encode()).hexdigest()==b['claim_sha256']
    assert support_bundle([record],bindings)==support_bundle([record],bindings)
    changed=copy.deepcopy(record);changed['text']='Подмена'
    with pytest.raises(ServiceError):bind_claims([changed],service.snapshot)

def test_all_claim_anchors_are_valid_and_product_parameter_is_bound():
    service=make_service()
    for _,claims in CAPABILITIES.values():
        for section,anchor in claims.items():assert anchor in service.snapshot.sections[section]['text']
    record=service.snapshot.products['KB-004'];b=bind_claims([record],service.snapshot)[0]
    assert b['required_parameter']=='product_id' and b['parameter_value']=='KB-004'

def test_unknown_delivery_parameter_vetoes_otherwise_valid_bundle():
    service=make_service();service.semantic=SemanticDouble(topic='delivery')
    def generated(q,e,t):
        return Generation(ProviderDraft(abstain=False,selections=[Selection(source_id=e[0]['source_id'],evidence_id=e[0]['evidence_id'])]),{}, {'delivery_method':'другой'})
    service.provider.generate=generated
    _,r=service.chat(ChatRequest(question='Доставка необычным способом'),'test')
    assert r.status=='insufficient_context' and not r.sources

def test_model_cannot_select_invented_support_bundle():
    service=make_service();service.semantic=SemanticDouble()
    service.provider.generate=lambda *args:Generation(ProviderDraft(abstain=False,selections=[Selection(source_id='invented',evidence_id='invented')]),{})
    code,r=service.chat(ChatRequest(question='Оплата'),'test')
    assert code==502 and r.status=='system_error'

def test_partial_or_abstaining_selection_is_not_reported_answered():
    service=make_service();service.semantic=SemanticDouble()
    service.provider.generate=lambda *args:Generation(ProviderDraft(abstain=True,selections=[]),{})
    _,r=service.chat(ChatRequest(question='Оплата'),'test')
    assert r.status=='insufficient_context'

@pytest.mark.parametrize('value,valid',[('другой',True),('самолёт',False)])
def test_actual_provider_delivery_parameter_schema_and_strict_validation(value,valid):
    import httpx,json
    from kbeauty_support.generation.provider import OllamaProvider
    digest='a'*64
    def handler(request):
        if request.method=='GET':return httpx.Response(200,json={'models':[{'name':'qwen3:0.6b','digest':digest,'context_length':8192}]})
        body=json.loads(request.content)
        assert body['format']['required']==['способ']
        assert len(body['messages'])==2 and body['messages'][1]['content']=='Другой способ?'
        content=json.dumps({'способ':value})
        return httpx.Response(200,json={'model':'qwen3:0.6b','done':True,'message':{'content':content}})
    provider=OllamaProvider('http://127.0.0.1:11434',model='qwen3:0.6b',expected_digest=digest,token_counter=lambda text:100,
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    evidence=[{'source_id':'bundle','evidence_id':'bundle:support','section':'support','text':'Доставка'}]
    if valid:assert provider.extract_delivery('Другой способ?',5).attributes['delivery_method']==value
    else:
        with pytest.raises(ServiceError,match='invalid_delivery_parameter'):provider.extract_delivery('Другой способ?',5)

@pytest.mark.parametrize('product_id',[f'KB-{n:03d}' for n in range(1,10)])
def test_support_bundle_preserves_exact_product_identity_and_price(product_id):
    import json
    service=make_service();record=service.snapshot.products[product_id]
    bundle=support_bundle([record],bind_claims([record],service.snapshot))
    assert json.loads(bundle['text'])['exact_products']==[record['product']]
