"""Answer suitability is a separate policy boundary, never a score threshold."""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from threading import Lock
import re

STATUSES = ("answered", "clarification_needed", "insufficient_context", "requires_external_data", "handoff_required", "system_error")


class OutcomeMetrics:
    def __init__(self):
        self.counts=Counter({s:0 for s in STATUSES})
        self._lock=Lock()

    def record(self, status: str) -> None:
        if status in STATUSES:
            with self._lock:
                self.counts[status]+=1

    def metrics(self) -> dict:
        with self._lock:
            counts=dict(self.counts)
        total=sum(counts.values())
        return {"categories":counts,"category_shares":{s:n/total if total else 0 for s,n in counts.items()},
                "total":total,"scope":"process API responses; not resolved customer problems"}


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str


class AnswerControl:
    def decide(self, *, question: str, error: bool = False, conflict: bool = False, missing: bool = False,
               grounded: bool = False, enough: bool = True) -> Decision:
        if error:
            return Decision("system_error", "dependency_or_validation_error")
        if conflict:
            return Decision("handoff_required", "conflicting_sources")
        q=question.casefold()
        if re.search(r"оператор|переда[йт].*человек|свяжи.*человек|поговор.{0,20}(человек|сотрудник)|(?:хочу|нужен|нужна|позови|можно|соедини).{0,30}(?:человек|сотрудник)|оспарив|бонусы.*потрачен.*возврат",q):
            return Decision("handoff_required", "human_review_requested")
        from .intent import analyze
        if analyze(question).external:
            return Decision("requires_external_data", "order_system_unavailable")
        if missing:
            return Decision("clarification_needed", "missing_user_information")
        if not enough or not grounded:
            return Decision("insufficient_context", "unsupported_or_incomplete_evidence")
        return Decision("answered", "validated_evidence")

    @staticmethod
    def handoff(reason: str, request_id: str) -> dict:
        return {"contract_version":"1.0","reason":reason,"target_queue":"customer_support",
                "idempotency_key":request_id,"source_ids":[],"required_fields":["secure_contact","order_reference_if_relevant","consent"],
                "created":False,"external_action_performed":False,"customer_message":"Требуется проверка сотрудником. Обращение ещё не передано; операторская система не подключена."}
