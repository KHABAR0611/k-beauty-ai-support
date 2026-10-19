# Hybrid Search & RRF — проверка0.5.0

Дата19.10.2026. Блок3 реализован и представлен на приёмку. Реальная интеграция Qdrant Server1.15.1 проверена. Бизнес-данные1.1 и все13 frozen query relevance sets сохранены; reranker, LLM и API не реализованы.

## Итог сравнения

Hybrid повысил полноту@5, но не победил по всем критериям: ранние позиции и семантическая перефразировка имеют регрессии. Это mixed outcome, а не универсальное улучшение. Все режимы остаются доступными, dense baseline не удалён.

| Mode | Recall@3 | Recall@5 | MRR@5 | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|
| bm25 | 0.688462 | 0.817949 | 0.884615 | 328.1 | 355.7 |
| dense | 0.734615 | 0.820513 | 0.961538 | 645.1 | 935.2 |
| hybrid | 0.726923 | 0.917949 | 0.903846 | 625.6 | 724.7 |

Основные параметры заданы до первого hybrid run: k1=1.2,b=0.75,avg_len=69.9, stemming on, prefetch20/20, равные ветви, native RRF1.15.1. Model BAAI/bge-m3 revision5617a9f61b028005a4858fdac845db406aefb181,1024d CLS+L2/Cosine, официальный FP32 ONNX CPU batch1/threads2. Sparse FastEmbed0.7.3, Snowball russian, asset revision22b8d2af71a76161e18dd432d2cee0eefa66e412. В primary collection20 points и40 named representations; это не40 разных документов.

## Baseline и протокол

Начальная рабочая версия960a6e1 содержала реализацию Блока2 на47c6256 и GitHub/CI настройки. Dense baseline измерен до изменений и заморожен commit896cbb0, план8669485. [Исходный baseline](block-3-dense-baseline.json) содержит relevant sources, top5 со scores,39 latency samples, модель и конфигурацию. Исходные Recall@3/5=0.734615/0.820513,MRR@5=0.961538,warm p50/p95=373.9/916.9ms. Текущий dense mode воспроизвёл все13 top5 IDs/scores и обе Recall метрики без изменений.

Query labels SHA-256:d7b1bbd56f943e1f9e56255b6a7fa822965ec8b480a38c6ec7a4660f848573cd. Recall@k — число уникальных relevant sections в top-k, делённое на общее число relevant sections данного query; затем macro mean по13 запросам. MRR@5 — mean обратного ранга первого relevant source в пределах5,0 если не найден. Для повторов сначала mean метрики по query, затем macro по queries. MRR не доказывает, что найдены остальные необходимые источники составного вопроса.

Latency:3 повтора×13 queries=39 samples на mode,1 warmup, без cache query vectors, порядок modes циклически меняется между повторами. Измеряется alias+descriptor/analyzer validation+query encode+Server query+payload, без CLI process startup, скачивания, проверки2.3GB файлов и model session startup. p50/p95 nearest-rank; per-query p95 по3 samples равен максимуму и является только наблюдением. Все режимы — та же physical collection/те же20 texts. Небольшой corpus, один старый CPU i5/8ГБ, нет isolation/load test; разницы latency не являются гарантией производительности или SLA.

После исправления final-score ties все13 ranking lists каждого mode совпали в трёх повторах. [Полный JSON](block-3-comparison.json) содержит каждый query, relevant sources, top5 IDs/scores, все повторения, latency и signatures.

## Каждый запрос

В ячейках: Recall@3 / Recall@5 / RR@5. Top5, relevant sets и latency каждого запроса доступны в JSON по тому же ID.

