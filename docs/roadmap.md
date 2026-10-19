# Roadmap и gates

| Этап | Поставка | Gate |
|---|---|---|
| Foundation (завершён) | аудит, CLI, контракты, инфраструктурная конфигурация | поведенческие unit tests; отчёт с ограничениями окружения |
| 1 — Data Ingestion, Chunking & Metadata (принят) | reader/chunker, manifests, dry-run CLI | детерминизм, исключения, обновление/удаление, path safety |
| 2 — Dense embeddings и Index publishing (принят) | dense encoder, Qdrant adapter, alias; BM25 перенесён в3 | реальные Qdrant integration tests, повтор без дублей, сбой/rollback, persistence |
| 3 — Hybrid retrieval (на приёмке) | dense/BM25 → RRF; reranking исключён | реальные три режима на Server, macro Recall@3/5, MRR@5, latency и query-level регрессии |
| 4 — Reranking и Answer API (после приёмки и уточнения scope) | FastAPI, calculator, context, LLM, citations | 12 сценариев; точные суммы T01–T06; границы T08/T10/T11/T12 |
| 5 — Operational hardening | CI, metrics, restore, security gates | воспроизводимый deploy на чистой машине, outages, load tests, dependency scan |

Блоки1–2 приняты. Блок3 реализован и представлен на приёмку. Reranking/LLM/API не начаты; следующий scope требует приёмки владельца. Последующие этапы ниже остаются проектируемыми. Цель e2e: ≥11/12 полных pass и 100% критических ограничений; один критический отказ блокирует gate. Набор расширяется независимыми вопросами и перефразировками. Фактические latency/стоимость/надёжность появятся только после измерений; SLO не заявлены достигнутыми.
