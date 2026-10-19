# Блок 4: Reranking & Retrieval Optimization

Pipeline: query → BGE-M3 + BM25 → Qdrant RRF → pool → MiniLM cross-encoder → final top5.

Исходный commit fe1676c, business1.1, 20 points, 11 политик и 9 товаров. Checkpoints, правила, qrels и результаты Блока3 не изменены. Новые holdout/план зафиксированы a82a9ee до inference. [Выбор модели](reranker-model-selection.md), [план](block-4-experiment-plan.json), [архитектура](rag-architecture.md), ADR023–025.

## Результаты на исходных 13 запросах

| Режим | Recall@3 | Recall@5 | MRR@5 | Total p50/p95, мс | Retrieval p50/p95, мс | Rerank p50/p95, мс |
|---|---:|---:|---:|---:|---:|---:|
| dense | 73.46% | 82.05% | 96.15% | 686.8 / 1158.7 | 686.8 / 1158.7 | 0.0 / 0.0 |
| hybrid | 72.69% | 91.79% | 90.38% | 653.3 / 936.3 | 653.3 / 936.3 | 0.0 / 0.0 |
| rerank_pool_10 | 75.00% | 87.69% | 94.87% | 3178.8 / 3997.4 | 659.3 / 852.5 | 2517.4 / 3130.0 |
| rerank_pool_15 | 75.00% | 87.69% | 94.87% | 4357.5 / 5072.3 | 664.9 / 862.9 | 3639.6 / 4322.3 |
| rerank_pool_5 | 80.38% | 91.79% | 94.87% | 1980.4 / 2493.8 | 678.1 / 885.1 | 1276.4 / 1608.7 |

Primary конфигурация — pool10, final5, prefetch20, CPU2 threads, batch1, raw logits, FP32; pool5/15 являются диагностикой, не подбором по holdout. Каждый режим — 39 измерений, три повтора с циклической перестановкой порядка. Macro recall = среднее доли уникальных relevant sections в top-k; MRR5 = среднее обратного ранга первого relevant section в top5. Percentile nearest-rank. Для вопросов с шестью источниками ceiling@5=5/6; reranker не решает ограничение длины контекста.

Сохранённый baseline Блока3: Dense .734615/.820513/.961538, Hybrid .726923/.917949/.903846 (Recall3/Recall5/MRR5). Новые измерения latency относятся к текущему desktop CPU-сеансу; старые времена не заменяются. Запросы без query/score cache; warm sessions. Скачивание, SHA gate, session startup и warmup не входят в query timing и опубликованы отдельно в JSON. Сумма отдельных p50/p95 не обязана равняться квантилю total.

## Решение по качеству

Primary pool10 **не рекомендуется вместо Hybrid**: рост Recall3/MRR сопровождается снижением Recall5 на4,10 п.п. и примерно пятикратной warm задержкой. На holdout полнота и MRR уже достигают ceiling у Hybrid; reranker не даёт прироста. Приемлемость latency не подтверждена продуктовым SLO, конкурентная нагрузка не проверена. Функциональная интеграция выполнена; quality gate для включения primary10 как стандартного режима не пройден.

Pool5 — перспективная диагностика: Recall3 80,38% вместо72,69%, MRR94,87% вместо90,38%, Recall5 остаётся91,79%. При final5 он только переставляет исходные пять документов, поэтому не может улучшить или ухудшить их membership/Recall5. Его p50 около1,98s против0,65s Hybrid. Независимой проверки pool5 нет; он не подменяет preregistered pool10 задним числом. Pool15 повторяет качество pool10 с большей ценой и не обоснован для текущих данных. Следующий опыт — заранее зафиксированная проверка pool5 на новом holdout либо другая модель с отдельным ресурсным бюджетом; текущий рекомендуемый режим сохраняется Hybrid.

## R13 и составные вопросы

R13: DR-05 перемещён RRF4→reranker3 при каждом pool; Recall3 0→1, RR5 .25→.3333. Dense раньше ставил его первым. DR-06 и DR-03 остаются выше: полное исправление перефразировки не достигнуто. Вероятная причина — общая временная/возвратная лексика конкурирующих разделов, а не уверенное различение повреждения и сроков; это объяснение по результатам, не доказательство внутренней логики нейросети.

