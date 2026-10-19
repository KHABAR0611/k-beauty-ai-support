"""Explicit source-ranking experiments. Labels are consumed only after search."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import statistics
import time

from .dense import RetrievalError
from .evaluation import percentile, recall, reciprocal_rank
from .rerank import RerankConfig, RerankedSearch


def process_memory() -> dict:
    """Current-process working set; never label it as whole-machine or model RAM."""
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

        api = ctypes.WinDLL("psapi", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        api.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        value = Counters()
        value.cb = ctypes.sizeof(value)
        if not api.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(value), value.cb):
            raise OSError(ctypes.get_last_error(), "Process memory measurement failed")
        return {"working_set_bytes": value.WorkingSetSize, "peak_working_set_bytes": value.PeakWorkingSetSize,
                "private_commit_bytes": value.PagefileUsage, "method": "Windows GetProcessMemoryInfo"}
    status = Path("/proc/self/status")
    if status.exists():
        values = {line.split(":")[0]: line.split(":")[1].strip() for line in status.read_text().splitlines() if ":" in line}
        return {"working_set_bytes": int(values["VmRSS"].split()[0])*1024,
                "peak_working_set_bytes": int(values["VmHWM"].split()[0])*1024, "method": "Linux proc status"}
    return {"method": "unavailable"}


def compare_reranked(index, encoder, scorer, labels: dict, *, pools: tuple[int, ...] = (5, 10, 15),
                     repetitions: int = 3, prefetch: int = 20) -> dict:
    if (isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1 or not labels.get("queries")
            or not pools or len(set(pools)) != len(pools)):
        raise RetrievalError("Invalid reranking experiment")
    searches = {f"rerank_pool_{pool}": RerankedSearch(index, encoder, lambda: scorer, RerankConfig(pool, 5, prefetch)) for pool in pools}
    modes = ("dense", "hybrid", *searches)
    rows = {mode: {case["id"]: {**case, "samples": []} for case in labels["queries"]} for mode in modes}
    if any(len(cases) != len(labels["queries"]) for cases in rows.values()):
        raise RetrievalError("Duplicate evaluation query IDs")
    generation = None
    memory = {"before_requests": process_memory()}
    for repetition in range(repetitions):
        order = modes[repetition % len(modes):] + modes[:repetition % len(modes)]
        for case in labels["queries"]:
            for mode in order:
                started = time.perf_counter()
                if mode in searches:
                    result = searches[mode].search(case["query"])
                    if not result["reranking"]["applied"]:
                        raise RetrievalError("Experiment reranker fell back; do not count fallback as model quality")
                    timing = result["timing_ms"]
                else:
                    result = index.search(case["query"], encoder, mode=mode, limit=5, prefetch=prefetch)
                    elapsed = (time.perf_counter()-started)*1000
                    timing = {"retrieval": elapsed, "rerank": 0.0, "total": elapsed}
                if generation is not None and generation != result["generation"]:
                    raise RetrievalError("Index generation changed during experiment")
                generation = result["generation"]
                row = rows[mode][case["id"]]
                row["samples"].append({"timing_ms": timing, "sections": [h["metadata"]["section"] for h in result["hits"]],
                                       "memory": process_memory()})
                row["top5"] = [{k: v for k, v in h.items() if k != "text"} for h in result["hits"]]
                row["positions"] = result.get("reranking", {}).get("positions", [])
    memory["after_requests"] = process_memory()
    summaries = {}
    for mode, cases in rows.items():
        data = list(cases.values())
        for row in data:
            rankings = [s["sections"] for s in row["samples"]]
            row["recall_at_3"] = statistics.mean(recall(r, row["relevant"], 3) for r in rankings)
            row["recall_at_5"] = statistics.mean(recall(r, row["relevant"], 5) for r in rankings)
            row["rr_at_5"] = statistics.mean(reciprocal_rank(r, row["relevant"]) for r in rankings)
            row["rankings_stable"] = all(r == rankings[0] for r in rankings)
        summary = {key: statistics.mean(row[key] for row in data) for key in ("recall_at_3", "recall_at_5", "rr_at_5")}
        summary["mrr_at_5"] = summary.pop("rr_at_5")
        samples = [s for row in data for s in row["samples"]]
        summary["latency"] = {stage: {f"p{p}_ms": percentile([s["timing_ms"][stage] for s in samples], p) for p in (50, 95)}
                               for stage in ("retrieval", "rerank", "total")}
        summary.update(latency_samples=len(samples), results=data)
        summaries[mode] = summary
    return {"generation": generation, "repetitions": repetitions, "prefetch": prefetch, "pools": list(pools),
            "modes": summaries, "memory": memory}
