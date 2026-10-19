# Roadmap и gates

| Этап | Поставка | Gate |
|---|---|---|
| Foundation (завершён) | аудит, CLI, контракты, инфраструктурная конфигурация | поведенческие unit tests; отчёт с ограничениями окружения |
| 1 — Data Ingestion, Chunking & Metadata (принят) | reader/chunker, manifests, dry-run CLI | детерминизм, исключения, обновление/удаление, path safety |
| 2 — Dense embeddings и Index publishing (реализован; на приёмке) | dense encoder, Qdrant adapter, alias; BM25 перенесён в3 | реальные Qdrant integration tests, повтор без дублей, сбой/rollback, persistence |
| 3 — Hybrid retrieval | dense/BM25 → RRF → reranking | русский analyzer suite, Recall@k/nDCG на размеченном корпусе, сравнение с dense-only |
| 4 — Answer API | FastAPI, calculator, context, LLM, citations | 12 сценариев; точные суммы T01–T06; границы T08/T10/T11/T12 |
| 5 — Operational hardening | CI, metrics, restore, security gates | воспроизводимый deploy на чистой машине, outages, load tests, dependency scan |

Блок1 принят. Блок2 реализован и проверен с настоящим Server; представлен на приёмку. Этапы3–5 не начаты; переход к3 требует отдельной приёмки владельца. Цель e2e: ≥11/12 полных pass и 100% критических ограничений; один критический отказ блокирует gate. Набор расширяется независимыми вопросами и перефразировками. Фактические latency/стоимость/надёжность появятся только после измерений; SLO не заявлены достигнутыми.