R01 при pool10 теряет DR-01 (сборку): Recall5 1→.5. R05 теряет DR-02 (доставку): 1→.8. R04 получает DR-02: .6667→.8333. R03 сохраняет4/6 источников, но вместо доставки DR-02 появляется крем KB-004: агрегированная полнота скрывает смену отсутствующих условий. R07 нужный DR-04 становится первым вместо DR-05, улучшая RR5 .5→1. Точный SKU R14/KB-005 остаётся первым. Cross-encoder оценивает каждый документ независимо; его цель не гарантирует покрытие всех подзадач финансового вопроса. Увеличение pool добавляет конкурирующие тематически похожие политики; RRF weight/labels и бизнес-данные не менялись ради этих случаев.

## Независимый holdout: 10 запросов

| Режим | Recall@3 | Recall@5 | MRR@5 | Total p50/p95, мс | Retrieval p50/p95, мс | Rerank p50/p95, мс |
|---|---:|---:|---:|---:|---:|---:|
| dense | 100.00% | 100.00% | 95.00% | 599.0 / 962.1 | 599.0 / 962.1 | 0.0 / 0.0 |
| hybrid | 100.00% | 100.00% | 100.00% | 579.6 / 680.2 | 579.6 / 680.2 | 0.0 / 0.0 |
| rerank_pool_10 | 100.00% | 100.00% | 100.00% | 2875.7 / 3330.8 | 583.1 / 730.9 | 2304.6 / 2690.8 |

Holdout размечен вручную до первого inference, не использован для выбора модели, boosts или размера pool. Проверен только заранее выбранный pool10. Это небольшой дополнительный набор того же каталога, а не независимая бизнес-выборка; статистическая значимость улучшения не доказана. [Все raw traces](block-4-holdout.json).

## Память и воспроизводимость

13 запросов: warmup dense 60.3s, reranker (hash gate + session + warmup) 20.9s.

- before_model_sessions: working set 365.8 MiB; process peak 365.8 MiB; private commit 448.7 MiB.
- both_warmed: working set 1415.0 MiB; process peak 2422.5 MiB; private commit 2336.2 MiB.
- dense_warmed: working set 1536.4 MiB; process peak 1550.2 MiB; private commit 1617.9 MiB.
- После запросов: {"method": "Windows GetProcessMemoryInfo", "peak_working_set_bytes": 2540138496, "private_commit_bytes": 2458394624, "working_set_bytes": 2075459584}

holdout: warmup dense 14.3s, reranker (hash gate + session + warmup) 15.1s.

- before_model_sessions: working set 364.5 MiB; process peak 364.5 MiB; private commit 447.2 MiB.
- both_warmed: working set 2034.4 MiB; process peak 2510.5 MiB; private commit 2336.6 MiB.
- dense_warmed: working set 1535.6 MiB; process peak 1549.6 MiB; private commit 1617.4 MiB.
- После запросов: {"method": "Windows GetProcessMemoryInfo", "peak_working_set_bytes": 2632482816, "private_commit_bytes": 2456436736, "working_set_bytes": 2216140800}

Working set — наблюдаемая память всего Python-процесса, не только weights; peak кумулятивен и включает загрузку. Разность milestones — наблюдаемая стоимость добавления reranker в данном процессе, не точная изолированная память модели. Docker/ОС/браузер не входят в process RSS. GPU не использовался. Все request samples содержат memory snapshot; отсутствуют нагрузочные и конкурентные измерения.

## Покрытие, ошибки и ограничения

Fallback атомарно сохраняет Hybrid top-k при ошибке загрузки/инференса, длинной паре или невалидных scores. Disabled mode модель не загружает. Ошибка Qdrant не маскируется. Результат сохраняет source/product/price и original RRF score; rerank_score — отдельный raw logit, не вероятность. Журнал positions показывает ID и before/after без пользовательского текста.

Нет LLM, API, hard timeout для native inference, HA, load test, backup restore и полноценного security/dependency scan. Hash manifest подтверждает целостность выбранных файлов, не безопасность всех зависимостей. Длинные новые документы потребуют другой стратегии при превышении pair512; сейчас truncation запрещена. Точный SKU и multi-source completeness требуют отдельного контроля: улучшение MRR не гарантирует полноту.

[Результаты каждого запроса](block-4-query-results.md), [raw development](block-4-development.json), [проверки](block-4-test-results.json). Блок5 не реализован и требует отдельной приёмки.
