# Roadmap и gates

| Этап | Состояние | Gate |
|---|---|---|
|1 — Data Ingestion/Chunking | Принят |20 chunks,9 товаров, бизнес1.1, детерминизм |
|2 — Dense/Qdrant | Принят |Server, поколения/alias, persistence, frozen qrels |
|3 — Hybrid/RRF | Принят |Три режима,13 queries, метрики и регрессии |
|4 — Optional reranking | Принят |Реальная модель/Server, ablations, fallback |
|5 — Generation/FastAPI/Answer Control | Реализован, на приёмке |197 unit,13 Server contracts,12 real-HTTP cases и2 adversarial |
|6 — System evaluation | Не начат; требуется приёмка5 |Независимый holdout, слепая оценка, load/deployment/security |

[Результаты5](block-5-results.md) различают10 answered и2 requires_external_data; это не customer-resolution rate. Live routes:8 deterministic tools,2 capability control,2 настоящая LLM. Corpus мал и синтетичен. Production-ready/SLA или общее качество свободной генерации не заявляются.
