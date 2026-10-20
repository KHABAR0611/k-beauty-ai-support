"""Strict public request/response and provider evidence-selection contracts."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BasketItem(StrictModel):
    product_id: str = Field(pattern=r"^KB-\d{3}$")
    quantity: StrictInt = Field(ge=1, le=100)


class PricingInput(StrictModel):
    items: list[BasketItem] | None = Field(default=None, min_length=1, max_length=9)
    subtotal_kopecks: StrictInt | None = Field(default=None, ge=1, le=100_000_000)
    delivery: Literal["pickup", "moscow_courier", "spb_courier"] | None = None
    pickup_available: StrictBool | None = None
    registered: StrictBool | None = None
    first_order: StrictBool | None = None
    promo_code: Literal["WELCOME10"] | None = None
    bonus_balance: StrictInt | None = Field(default=None, ge=0, le=1_000_000)
    bonus_requested: StrictInt | Literal["maximum"] | None = None
    compare_options: StrictBool = False

    @model_validator(mode="after")
    def valid_basket(self):
        if self.items is not None and self.subtotal_kopecks is not None:
            raise ValueError("Choose catalog items or declared subtotal")
        if self.items and len({p.product_id for p in self.items}) != len(self.items):
            raise ValueError("Duplicate product IDs")
        if isinstance(self.bonus_requested, int) and not 0 <= self.bonus_requested <= 1_000_000:
            raise ValueError("Invalid bonus amount")
        return self


class CatalogQuery(StrictModel):
    category: str | None = Field(default=None, max_length=80)
    skin_type: str | None = Field(default=None, max_length=80)
    fragrance_free: StrictBool | None = None
    max_price_kopecks: StrictInt | None = Field(default=None, ge=1, le=100_000_000)
    ingredient: str | None = Field(default=None, min_length=1, max_length=80)


class ChatRequest(StrictModel):
    question: str = Field(min_length=1, max_length=4000)
    pricing: PricingInput | None = None
    catalog_query: CatalogQuery | None = None

    @model_validator(mode="after")
    def nonblank(self):
        if not self.question.strip():
            raise ValueError("Empty question")
        return self


class Selection(StrictModel):
    source_id: str = Field(min_length=1, max_length=80)
    evidence_id: str = Field(min_length=1, max_length=100)


class ProviderDraft(StrictModel):
    abstain: StrictBool
    selections: list[Selection] = Field(max_length=24)


class Source(StrictModel):
    source_id: str
    source: str
    section: str
    document_version: str
    product_id: str | None = None
    usage: Literal["quoted", "calculation", "catalog_verification"]


class ChatResponse(StrictModel):
    answer: str
    sources: list[Source]
    status: Literal["answered", "clarification_needed", "insufficient_context", "requires_external_data", "handoff_required", "system_error"]
    grounding_status: Literal["confirmed", "insufficient_context", "error"]
    request_id: str
    latency_ms: dict[str, float]
    index_generation: str | None = None
    calculation: dict | None = None
    catalog_result: dict | None = None
    missing_fields: list[str] = Field(default_factory=list)
    error_code: str | None = None
    usage: dict | None = None
    diagnostics: dict = Field(default_factory=dict)
    handoff: dict | None = None
    external_data: dict | None = None
