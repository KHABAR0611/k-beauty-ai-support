# BM25: русский корпус и совместимость

База: FastEmbed 0.7.3, модель Qdrant/bm25, Qdrant server/client 1.15.1. Это клиентские sparse vectors, не server-side inference новых версий Qdrant. Конфигурация: language=russian, stemming включён, k=1.2, b=0.75, avg_len=256 как начальная гипотеза, sparse modifier=IDF. Не включать IDF повторно на клиенте.

Проверка исходников выбранного tag подтверждает russian в supported_languages, Snowball stemming, stopword-файл языка и разные document/query weights. Нормализация удаляет неалфавитно-цифровые символы, поэтому SKU с дефисом нельзя доверять только sparse path. [FastEmbed v0.7.3 source](https://github.com/qdrant/fastembed/blob/v0.7.3/fastembed/sparse/bm25.py).

Это проверка применимости дизайна, не измерение качества. Snowball — stemming, не полноценная лемматизация. Словоформы, ё/е, смешанные алфавиты, числа и пунктуация требуют отдельных тестов. Одинаковые параметры и stopword assets обязательны для ingestion/query; SHA-256 assets и analyzer config включаются в fingerprint. Изменение любого параметра требует переиндексации. avg_len в этой реализации задаётся параметром: измерить среднюю длину корпуса тем же analyzer и зафиксировать значение.

План обязательных тестов: «доставка/доставки/доставкой» → DR-01/02; «возврат/возврата/вернуть» → DR-04/05/06 с разметкой, без предположения идеальной эквивалентности; «бонусы/бонусами» → PL-03/04; WELCOME10 → PL-02; KB-004/KB004 → точная SKU-ветвь с документированной нормализацией; «без отдушки до 1800» → точные filters. Добавить негативные близкие слова, ё/е и регистр.

Сравнить stemming on/off на одинаковых размеченных запросах: Recall@20 и nDCG@10, затем end-to-end. Не утверждать улучшение до прогона. Сохранить токены, sparse indices и retrieved IDs без PII. Проверить реальные query_points/prefetch/Fusion.RRF и IDF на выбранном server; новые API из актуальной документации не переносить автоматически на старую базу. [Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/).
