# Границы компонентов

Source preparation, retrieval, reranking, API и controlled generation реализованы; текущие контракты описаны ниже. В коде есть `PreparedBundle`, функции readers/prepare/export и минимальные `Chunk`, `Candidate`, `Answer`, Protocol для retriever/reranker/generator. Последние не заменяют model/Qdrant adapters.

JSONL boundary: `id` → point_id; metadata.source → source_path, document_version → version. preparation_generation — локальное подготовленное поколение, не опубликованная Qdrant collection. Index adapters преобразуют DTO и закрепляют model/analyzer fingerprint. API читает опубликованный индекс без publishing.

| Компонент | Вход → выход | Ответственность / ошибка |
|---|---|---|
| Source audit (реализован) | allowlisted data directory → counts/hashes | UTF-8/JSON, товары, ID, policy sections; exit 2 при дефекте |
| Ingestion reader (реализован) | allowlisted data root → validated sources | bounded UTF-8, JSON/YAML, hashes, source versions |
| Chunker (реализован) | validated sources → целые semantic units | сохраняет условия, UUIDs, hashes; token gate выполняется model adapter |
| Local exporter (реализован) | PreparedBundle → immutable generation + CURRENT | writer lock, integrity check, atomic pointer; без сети |
| Dense encoder | texts + model revision → vectors | размерность/finite values; timeout или несовместимость — job failed |
| BM25 encoder | texts + analyzer fingerprint → sparse vectors | russian, одинаковая нормализация query/document, IDF в Qdrant |
| Index repository | generation + points → staging manifest | idempotent upsert; удаление через новое поколение; alias после проверки |
| Catalog repository | SKU/filters + generation → exact records | цены в копейках; не найдено отличается от ошибки чтения |
| Retrieval | query + pinned generation + limits → candidates | два независимых поиска, payload filter по версии, RRF |
| Reranker | query + candidates → reordered candidates | не добавляет sources; score только для ранжирования |
| Context assembler | candidates + related IDs + budget → context | дедупликация; версии согласованы; не обрезать исключения |
| Calculator | typed basket + eligibility → Decimal breakdown | PL-05; недостающие поля — clarification |
| Generator | question + evidence → draft answer | не выполняет платежи и не создаёт факты |
| Answer validator | draft + context/snapshot → validated answer | citation IDs входят в context; числа подтверждены |
| API | typed HTTP request → response/error | request_id, ограничения входа, deadlines, safe errors |
| Evaluation | versioned cases + traces → metrics | различает retrieval/calculation/generation errors |

Путь вне allowlist, невалидная версия или дубликат ID не пропускаются с warning. Подробные exception types, async-варианты и сериализация DTO уточняются при реализации соответствующего этапа; Protocol — синхронная доменная граница, API не должен блокировать event loop.

## Реализованные контракты Блока2

`load_prepared`: pin CURRENT → verify hashes →20 source records. `Encoder`: signature/token_counts/encode. `embed`: model gate → normalized dense vectors + copied exact payload → generation/content SHA-256. `save_artifact`: immutable JSON cache. `DenseIndex.publish`: single writer → staging → verify → atomic alias. `DenseIndex.search`: pin physical generation → compare model signature → dense top-k → texts/metadata/product. Dense metadata содержит реальные token_count/tokenizer_id; source export сохраняется неизменным. Эти контракты реализованы в retrieval/, актуальная API-граница уточнена ниже.

## Контракты Блока3

RussianBm25.signature/tokens/document/query задают единый versioned analyzer. build_hybrid принимает проверенный dense artifact, вычисляет corpus avg_len и sparse vectors, сохраняет dense/text/product без изменения. validate_hybrid проверяет outer hash, identity, analyzer, corpus mean и заново вычисляет sparse values. HybridIndex наследует generation publisher; full readback проверяет обе named vectors и IDF config. Три independent modes возвращают один generation/physical collection; BM25-only принимает encoder=None. Compare использует неизменные qrels, фиксирует все повторы/latency/перестановки; unstable ranks не скрываются усреднением. Legacy dense CLI и формат dense-v1 сохранены.

## Контракты Блока4

`PairScorer.signature/score(query,texts)` возвращает ровно один finite raw logit на каждый исходный текст. `MiniLMCrossEncoder` проверяет approved hashes до session creation и длину всей пары до inference. `RerankConfig` ограничивает final_k≤pool≤20 и pool≤prefetch≤100. `RerankedSearch.search` читает Hybrid pool один раз, сохраняет physical generation и точные payload fields, сортирует по logit со stable original-rank ties. Состояние `reranking.applied` отличает модельный порядок от disabled/fallback; `fallback_reason` содержит safe exception category. Original `score` остаётся RRF score, `rerank_score` добавляется отдельно. `mode=hybrid` описывает источник кандидатов; факт reranking находится в отдельном поле, не смешивается с distance metric.

`timing_ms.retrieval/rerank/total` относится к одному вызову. При cold CLI search сюда входит lazy model load внутри rerank; benchmark предварительно прогревает sessions и отдельно сохраняет startup. Reranker не меняет Qdrant payload/schema или embeddings и не получает qrels. `compare_reranked` применяет labels только после search, проверяет единое поколение и не выдаёт fallback за измеренное качество cross-encoder. Failure retrieval propagates; failure reranker возвращает полный исходный Hybrid top-k. Concurrency и native inference hard deadline не заявлены.

## API0.7

ChatRequest → ChatService → ChatResponse(6 status). RuntimeRetriever возвращает20 candidates одного physical generation. Snapshot проверяет тексты/metadata business1.1. Context сохраняет полные units и проверяет budget/coverage. Typed calculator/catalog независимы от LLM. Provider выбирает allowlisted evidence, сервер рендерит утверждения. AnswerControl проверяет errors/capabilities/coverage до отправки. Счётчики учитывают только отправленный исход, не late worker. Handoff1.0 pending,created=false. [API](api.md), [Answer Control](answer-control.md).
