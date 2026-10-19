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
