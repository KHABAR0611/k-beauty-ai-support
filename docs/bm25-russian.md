# BM25: анализатор, русский корпус и ограничения

## Реализованная конфигурация

FastEmbed0.7.3 Qdrant/bm25, Qdrant client/server1.15.1. Sparse vectors вычисляются на клиенте; server-side model inference новых версий не используется. Точные настройки и runtime versions входят в sparse_model descriptor каждого point. Корпус — те же20 полных source texts, что и для dense, без query-specific boosts, скрытых expansions или подмешивания эталонов.

| Параметр | Значение и основание |
|---|---|
| k1 / b |1.2 /0.75, стандартные начальные значения FastEmbed, без подбора на13 вопросах |
| avg_len |69.9 токена после всего анализа; пересчитывается по новому corpus generation |
| Язык / stemming |russian / Snowball включён; диагностический off не меняет primary configuration |
| Stopwords |русский asset Qdrant/bm25 revision22b8d2af71a76161e18dd432d2cee0eefa66e412, UTF-8, SHA-2561743191192b4a4f77fcc216499455dc00c1b8626fdd407076a8deefff80e3d59 |
| Сохранённые частицы |не, нет, без — не удаляются как стоп-слова из-за смысловых ограничений бизнеса |
| Нормализация |Unicode NFKC → casefold → ё/е → KB-004/KB004/KB‑004/KB004 →kb004 |
| Токенизация |FastEmbed SimpleTokenizer, Unicode word tokens; пунктуация разделяет слова |
| Длина токена |≤40 символов, как в закреплённом adapter; не является chunk token limit |
| Hash |FastEmbed abs(MurmurHash3), int32-safe; проверка отсутствия collisions в текущем corpus vocabulary |
| IDF |Qdrant sparse modifier=idf; query weights1, document weights TF saturation/length normalization |

Формула: score(q,d)=сумма IDF(term) × tf(term,d)×(k1+1)/(tf(term,d)+k1×(1-b+b×len(d)/avg_len)). Query term repetitions не увеличивают query weights. IDF не умножается повторно на клиенте. Каждый physical generation имеет собственные corpus statistics; старые collections не влияют на новый IDF.

## Почему нужен adapter

Исходники FastEmbed0.7.3 открывают stopword file без encoding: на Windows default cp1251 и UTF-8 asset несовместимы. Узкий subclass явно читает UTF-8. Кроме того, native disable_stemmer отключает и stopwords; наш diagnostic stemming-off сохраняет ту же stopword policy, чтобы не смешивать два изменения. SKU до native punctuation splitting сводится к единому term; иначе KB-004 распадается на kb и004. Assets включены в package с Apache2.0 LICENSE и pinned provenance, не скачиваются скрытно во время поиска. LF закреплён через .gitattributes для проверяемого SHA на Windows clone.

## Проверки языка

Проверены одинаковые sparse terms для доставка/доставки/доставкой, бонусы/бонусами, ниацинамид/ниацинамидом, керамиды/керамидами; регистр Jeju Cloud и WELCOME10; ё/е; формы SKU с дефисом, без него и с Unicode-дефисом. KB-004 и KB-005 остаются разными. Поля name/ingredients и Latin brands сохраняются в source text; структура и точная цена остаются в payload.

Stemming не является полноценной лемматизацией: возврат и вернуть не обязаны совпадать. Нет перевода ниацинамид↔niacinamide или транслитерации Jeju↔Джеджу. Синонимы и межъязыковая эквивалентность остаются ограничениями sparse retrieval. Snowball может объединять близкие словоформы чрезмерно. Наличие слов «без» и «отдушка» не заменяет точный fragrance_free filter; число1800 не задаёт price predicate. Retrieval выдаёт кандидатов, а не доказательство бюджетного соответствия или излечения.

## RRF и точность сравнения

Qdrant1.15.1 предоставляет named sparse vectors, IDF modifier и FusionQuery/RRF с prefetch. В этой версии константа RRF=2 для нулевого rank: сумма1/(rank0+2). Параметры configurable/weighted RRF новых версий не используются. Fusion видит позиции документов, не складывает cosine и BM25 scores. Отсутствующий в ветви документ не получает её вклад.

При равных итоговых scores native RRF не гарантирует порядок. Приложение запрашивает полный union кандидатов двух prefetch и сортирует равные scores по UUID перед top-k; это не learned reranking. Внутренний порядок branch ties остаётся поведением выбранного Server и отдельно проверяется на данном корпусе; не заявляется универсальный порядок на всех версиях/корпусах. Prefetch20 охватывает весь текущий20-point corpus; для большого корпуса глубина требует независимого benchmark.

Полные результаты, stemming-off и prefetch5 diagnostic, включая регрессии: [Блок3](block-3-results.md). Диагностические конфигурации не подменяют primary результат. Источники: [FastEmbed0.7.3](https://github.com/qdrant/fastembed/blob/v0.7.3/fastembed/sparse/bm25.py), [RRF Qdrant1.15.1](https://github.com/qdrant/qdrant/blob/v1.15.1/lib/segment/src/common/reciprocal_rank_fusion.rs).
