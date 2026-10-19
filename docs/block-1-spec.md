# Block 1 — Data Ingestion, Chunking & Metadata

Статус: source preparation реализован в 0.3.0. Ниже — контракт поставки; фактические проверки и ограничения в validation-report.md.

## Цель и scope

Построить детерминированную подготовку источников к индексации: безопасное чтение → schema validation → semantic chunks → metadata → manifest/dry-run output. Полноценный API, LLM, hybrid query и модельные encoders не входят в этот блок. Интерфейсы writer/encoder подготовить для Block 2, не подменять работающими mock в пользовательском режиме.

## Вход

Только data/delivery_and_returns.md, data/payment_and_loyalty.md, data/products.json. Сохранить DR/PL IDs, 9 SKU, цены, пороги, сроки и порядок PL-05. CLI получает корень bundle и выходной каталог artifacts; файлы за пределами allowlist, symlinks, неверный UTF-8 и размеры >5 MiB отклонять. Ничего не сканировать рекурсивно по умолчанию.

## Контракты данных

1. Проверить metadata version/effective_date/language и согласованность bundle. Валидатор foundation покрывает только часть; расширить schema, а не считать её завершённой.
2. JSON: уникальные IDs, price >0 с точностью ≤2 знаков, currency=RUB, обязательные name/description/category/skin_types/fragrance_free. Boolean и строку в price отклонять. Опциональные характеристики сохранять без потерь.
3. Политики: корректный front matter, непустые уникальные разделы DR/PL; таблицы сохраняют шапки/пояснения. Ошибка останавливает job до записи индекса.

## Chunking

11 parent-разделов и 9 товарных записей до возможного дробления. Стратегия и metadata в `chunking-plan.md`. Для этого блока tokenizer не выбирается: целые semantic units экспортируются с token_count=null, stage=source_preparation, status=validated и embedding_ready=false. Выбор tokenizer, model revision и max length — обязательный gate Блока 2; source export не даёт разрешения на embedding/publish. ADR-013 заменяет прежнее требование измерения токенов до выбора модели.

Сохранить отдельные exact product snapshot и retrieval text. Никакой переинтерпретации LLM при подготовке цен. Политики нормализовать UTF-8/LF; source hash по исходным байтам. Не включать timestamps в content fingerprint.

## Manifest и повторные запуски

Выход: chunks.jsonl, catalog.snapshot.json, manifest.json, validation.json. Manifest включает schema/chunker revisions, source hashes, model/tokenizer IDs=null, analyzer_fingerprint=null, chunk count, content fingerprint, status=validated и embedding_ready=false; ошибки отражаются в CLI log и не публикуют active manifest. Файлы пишутся в staging directory, затем atomic rename публикует immutable generation; CURRENT переключается атомарно только на полный набор. Неизменный повтор проверяет hashes/байты и переиспользует поколение. Незавершённый staging не читается как валидный export.

Одинаковые входы/настройки дают одинаковые logical IDs, UUIDs и content hashes; повторный запуск не множит chunks. Изменённый раздел отражается в новом manifest; удалённый товар исчезает из snapshot и chunk set. Изменение schema/chunker/tokenizer/analyzer меняет fingerprint. Для Qdrant подготовить update plan, но само publish выполняется в Block 2 с generation/alias semantics.

## Ошибки и наблюдаемость

CLI: --data-dir, --output-dir, --dry-run; dry-run без записей и без сети. Exit 0 — valid; 2 — источник/конфигурация; 3 — ошибка записи/lock; Ctrl+C — interrupted. JSON event log с job_id, stage, counts, hashes и error codes, без содержимого секретов/текста клиентов. При disk full, частичном выводе или lock conflict не оставлять validated manifest.

## Обязательные автоматические проверки

- Два запуска на fixture дают одинаковые hashes и IDs, без дублей.
- Изменение DR-02 меняет нужный content hash, но не SKU и не бизнес-правила других разделов.
- Удаление товара не оставляет chunk/snapshot entry; дубликат ID и пустая секция отклоняются.
- Markdown-таблица DR-02, 48 часов DR-05, запрет совмещения PL-02 и порядок PL-05 сохранены целиком.
- Границы Unicode/параграфов; короткий раздел без лишнего overlap; превышение модели блокирует publish.
- Traversal, symlink, invalid UTF-8/JSON, bool/NaN/negative price, oversized file, несовпадающая версия → явный отказ.
- Read-only destination, interrupted job, lock contention и повтор после сбоя не повреждают предыдущий validated результат.

## Приёмка

Pytest pass на перечисленных сценариях, пример manifest и dry-run output в отчёте; никаких сетевых вызовов и LLM. 20 parent/source единиц accounted; index chunk count объясняется split mapping. Сборка выполняется на чистой Python 3.12 среде с pinned dependencies. Эталоны T01–T12 остаются отдельными от corpus; model/retrieval metrics откладываются на Block 3.