| Query | Dense | BM25 | Hybrid |
|---|---:|---:|---:|
| R01 | 0.500/1.000/1.000 | 1.000/1.000/1.000 | 0.500/1.000/1.000 |
| R02 | 0.200/0.200/1.000 | 0.600/0.800/1.000 | 0.600/0.600/1.000 |
| R03 | 0.500/0.667/1.000 | 0.500/0.667/1.000 | 0.500/0.667/1.000 |
| R04 | 0.500/0.500/1.000 | 0.500/0.667/1.000 | 0.500/0.667/1.000 |
| R05 | 0.600/0.800/1.000 | 0.600/1.000/1.000 | 0.600/1.000/1.000 |
| R06 | 0.750/1.000/1.000 | 0.750/1.000/1.000 | 0.750/1.000/1.000 |
| R07 | 1.000/1.000/0.500 | 0.500/0.500/0.500 | 1.000/1.000/0.500 |
| R08 | 1.000/1.000/1.000 | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| R09 | 1.000/1.000/1.000 | 0.500/1.000/1.000 | 1.000/1.000/1.000 |
| R10 | 0.500/0.500/1.000 | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| R12 | 1.000/1.000/1.000 | 1.000/1.000/1.000 | 1.000/1.000/1.000 |
| R13 | 1.000/1.000/1.000 | 0.000/0.000/0.000 | 0.000/1.000/0.250 |
| R14 | 1.000/1.000/1.000 | 1.000/1.000/1.000 | 1.000/1.000/1.000 |

Hybrid выиграл Recall@5 относительно dense для: R02, R04, R05, R10. По одному из ранних критериев или полноте проиграл: R13. Сводный прирост Recall@5 не скрывает эти регрессии.

## Составные вопросы и причины

- R02 (три SKU+ПВЗ): dense Recall@5=0.2, BM25=0.8, hybrid=0.6. BM25 поднимает KB-009/001/006 за счёт точных уникальных terms, dense находит доставку, fusion частично возвращает товары. Однако KB-006 и сборкаDR-01 остаются вне hybrid top5. В union20 они доступны: потеря связана с итоговым ранжированием/ограниченным top-k, а не отсутствием индекса. Query decomposition не внедрялась.
- R03 (SKU+WELCOME10+город+начисление): dense/hybrid Recall@5=4/6, BM25=4/6. Шесть обязательных sections не помещаются вtop5 даже теоретически. Разные режимы находят разные подмножества; высокий MRR не гарантирует корректного финансового ответа.
- R04 (два товара+списание+доставка): hybrid Recall@5=4/6 вместо3/6 dense; Recall@3 остаётся3/6. Exact SKU поднимают продукты, но PL-05 иDR-02 всё ещё отсутствуют вtop5, поэтому контекст финансового расчёта неполон.
- R05 (совмещение): hybrid восстанавливаетDR-02 вtop5 и достигает5/5; часть Recall@3 не улучшается. Это пример полезного объединения разных необходимых источников.
- R10 (оплата+трек): hybrid находитPL-01 иDR-03, dense толькоPL-01. Sparse literal terms про оплату/трек дополняют семантическую ветвь.
- R13 (разбитая баночка на третий день): dense DR-05 первым, BM25 вообще не находит его вtop5. Слова «день/срок» совпадают с начислением и хранением; «баночка разбита» не является словарным синонимом «повреждение флакона» для BM25. Hybrid опускаетDR-05 на4-е место: RR@5=0.25 и Recall@3=0 вместо1. Это явная регрессия, не скрытая успешным Recall@5.
- R14 (KB-005): BM25 находит единственный совпадающий SKU, dense/hybrid ставят его первым. Это проверенный пример, а не универсальный exact filter.

## Diagnostics без подмены primary результата

Stemming-off при той же UTF-8/stopword policy: BM25 Recall@3=0.688462,Recall@5=0.871795,MRR@5=0.884615. На этом маленьком наборе отказ от stemming улучшил@5: польза stemming не доказана этим benchmark. Он оставлен первичной заранее выбранной конфигурацией, а off — кандидат для независимой проверки, не автоматически продвинутый результат. [JSON](block-3-stemming-off.json).

