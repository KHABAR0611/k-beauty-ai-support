"""Semantic request planning and source-bound claims, without generated business facts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from .errors import ServiceError

# Capabilities describe the product contract, not evaluation phrases or expected answers.
# Each information capability binds to immutable sources and literal authoritative anchors.
CAPABILITIES = {
    'delivery':('География, способы, тарифы, сроки, сборка, пороги бесплатной доставки. Только курьер или ПВЗ.',{'DR-01':'только по России','DR-02':'после применения промокода и списания бонусов'}),
    'tracking':('Общие инструкции: где найти трек-номер и сколько хранится посылка в пункте. Не личный статус.',{'DR-03':'7 календарных дней'}),
    'quality_return':('Передумали, исправный товар, запечатанная или вскрытая упаковка; условия возврата или отмены.',{'DR-04':'7 календарных дней','DR-06':'10 календарных дней'}),
    'defect':('Протекание, разбитая упаковка, повреждение, ошибка: прислали другую позицию. Фото, проверка, пересылка.',{'DR-05':'оплачивает магазин'}),
    'refund_money':('Сумма и срок возврата денег, восстановление бонусов, исходная доставка при возврате/отмене.',{'DR-04':'включая оплаченную доставку','DR-05':'за весь заказ','DR-06':'фактически уплаченная денежная часть'}),
    'payment':('Способы оплаты: карта/СБП, наличные, рассрочка; комиссия, чек, ожидание платежа, списание без подтверждения.',{'PL-01':'Наличными, при получении и в рассрочку оплатить нельзя'}),
    'promo':('Право и условия WELCOME10: первый зарегистрированный заказ, минимум, повторное применение.',{'PL-02':'первого заказа зарегистрированного клиента'}),
    'accrual':('Начисление баллов: процент, денежная база без доставки, когда появляются и когда сгорают бонусы.',{'PL-03':'180 календарных дней'}),
    'redemption':('Правила списания баллов, лимит, совмещение со скидкой, порядок скидок и влияние на бесплатную доставку.',{'PL-02':'можно совмещать','PL-03':'без доставки','PL-04':'20% стоимости товаров после применения промокода','PL-05':'Денежный итог'}),
    'product':('Факты об определённом товаре: цена, состав, объём, SPF, отдушка. Для точного ответа нужен артикул.',{}),
    'calculate':('Действие: вычислить персональную денежную сумму корзины, итог, сколько заплатить или списать. Нужны данные корзины, не только общие правила.',{}),
    'recommend':('Действие: подобрать или предложить подходящее средство по пожеланиям, коже, бюджету. Нужны структурированные параметры каталога.',{}),
    'order_action':('Действие во внешней системе: проверить личный заказ/оплату, найти посылку, выполнить возврат денег. Общая инструкция о треке сюда не относится.',{}),
    'human':('Пользователь хочет живого сотрудника, консультанта, специалиста или оспаривает решение. Нужна передача человеку.',{}),
    'reference':('Неясно, о каком товаре речь: местоимение без артикула; нужно уточнить предмет вопроса.',{}),
    'unsupported':('Запрошены неизвестное условие/свойство/способ или тема вне перечисленных возможностей. Часть вопроса не поддержана. Нельзя подменять её общей справкой.',{}),
}

MODE_TEXTS = {
 'information':('Каковы правила магазина?','Как устроена доставка и возврат?','Какие условия оплаты, скидок и бонусов?',
                'Сколько стоит конкретный товар, каковы его объём и состав?','Каков срок начисления баллов и правила процента от оплаты?'),
 'calculate':('Рассчитай мою корзину, сколько я заплачу?','Посчитай итог с доставкой, скидкой и баллами.','Вычисли сумму оплаты за заказ.'),
 'recommend':('Подбери мне подходящую косметику по бюджету.','Посоветуй средство для моей кожи.'),
 'human':('Соедините с живым специалистом поддержки.','Хочу поговорить с консультантом, а не автоматом.'),
 'personal_order':('Где мой заказ и почему он задерживается?','Моя посылка приехала или ещё едет? Проверь.'),
 'reference':('А у него есть отдушка?','Он подходит мне? О каком товаре речь?'),
 'unsupported':('Необычный способ доставки, не описанный в правилах.','Можно организовать дополнительные услуги вне условий магазина?'),
}
TOPIC_TEXTS = {
 'delivery':('Куда вы отправляете покупки, какой способ и сколько стоит пересылка?','География доставки, наличие пунктов выдачи, время сборки и перевозки.'),
 'tracking':('Где найти номер отправления и сколько хранится посылка?','Как долго покупка лежит в пункте выдачи?'),
 'quality_return':('Можно сдать исправную косметику обратно, если передумала?','Вскрытая или запечатанная упаковка и срок возврата товара.'),
 'defect':('Пришла другая позиция или повреждённый товар, нужны фото и пересылка назад.','Нарушена герметичность, содержимое вытекло, обнаружена ошибка комплектации.'),
 'refund_money':('Когда и сколько денег возвращается после отмены или возврата?','Срок перечисления денег и восстановление баллов.'),
 'payment':('Какие способы оплаты, наличные или карта, чек и комиссия?','Можно отдать купюры при получении или нужна онлайн оплата?'),
 'promo':('Кому доступна скидка WELCOME10 и на каких условиях?','Промокод для первого или повторного заказа, минимальная сумма.'),
 'accrual':('Когда начисляются баллы, сколько процентов и когда они сгорают?','С какой денежной суммы считают бонусную награду, включается ли доставка?'),
 'redemption':('Можно совместить бонусы со скидкой и какой лимит списания?','В каком порядке применять промокод и баллы?'),
 'product':('Цена, состав, объём, SPF или отдушка определённого товара.','Характеристики косметики по артикулу.'),
}


class SemanticRouter:
    def __init__(self, encoder):
        self.encoder=encoder
        self.prototypes=[(kind,key,text) for kind,groups in [('mode',MODE_TEXTS),('topic',TOPIC_TEXTS)] for key,texts in groups.items() for text in texts]
        self.vectors=encoder.encode([text for _,_,text in self.prototypes])

    def classify(self, question: str) -> dict:
        query=self.encoder.encode([question])[0]
        grouped={'mode':{},'topic':{}}
        for (kind,key,_),vector in zip(self.prototypes,self.vectors,strict=True):
            score=sum(a*b for a,b in zip(query,vector,strict=True))
            grouped[kind][key]=max(grouped[kind].get(key,-1),score)
        ranked={kind:sorted(scores.items(),key=lambda item:(-item[1],item[0])) for kind,scores in grouped.items()}
        return {'mode':ranked['mode'][0][0],'margin':ranked['mode'][0][1]-ranked['mode'][1][1],
                'modes':[{'mode':key,'similarity':score} for key,score in ranked['mode']],
                'topic':ranked['topic'][0][0],'topic_margin':ranked['topic'][0][1]-ranked['topic'][1][1],
                'topics':[{'topic':key,'similarity':score} for key,score in ranked['topic']],
                'score_is_probability':False}


SECTION_CAPABILITY={'DR-01':'delivery','DR-02':'delivery','DR-03':'tracking','DR-04':'quality_return',
 'DR-05':'defect','DR-06':'refund_money','PL-01':'payment','PL-02':'promo','PL-03':'accrual','PL-04':'redemption','PL-05':'redemption'}

def override_sections(request, hits: list[dict], semantic: dict) -> set[str] | None:
    from .intent import analyze
    legacy=analyze(request.question)
    topic=semantic['topic'];score=semantic['topics'][0]['similarity']
    if topic in ('accrual','promo') and semantic['topic_margin']>=.08 and len(legacy.sections)>2:
        return set(CAPABILITIES[topic][1])
    families=[{'quality_return','defect','refund_money'},{'promo','accrual','redemption'}]
    def related(left,right):
        return left==right or any(left in group and right in group for group in families)
    if legacy.sections and not legacy.clarification:
        existing={SECTION_CAPABILITY.get(s,'product' if s.startswith('KB-') else None) for s in legacy.sections}
        if semantic['topic_margin']<.08 or any(related(topic,key) for key in existing):
            return None
    if not hits or score<.55 or semantic['topic_margin']<.01:
        return None
    for hit in hits[:3]:
        selected=SECTION_CAPABILITY.get(hit['metadata']['section'])
        compatible=related(selected,topic)
        if selected and compatible:
            return set(CAPABILITIES[selected][1])
    return None


def bind_claims(records: list[dict],snapshot) -> list[dict]:
    result=[]
    for record in records:
        section=record['metadata']['section']
        expected=snapshot.sections.get(section)
        if expected is None or record['text']!=expected['text']:
            raise ServiceError('claim_source_mismatch')
        if record.get('product'):
            if record['metadata']['product_id'] not in snapshot.products:
                raise ServiceError('claim_product_parameter_missing')
            result.append({'section':section,'source_id':record['id'],'source_sha256':record['metadata']['source_sha256'],
                           'required_parameter':'product_id','parameter_value':record['metadata']['product_id']})
            continue
        anchors=sorted({claims[section] for _,claims in CAPABILITIES.values() if section in claims})
        if not anchors:raise ServiceError('unregistered_claim_source')
        for anchor in anchors:
            if anchor not in record['text']:raise ServiceError('claim_source_mismatch')
            start=record['text'].index(anchor)
            sentence_start=max(record['text'].rfind('.',0,start),record['text'].rfind('\n',0,start))+1
            sentence_end=record['text'].find('.',start+len(anchor))
            sentence_end=len(record['text']) if sentence_end<0 else sentence_end+1
            result.append({'section':section,'source_id':record['id'],'source_sha256':record['metadata']['source_sha256'],
                'anchor':anchor,'start':start,'end':start+len(anchor),'claim_sha256':hashlib.sha256(anchor.encode()).hexdigest(),
                'support_sentence':record['text'][sentence_start:sentence_end].strip()})
    return result


def support_bundle(records: list[dict], bindings: list[dict]) -> dict:
    import json
    scopes=sorted({CAPABILITIES[SECTION_CAPABILITY[r['metadata']['section']]][0] for r in records if not r.get('product')})
    anchors=sorted({b['support_sentence'] for b in bindings if 'support_sentence' in b})
    products=[r['product'] for r in records if r.get('product')]
    text=json.dumps({'source_scopes':scopes,'literal_support_anchors':anchors,'exact_products':products},ensure_ascii=False)
    identity=hashlib.sha256(json.dumps(bindings,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'source_id':identity,'evidence_id':identity+':support','section':'validated_source_bundle','text':text}
