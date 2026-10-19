# Границы компонентов

Source preparation реализован; остальные pipeline-интерфейсы — целевые контракты. В коде есть `PreparedBundle`, функции readers/prepare/export и минимальные `Chunk`, `Candidate`, `Answer`, Protocol для retriever/reranker/generator. Последние не заменяют model/Qdrant adapters.

JSONL boundary: `id` → будущий point_id; metadata.source → source_path, document_version → version. preparation_generation — локальное подготовленное поколение, не опубликованная Qdrant collection. Adapter Блока 2 должен явно преобразовать DTO и закрепить model/analyzer fingerprint. Сейчас embeddings и Qdrant publishing не вызываются.

| Компонент | Вход → выход | Ответственность / ошибка |
|---|---|---|
| Source audit (реализован) | allowlisted data directory → counts/hashes | UTF-8/JSON, товары, ID, policy sections; exit 2 при дефекте |
| Ingestion reader (реализован) | allowlisted data root → validated sources | bounded UTF-8, JSON/YAML, hashes, source versions |
| Chunker (реализован) | validated sources → целые semantic units | сохраняет условия, UUIDs, hashes; token count ещё не измерен |
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

`load_prepared`: pin CURRENT → verify hashes →20 source records. `Encoder`: signature/token_counts/encode. `embed`: model gate → normalized dense vectors + copied exact payload → generation/content SHA-256. `save_artifact`: immutable JSON cache. `DenseIndex.publish`: single writer → staging → verify → atomic alias. `DenseIndex.search`: pin physical generation → compare model signature → dense top-k → texts/metadata/product. Dense metadata содержит реальные token_count/tokenizer_id; source export сохраняется неизменным. Эти контракты реализованы в retrieval/, остальные query/API контракты выше остаются проектируемыми.

## Контракты Блока3

RussianBm25.signature/tokens/document/query задают единый versioned analyzer. build_hybrid принимает проверенный dense artifact, вычисляет corpus avg_len и sparse vectors, сохраняет dense/text/product без изменения. validate_hybrid проверяет outer hash, identity, analyzer, corpus mean и заново вычисляет sparse values. HybridIndex наследует generation publisher; full readback проверяет обе named vectors и IDF config. Три independent modes возвращают один generation/physical collection; BM25-only принимает encoder=None. Compare использует неизменные qrels, фиксирует все повторы/latency/перестановки; unstable ranks не скрываются усреднением. Legacy dense CLI и формат dense-v1 сохранены.
