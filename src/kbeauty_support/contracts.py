"""Typed boundaries for adapters; no retrieval or model implementation."""

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class Chunk:
    point_id: str
    section_id: str
    text: str
    source_path: str
    source_sha256: str
    version: str
    index_generation: str


@dataclass(frozen=True)
class Candidate:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Answer:
    status: str
    text: str
    source_ids: tuple[str, ...]


class Retriever(Protocol):
    def retrieve(self, question: str, limit: int, generation: str) -> Sequence[Candidate]: ...


class Reranker(Protocol):
    def rerank(self, question: str, candidates: Sequence[Candidate], limit: int) -> Sequence[Candidate]: ...


class Generator(Protocol):
    def generate(self, question: str, context: Sequence[Chunk]) -> Answer: ...
