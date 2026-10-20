"""Retrieval, exact tools, constrained generation and independent answer control."""
from __future__ import annotations

import json
import re
import time

from kbeauty_support.api.models import ChatResponse, Source
from .business import pricing_options, catalog_search, calculation_text
from .context import assemble, SourceConflict
from .control import AnswerControl, OutcomeMetrics
from .errors import ServiceError, InsufficientContext
from .intent import analyze, verify_coverage


class ChatService(OutcomeMetrics):
    def __init__(self, snapshot, retriever, provider, *, max_sources: int = 14, max_context_bytes: int = 24000):
        super().__init__()
        self.snapshot,self.retriever,self.provider=snapshot,retriever,provider
        self.max_sources,self.max_context_bytes=max_sources,max_context_bytes
        self.control=AnswerControl()

    def ready(self) -> dict:
        try:
            retrieval=self.retriever.ready()
        except Exception:
            retrieval={"ready":False,"code":"retrieval_unavailable"}
        llm=self.provider.ready()
        return {"ready":bool(retrieval["ready"] and llm["ready"]),"dependencies":{"retrieval":retrieval,"llm":llm}}

    def chat(self, request, request_id: str) -> tuple[int,ChatResponse]:
        started=time.perf_counter()
        timings={"preparation":0.0,"retrieval":0.0,"context":0.0,"tools":0.0,"llm":0.0,"answer_control":0.0}
        intent=analyze(request.question)
        trace={"intent_facets":list(intent.facets),"required_sections":[],"retrieved_sections":[],"context_sections":[],"selected_sections":[],"llm_attempted":False}
        generation=None
        llm_attempted=False
        def result(status, answer, *, http=200, sources=None, **kwargs):
            return http,ChatResponse(answer=answer,sources=sources or [],status=status,
                grounding_status="confirmed" if status=="answered" else "error" if status=="system_error" else "insufficient_context",
                request_id=request_id,latency_ms={**timings,"total":(time.perf_counter()-started)*1000},
                index_generation=generation,**{**kwargs,"diagnostics":{**trace,**kwargs.get("diagnostics",{})}})
        try:
            pre=self.control.decide(question=request.question)
            if pre.status=="handoff_required":
                return result(pre.status,"Нужна проверка сотрудником; обращение не передано, операторская система не подключена.",
                              handoff=self.control.handoff(pre.reason,request_id),diagnostics={"generation_performed":False})
            if re.search(r"(?:cvv|cvc|одноразов\w* код)\s*[:=]?\s*\d{3,}|\b(?:\d[ -]?){13,19}\b",request.question,re.I):
                raise ServiceError("payment_secrets_not_accepted",422)
            if request.pricing is None and re.search(r"итог|заплачу|спиш[иу]|спишите|рассчита",request.question,re.I):
                raise InsufficientContext(["pricing"])
            if request.catalog_query is None and request.pricing is None and (intent.clarification or re.search(r"подбери|порекомендуй",request.question,re.I)):
                raise InsufficientContext([intent.clarification or "catalog_query"])
            if request.pricing is None and request.catalog_query is None and not self.provider.ready()["ready"]:
                if pre.status=="handoff_required":
                    return result(pre.status,"Нужна проверка сотрудником; обращение не передано, операторская система не подключена.",
                                  handoff=self.control.handoff(pre.reason,request_id),diagnostics={"generation_performed":False})
                if pre.status=="requires_external_data":
                    return result(pre.status,"Нет доступа к внешней системе. Статус не проверен и действия не выполнены.",
                                  external_data={"system":"order_management","available":False,"action_performed":False},
                                  diagnostics={"generation_performed":False})
                raise ServiceError("llm_not_configured_or_unavailable")
            timings["preparation"]=(time.perf_counter()-started)*1000
            phase=time.perf_counter()
            retrieved=self.retriever.retrieve(request.question)
            timings["retrieval"]=(time.perf_counter()-phase)*1000
            generation=retrieved["generation"]
            for key,value in retrieved.get("timings_ms",{}).items():
                timings[key]=value
            hits=self.snapshot.validate(retrieved["hits"])
            trace["retrieved_sections"]=[h["metadata"]["section"] for h in hits]
            phase=time.perf_counter()
            context=assemble(request,hits,max_sources=self.max_sources,max_bytes=self.max_context_bytes)
            trace.update(required_sections=sorted(context.required_sections),context_sections=[h["metadata"]["section"] for h in context.records])
            if not context.records:
                return result("insufficient_context","В базе нет достаточных сведений для такого вопроса.")
            timings["context"]=(time.perf_counter()-phase)*1000
            phase=time.perf_counter()
            calculation=pricing_options(request.pricing,self.snapshot.products) if request.pricing else None
            catalog=catalog_search(request.catalog_query,self.snapshot.products) if request.catalog_query else None
            timings["tools"]=(time.perf_counter()-phase)*1000
            phase=time.perf_counter()
            selected={}
            usage=None;generation_performed=False;abstain=False
            if calculation or catalog or pre.status=="requires_external_data":
                # A typed, versioned calculator is the answer authority for exact money.
                # This is not a provider double and is never reported as LLM generation.
                selected={e["source_id"]:e for e in context.evidence.values()}
            else:
                llm_attempted=True
                trace["llm_attempted"]=True
                try:
                    generated=self.provider.generate(request.question,list(context.evidence.values()),{"calculation":calculation,"catalog":catalog})
                finally:
                    timings["llm"]=(time.perf_counter()-phase)*1000
                generation_performed=True;usage=generated.usage;abstain=generated.draft.abstain
                for claim in generated.draft.selections:
                    evidence=context.evidence.get(claim.evidence_id)
                    if evidence is None or evidence["source_id"]!=claim.source_id:
                        raise ServiceError("ungrounded_llm_output",502)
                    selected[evidence["source_id"]]=evidence
            phase=time.perf_counter()
            covered={e["section"] for e in selected.values()}
            semantic_ok,missing=verify_coverage(request.question,covered,tool=bool(calculation or catalog))
            enough=context.required_sections.issubset(covered) and semantic_ok
            trace.update(selected_sections=sorted(covered),model_abstained=abstain,missing_obligation_sections=missing,coverage_verified=semantic_ok)
            decision=self.control.decide(question=request.question,grounded=bool(selected) and not abstain,enough=enough)
            timings["answer_control"]=(time.perf_counter()-phase)*1000
            if decision.status=="insufficient_context":
                return result(decision.status,"Источники не подтверждают достаточно полный ответ. Уточните вопрос или обратитесь в поддержку.",
                              usage=usage,diagnostics={"generation_performed":generation_performed,"reason":decision.reason})
            sources=[];paragraphs=[]
            for record in context.records:
                if record["id"] not in selected:
                    continue
                meta=record["metadata"]
                sources.append(Source(source_id=record["id"],source=meta["source"],section=meta["section"],
                    document_version=meta["document_version"],product_id=meta.get("product_id"),usage="quoted"))
                paragraphs.append(selected[record["id"]]["text"]+" ["+record["id"]+"]")
            intro=[]
            if re.search(r"секрет|\bключ\w*\b|api[_ -]?key",request.question,re.I):
                intro.append("Сервис не раскрывает секреты и не исполняет команды на изменение правил магазина.")
            if re.search(r"леч|акне|аллерг|гарант",request.question,re.I):
                intro.append("Сервис не даёт лечебных гарантий и не назначает лечение. Для лечения обратитесь к врачу.")
            if calculation:
                intro.append(calculation_text(calculation))
            if catalog:
                intro.append("Проверка всего текущего каталога, без подтверждения наличия и будущих поставок: "+json.dumps(catalog,ensure_ascii=False))
            handoff=None;external=None
            if decision.status=="handoff_required":
                handoff=self.control.handoff(decision.reason,request_id)
                handoff["source_ids"]=[s.source_id for s in sources]
                intro.append(handoff["customer_message"])
            if decision.status=="requires_external_data":
                external={"system":"order_management","available":False,"action_performed":False,
                          "required_fields":["order_reference_via_secure_channel"]}
                intro.append("Нет доступа к реальным заказам. Проверка статуса, перечисление денег и оформление возврата не выполнены.")
            return result(decision.status,"\n\n".join(intro+paragraphs),sources=sources,calculation=calculation,catalog_result=catalog,
                          handoff=handoff,external_data=external,usage=usage,
                          diagnostics={"generation_performed":generation_performed,"answer_mode":"deterministic_calculator" if calculation else "deterministic_catalog" if catalog else "capability_control" if pre.status=="requires_external_data" else "validated_extractive",
                                       "llm_attempted":llm_attempted,
                                       "required_sections":sorted(context.required_sections),"context_bytes":context.bytes_used,
                                       "retrieved_sources":len(hits),"context_sources":len(context.records),
                                       "reranker_applied":retrieved.get("reranking",{}).get("applied",False),
                                       "score_is_probability":False,"reason":decision.reason})
        except SourceConflict as exc:
            handoff=self.control.handoff("conflicting_sources",request_id)
            handoff["source_ids"]=exc.source_ids
            return result("handoff_required","Обнаружено противоречие источников. Условия нельзя подтвердить до проверки сотрудником.",
                          handoff=handoff,diagnostics={"reason":"conflicting_sources"})
        except InsufficientContext as exc:
            user_fields=[f for f in exc.fields if not f.startswith(("context_","required_source_"))]
            status="clarification_needed" if user_fields else "insufficient_context"
            labels={"product_reference":"артикул или название товара: предыдущие сообщения не сохраняются", "pricing":"состав корзины или сумма товаров, способ доставки и условия применения скидок/бонусов",
                "pricing.items_or_subtotal_kopecks":"товары и количество либо сумма товаров","pricing.delivery":"город и способ доставки",
                "pricing.pickup_available":"есть ли доступный пункт выдачи","pricing.registered":"зарегистрирован ли покупатель",
                "pricing.first_order":"является ли заказ первым","pricing.bonus_balance":"доступный бонусный баланс",
                "catalog_query":"категория, бюджет и необходимые свойства товара","available_delivery_method":"доступный способ доставки",
                "promo_eligibility_not_satisfied":"возможность расчёта без недоступного промокода","registered_account_required_for_bonus":"регистрация для использования бонусов"}
            answer="Для ответа уточните: "+"; ".join(labels.get(f,"условия запроса") for f in exc.fields)+"."
            if status=="insufficient_context":answer="Не удалось собрать достаточно полный контекст. Уточните или сузьте вопрос."
            return result(status,answer,missing_fields=exc.fields)
        except ServiceError as exc:
            return result("system_error","Сервис временно не может подтвердить ответ.",http=exc.http_status,error_code=exc.code,
                          diagnostics={"llm_attempted":llm_attempted,"generation_performed":False})
        except Exception:
            return result("system_error","Сервис временно не может подтвердить ответ.",http=503,error_code="dependency_unavailable")
