"""Source recall on frozen labels; this does not evaluate generated answers."""
from __future__ import annotations

from .dense import RetrievalError


def recall(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not relevant or len(set(relevant)) != len(relevant):
        raise RetrievalError("Recall requires a nonempty unique relevance set")
    return len(set(retrieved[:k]) & set(relevant)) / len(relevant)


def evaluate(index, encoder, labels: dict) -> dict:
    rows = []
    generation = None
    for case in labels["queries"]:
        result = index.search(case["query"], encoder, limit=5)
        if generation is not None and generation != result["generation"]:
            raise RetrievalError("Published generation changed during evaluation; rerun")
        generation = result["generation"]
        sections = [hit["metadata"]["section"] for hit in result["hits"]]
        rows.append({**case, "retrieved": sections, "hits": result["hits"],
                     "recall_at_3": recall(sections, case["relevant"], 3),
                     "recall_at_5": recall(sections, case["relevant"], 5)})
    if not rows:
        raise RetrievalError("Evaluation set is empty")
    return {"generation": generation, "query_count": len(rows), "metric": "macro source recall",
            "recall_at_3": sum(r["recall_at_3"] for r in rows) / len(rows),
            "recall_at_5": sum(r["recall_at_5"] for r in rows) / len(rows),
            "ceiling_at_3": sum(min(3, len(r["relevant"])) / len(r["relevant"]) for r in rows) / len(rows),
            "ceiling_at_5": sum(min(5, len(r["relevant"])) / len(r["relevant"]) for r in rows) / len(rows),
            "results": rows}
