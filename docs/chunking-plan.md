# Structure-aware chunking v1

Реализовано в ingestion/sources.py и pipeline.py. Markdown делится по устойчивым заголовкам DR/PL; целый раздел, включая таблицы, исключения и ограничения, становится одним chunk. Заголовок документа и preamble повторяются для сохранения происхождения и общего контекста. Каталог: один товар = один logical document, с полным JSON product и price_kopecks вне retrieval text.

В текущем корпусе 11 policy chunks + 9 product chunks. Overlap=0: ни одно условие не отрывается от раздела. Фиксированная нарезка по символам отклонена, поскольку может отделить порог/исключение; LLM chunking не нужен и нарушил бы детерминизм. Автоматическое универсальное дробление длинных таблиц не реализовано: при >12 000 символов явный отказ, без truncation. Это safety limit, не измерение токенов.

UUIDv5: source path + document/catalog ID + section/product ID + schema_version + chunker_version. Source version не включена в ID, чтобы редактирование того же logical document обновляло запись; hashes и preparation generation отражают новый контент. Изменение схемы/chunker может создать новые IDs. UUID — корректный будущий Qdrant point ID, не произвольная строка DR-02.

Metadata: source, section, type, document_id, document_version, effective_date, language, data_origin, title, logical_id, parent_id, source_sha256, chunk_sha256, schema_version, chunker_version, preparation_generation, token_count=null, tokenizer_id=null. Product chunks дополнительно содержат product_id и exact product. Политики не получают product_id.

Нормализация текста — UTF-8/LF, trim только внешних границ; абзацы и таблицы не пересказываются. Source hashes — по байтам, chunk hashes — по нормализованному тексту. Каталог сортируется по ID для exports, Decimal сохраняется как JSON number без binary float; оригинальные optional fields остаются в snapshot. В document text видны только поля одного товара.

Manifest stage=source_preparation, status=validated означает успешную структурную проверку. embedding_ready=false до выбранного model tokenizer, проверки max length и закреплённых revisions в Блоке 2. Старые ориентиры 250–500 токенов не выдаются за выполненный замер; новый ADR-013 фиксирует эту границу.

DR-02, PL-02/03/04/05 потребуются совместно для расчётных запросов; DR-04/05 связаны с DR-06. Retrieval/context expansion остаются следующими этапами и не смешиваются с source chunking. Тесты и инженерная документация не входят в allowlist.
