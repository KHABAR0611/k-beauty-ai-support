"""Whole evidence units from an approved business snapshot, with explicit budgets."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from kbeauty_support.ingestion.pipeline import prepare
from .errors import ServiceError, InsufficientContext

APPROVED_PREPARATION = "f62c8bbe398110d2010ca66d2a314cd692fbf43861317f1b38bc12157d22e223"
INJECTION = re.compile(r"ignore.{0,30}(instruction|previous)|system\s*prompt|api[_ -]?key|забудь.{0,30}(правил|инструкц)|игнорируй.{0,30}инструкц|секретн.{0,20}ключ",re.I)


class SourceConflict(Exception):
    def __init__(self, source_ids: list[str]):
        super().__init__("conflicting_sources")
        self.source_ids=source_ids


class Snapshot:
    def __init__(self, data_dir: Path):
        bundle=prepare(data_dir)
        if bundle.fingerprint != APPROVED_PREPARATION:
            raise ServiceError("business_snapshot_not_approved")
        self.generation=bundle.fingerprint
        self.records={c["id"]:c for c in bundle.chunks}
        self.sections={c["metadata"]["section"]:c for c in bundle.chunks}
        self.products={c["metadata"]["product_id"]:c for c in bundle.chunks if c.get("product")}

    def validate(self, hits: list[dict]) -> list[dict]:
        sections={}
        section_ids={}
        result={}
        for hit in hits:
            meta=hit.get("metadata",{})
            key=meta.get("section")
            if key in sections and sections[key] != hit.get("text"):
                raise SourceConflict(sorted({i for i in (section_ids[key],hit.get("id")) if i in self.records}))
            sections[key]=hit.get("text")
            section_ids[key]=hit.get("id")
            expected=self.records.get(hit.get("id"))
            if (expected is None or hit.get("text") != expected["text"]
                    or any(meta.get(k)!=expected["metadata"][k] for k in ("source","section","document_version","chunk_sha256","preparation_generation","source_sha256"))
                    or hit.get("product")!=expected.get("product") or hit.get("price_kopecks")!=expected.get("price_kopecks")):
                raise ServiceError("source_integrity_failure")
            if INJECTION.search(hit["text"]):
                raise ServiceError("unsafe_source_content")
            result[hit["id"]]=hit
        if set(result)!=set(self.records):
            raise ServiceError("incomplete_or_stale_index")
        return list(result.values())


@dataclass(frozen=True)
class Context:
    records: list[dict]
    evidence: dict[str,dict]
    required_sections: set[str]
    bytes_used: int


def required_sections(request) -> set[str]:
    q=request.question.casefold()
    sections=set(re.findall(r"\bKB-\d{3}\b",request.question.upper()))
    if request.pricing is not None or re.search(r"итог|заплачу|денег|рассчита|сколько.*бонус|бонус.*сколько",q):
        sections.update(["DR-01","DR-02","PL-02","PL-03","PL-04","PL-05"])
    if re.search(r"достав|курьер|пвз|сборк|сколько.*ждать",q):
        sections.update(["DR-01","DR-02"])
    if re.search(r"бонус|welcome10|промокод",q):
        sections.update(["PL-02","PL-03","PL-04","PL-05"])
    defect_query=re.sub(r"(?:брака|дефекта|повреждений)\s+нет|(?:без|нет)\s+(?:брака|дефектов|повреждений)","",q)
    if re.search(r"брак|поврежд|разбит|дефект|48 час",defect_query):
        sections.add("DR-05")
        if re.search(r"когда.*деньг|срок.*возврат",q):
            sections.add("DR-06")
    elif re.search(r"возврат|верну|верни|пломб|вскры",q):
        sections.update(["DR-04","DR-06"])
        if re.search(r"верни.*деньг|оформи.*возврат",q):
            sections.add("DR-05")
    if re.search(r"оплат|наличн|cvv|cvc|сбп|карт",q):
        sections.add("PL-01")
    if re.search(r"трек|статус|где.*заказ|отслед",q):
        sections.add("DR-03")
    if request.pricing and request.pricing.items:
        sections.update(p.product_id for p in request.pricing.items)
    if request.catalog_query:
        sections.update(f"KB-{n:03d}" for n in range(1,10))
    elif (not request.pricing and not any(s.startswith("KB-") for s in sections) and not sections.intersection({"DR-04","DR-05","DR-06"})
          and re.search(r"крем|тонер|сыворот|маск|бальзам|флюид|spf|ретинол|ингредиент|ниацинамид|han river|bomi lab",q)):
        sections.update(f"KB-{n:03d}" for n in range(1,10))
    return sections


def assemble(request, hits: list[dict], *, max_sources: int = 14, max_bytes: int = 24000) -> Context:
    required=required_sections(request)
    found={h["metadata"]["section"]:h for h in hits}
    if not required.issubset(found) or len(required)>max_sources:
        raise InsufficientContext(["required_source_coverage"])
    chosen=[h for h in hits if h["metadata"]["section"] in required]
    # No guessed universal score threshold: corpus sources are selected by explicit domain requirements.
    if not required:
        return Context([],{},set(),0)
    evidence={}
    for hit in chosen:
        # A complete section preserves negation, deadlines, thresholds and exceptions together.
        units=[hit["text"]]
        for unit in units:
            uid=hit["id"]+":"+hashlib.sha256(unit.encode()).hexdigest()[:16]
            evidence[uid]={"evidence_id":uid,"source_id":hit["id"],"section":hit["metadata"]["section"],"text":unit}
    size=len(json.dumps(list(evidence.values()),ensure_ascii=False).encode("utf8"))
    if size>max_bytes:
        raise InsufficientContext(["context_budget_exceeded"])
    return Context(chosen,evidence,required,size)