Prefetch5: hybrid Recall@3=0.737179,Recall@5=0.917949,MRR@5=0.903846. Изменение глубины меняет вклад односторонних кандидатов и ограничивает union; меньшая глубина может улучшить известный вопрос и потерять нужный источник на другом. Это одиночный diagnostic run, не оптимизация по независимому holdout. [JSON](block-3-prefetch5.json).

## Надёжность и фактические тесты

- 132 unit/regression tests passed в новой чистой venv из43-package hybrid lock; pip check успешен. Сохраняются бизнес-регрессии1.1, source validation и dense contracts.
- 12 real Server integration tests passed,0 failed/skipped:7 новых hybrid+5 прежних dense. Три modes реально запрошены; BM25-only вызван без encoder. Независимая сумма1/(rank0+2) совпала с фактическими RRF scores Server.
- Проверены повторная публикация no-op, обе vectors и полные payload, analyzer mismatch, partial update после4 records, отказ readback до alias, update с настоящим re-embedding изменённого текста, пересчёт sparse/avg_len и исключение удалённого record из нового19-point поколения. Эти modified datasets изолированы в test aliases; business source files и product alias не переписывались.
- Alias переключён внутри encode query: query завершился на закреплённой прежней physical collection, без смешивания representations/generations.
- Docker Engine/Compose работают; Qdrant1.15.1 в собственном project kbeauty-review-check, loopback6394, persistent named volume. /readyz и/healthz200 послеrestart, оба вектора/payload/alias/top5 сохранились. Старые volumes/images/collections не удалялись. Ретенция старых generations не реализована.
- После накопления коллекций первый30s readiness deadline оказался недостаточен: восстановление по логам заняло около65s, OOMKilled=false. Deadline изменён на monotonic180s, затем весь suite прошёл. Сам query не получает незаявленную HA/retry-гарантию.
- [Имена и итог тестов](block-3-test-results.json), [пример двух представлений](../examples/hybrid-summary.json). Отдельная проверка CLI/clone фиксируется при передаче.

## Обнаруженные инженерные проблемы

1. FastEmbed0.7.3 default encoding ломает чтение UTF-8 stopwords на Windows; explicit UTF-8 subclass, asset hash/provenance/license и LF checkout устранили зависимость от locale.
2. Native punctuation splitting разделяетSKU: введена общая normalized формаkbNNN до tokenization. Морфология протестирована, но translation/transliteration/полная лемматизация отсутствуют.
3. Native RRF имеет hardcodedk2, неk60; independent Server test закрепляет формулу. Default score ties меняли порядок и иногда составtop5. Первый run сохранён [отдельно](block-3-initial-server-rrf.json). Итоговый tie-break применяется ко всему union до cutoff, без изменения score weights/labels.
4. Старые test collections замедлили recovery; вместо удаления данных исправлена временная предпосылка тестов и измерена readiness.
5. BM25 не исполняет price/fragrance predicates. Полнота поиска не даёт права обещать цены/итог/возврат без точных проверок. RRF не читает query/document заново, поэтому не исправляет смысловую ошибку sparse.

## Ограничения и приёмка

Функциональные критерии выполнены с реальным Server. По качеству подтверждено улучшение macro Recall@5 на этом наборе, но есть регрессии Recall@3/MRR иR13. Primary configuration не объявляется лучшей для всех запросов. Для выбора stemming/depth/дальнейшего reranker нужен независимый набор, а не ещё один подбор по13 известным вопросам.

Нет reranker, LLM, API, query decomposition, переводчика/синонимов, автоматического GC, backup restore, HA, нагрузки и security audit. Внутренние ties prefetch остаются поведением выбранной версии Server; проверенная воспроизводимость ограничена данным corpus/environment. Качество ответов LLM не измерялось. Следующий этап не начинается без приёмки владельца.

Все13 вопросов с relevant sources, top5 каждого режима и per-query latency: [таблицы](block-3-query-results.md).
