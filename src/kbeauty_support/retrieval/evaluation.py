"""Source recall on frozen labels; this does not evaluate generated answers."""
from __future__ import annotations

from .dense import RetrievalError
import math
import statistics
import time


def recall(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not relevant or len(set(relevant)) != len(relevant):
        raise RetrievalError("Recall requires a nonempty unique relevance set")
    return len(set(retrieved[:k]) & set(relevant)) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    if not relevant:
        raise RetrievalError("MRR requires relevant sources")
    return next((1 / rank for rank, section in enumerate(retrieved[:k], 1) if section in relevant), 0.0)


def percentile(values: list[float], p: float) -> float:
    if not values or not 0 < p <= 100:
        raise RetrievalError("Invalid percentile input")
    return sorted(values)[math.ceil(len(values) * p / 100) - 1]


def compare(index, encoder, labels: dict, *, repetitions: int = 3, prefetch: int = 20,
            modes: tuple[str, ...] = ("dense", "bm25", "hybrid")) -> dict:
    if repetitions < 1 or not labels["queries"]:
        raise RetrievalError("Empty experiment")
    rows = {mode: {case["id"]: {**case, "latency_ms": []} for case in labels["queries"]} for mode in modes}
    generation = None
    for repetition in range(repetitions):
        order = modes[repetition % len(modes):] + modes[:repetition % len(modes)]
        for case in labels["queries"]:
            for mode in order:
                start = time.perf_counter()
                result = index.search(case["query"], encoder, mode=mode, limit=5, prefetch=prefetch)
                elapsed = (time.perf_counter() - start) * 1000
                if generation is not None and result["generation"] != generation:
                    raise RetrievalError("Generation changed during comparison")
                generation = result["generation"]
                row = rows[mode][case["id"]]
                sections = [h["metadata"]["section"] for h in result["hits"]]
                if "retrieved_repetitions" not in row:
                    row["retrieved_repetitions"] = []
                row["retrieved_repetitions"].append(sections)
                row["latency_ms"].append(elapsed)
                row["top5"] = [{"id": h["id"], "section": h["metadata"]["section"], "source": h["metadata"]["source"], "score": h["score"]} for h in result["hits"]]
    summaries = {}
    for mode, cases in rows.items():
        data = []
        for row in cases.values():
            rank_lists = row["retrieved_repetitions"]
            row["recall_at_3"] = statistics.mean(recall(r, row["relevant"], 3) for r in rank_lists)
            row["recall_at_5"] = statistics.mean(recall(r, row["relevant"], 5) for r in rank_lists)
            row["rr_at_5"] = statistics.mean(reciprocal_rank(r, row["relevant"]) for r in rank_lists)
            row["rankings_stable"] = all(r == rank_lists[0] for r in rank_lists)
            row["latency_p50_ms"] = percentile(row["latency_ms"], 50)
            row["latency_p95_ms"] = percentile(row["latency_ms"], 95)
            data.append(row)
        timings = [ms for row in data for ms in row["latency_ms"]]
        summaries[mode] = {"recall_at_3": statistics.mean(r["recall_at_3"] for r in data),
                           "recall_at_5": statistics.mean(r["recall_at_5"] for r in data),
                           "mrr_at_5": statistics.mean(r["rr_at_5"] for r in data),
                           "p50_ms": percentile(timings, 50), "p95_ms": percentile(timings, 95),
                           "latency_samples": len(timings), "results": data}
    return {"generation": generation, "prefetch": prefetch, "repetitions": repetitions, "modes": summaries}


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
