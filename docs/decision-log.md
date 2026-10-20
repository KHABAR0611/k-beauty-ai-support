# Architecture Decision Records

Дата: 19.10.2026. Записи фиксируют эволюцию дизайна; публичная Git-история начинается с текущей поставки. Статус «принято» означает утверждённый дизайн; завершённые компоненты отмечены отдельно.

## ADR-001 — Superseded: способ реализации

Исходное решение о внешней платформе оркестрации заменено ADR-008 по изменившимся требованиям. История не переписана; старые ограничения «без Python» больше не действуют.

## ADR-002 — Accepted: политики и каталог раздельно

Markdown — правила, JSON — точные товарные поля. Альтернатива: общий индекс без точного snapshot. Выбрано разделение, поскольку similarity не гарантирует цену и фильтр. Последствие: query связывает оба источника одной генерацией.

## ADR-003 — Accepted in 0.3.0: смысловые chunks

11 целых parent-разделов и 9 товаров реализованы, их полнота проверена. Альтернатива — фиксированные интервалы. Модельные размеры и глубины поиска требуют экспериментов; старое k=5 заменено конфигурацией нескольких стадий. Tokenizer gate уточнён ADR-013, retrieval остаётся будущим этапом.

## ADR-004 — Superseded by ADR-016: денежные правила 1.0

В исходном наборе 1.0 были выбраны PL-05 и DR-02: порог после промокода до бонусов, списание несовместимо с WELCOME10, начисление на денежную часть товаров. Реализация расчёта — Decimal, не LLM. Альтернатива расчёта порога после бонусов отклонена как изменение утверждённых правил.

## ADR-005 — Accepted: изоляция источников

Индексируются только три allowlisted файла `data/`. Тесты и инженерная документация не входят в corpus. Последствие: нет утечки эталонов в retrieval.

## ADR-006 — Accepted: справочные операции

Нет CRM, платежей, реальных возвратов и отслеживания. Подключение write-инструментов требует отдельного ADR, авторизации и тестового контура.

## ADR-007 — Partially superseded: платформа и модели

Платформа закреплена ADR-008. Dense-модель уточнена ADR-017; reranker и LLM пока открыты: оценить русский корпус, стоимость, latency, лицензии; зафиксировать revisions до публикации индекса.

## ADR-008 — Accepted: Python / FastAPI / Qdrant

Контекст: утверждён backend с контролем индекса и диагностики. Qdrant выбран окончательно, альтернативное хранилище не рассматривается. Два независимых pipeline; Qdrant хранит dense+sparse vectors, API не публикует индекс. Последствие: больше ответственности за эксплуатацию, но проверяемые контракты и воспроизводимость.

## ADR-009 — Accepted: BM25 → RRF → reranking

FastEmbed 0.7.3 Qdrant/bm25 с russian; Qdrant server/client 1.15.1, sparse IDF modifier. RRF работает с рангами, reranker отдельно с query/document. Альтернатива складывать сырые dense/BM25 scores отклонена из-за разных шкал. Языковая поддержка в коде не доказывает качество поиска: `bm25-russian.md` определяет тесты.

## ADR-010 — Accepted: поколения индекса

Manifest fingerprint, staging collection, проверка целостности, atomic alias switch. Повторный тот же manifest — no-op; изменение/удаление источников отражается новым поколением. Альтернатива inplace upsert сложнее для удаления и rollback. Последствие: временно требуется место на два поколения, один publisher и retention.

## ADR-011 — Accepted: локальные материалы вне поставки

В Git и Docker build context не включаются личные заметки. Архитектурные решения для сопровождения остаются в `docs/`. Историю прежних коммитов не переписывать.

## ADR-012 — Accepted: поэтапная реализация

Текущий этап ограничен foundation. API, embeddings, retrieval и LLM не симулируются. Поведенческие тесты валидатора и эталонов не являются доказательством RAG-качества. Каждая следующая поставка имеет проверяемый gate в roadmap.


## ADR-013 — Accepted: source preparation до выбора tokenizer

Контекст: модель embeddings ещё не выбрана, текущий корпус мал и содержит значимые исключения. Решение: целые Markdown-разделы и отдельные товарные документы, без overlap/LLM chunking. 12 000 символов — только safety bound; при превышении fail, без скрытой обрезки. Export status=validated подтверждает schema validation, embedding_ready=false сохраняет обязательный tokenizer gate Блока 2. Альтернатива выбрать произвольную модель ради токенизации отклонена как преждевременное решение.

## ADR-014 — Accepted: immutable local export generations

Четыре детерминированных файла, content fingerprint, UUIDv5 logical IDs, source byte hashes. Staging directory → atomic rename → atomic CURRENT. O_EXCL writer lock, явный отказ на lock contention, сохранение прошлой генерации при сбое. Альтернатива пофайлового обновления в корне отклонена: читатель может смешать поколения. Hash verification защищает повтор от повреждённого export. Не гарантируется восстановление после hardware power loss; directory fsync portability и backup — отдельная проверка.

## ADR-015 — Accepted: чистая публичная история и один active repository

Публичный checkout начинается новым root commit из актуальных исходников; прежняя история не импортируется. Архив сохраняется без изменений. После передачи весь код ведётся только в новом checkout, личные знания — вне него. Нельзя push неизвестного URL или force push. Содержимое первого коммита проверяется до передачи.


## ADR-016 — Accepted: бизнес-база 1.1 по уточнению владельца

При приёмке 19.10.2026 владелец указал исходные требования: доставка после промокода и бонусов, совмещение WELCOME10 разрешено, KB-004=1890 и KB-005=1590. Отдельным ответом подтверждена база cap20% после промокода. В Git прежние значения существовали уже в первом доступном commit, поэтому поздняя смена в Блоке1 не доказана; история не переписывается. Версия всех трёх источников повышена до1.1. Обновлены T03/T05/T06/T09, все12 expected records, regression pins и примеры. Детерминизм ingestion не является свидетельством верности бизнес-требований; основание решения — owner clarification, не pass rate. Остальные цены/сроки сохранены.

## ADR-017 — Accepted: официальный BAAI/bge-m3 dense ONNX

Блок2 утверждает bge-m3 как основной кандидат. Многоязычный checkpoint пригоден для русских данных по назначению, что отдельно проверено на собственном корпусе. Pinned revision5617a9f61b028005a4858fdac845db406aefb181; все7 files SHA-256 закреплены. Выбраны официальный FP32 ONNX, CLS+L2,1024d, CPU batch1, без prefix, max8192. FastEmbed0.7.3 не поддерживает модель в своём registry; вместо неявного обновления зависимости добавлен прямой ONNX Runtime adapter. FastEmbed остаётся только для будущей sparse-стадии. Tokenizer не обрезает input. Нет смены модели или квантования. Альтернатива multilingual-e5-small существенно легче, но имеет384d/512 tokens, требует query/passage prefixes, новой коллекции и новой оценки; без согласования не используется. На8ГБ RAM текущий вариант выполняется, но дорог по памяти и CPU; latency/SLA не обещаются.

## ADR-018 — Implemented: dense поколения и безопасная публикация

Реализует ADR-010: immutable artifact → deterministic physical collection → batch upsert → full readback + smoke → atomic alias. Для изменённых/удалённых документов создаётся полное новое поколение, старые не удаляются. No-op проверяет payload и vectors, а не только количество. Query pin физической collection защищает от смешивания поколений. Local writer lock предполагает единственного publisher; multi-host concurrency не заявляется. Реальные Server tests подтверждают interrupted update и restart, но не hardware power loss или backup restore.

## ADR-019 — Accepted: frozen source recall до оценки

13 query relevance sets зафиксированы commit1003d53 до первого model search. Эталоны не меняются по результатам. Macro Recall@3/5 измеряет долю найденных источников, включая multi-source cases; отдельно публикуется достижимый ceiling для фиксированного k. T11 и частиT12 вне retrieval-границы не притворяются поисковыми тестами. Малый набор не доказывает обобщение, медицинскую безопасность или качество LLM. Dense-only baseline сохраняется для последующего сравнения; API, hybrid и генерация не входят в Блок2.

Справка по предложенной, но не использованной альтернативе: [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), 384 измерения, max512, query/passage prefixes. Модель требует отдельного согласования и сравнения на том же corpus; её качество здесь не измерялось.

## ADR-020 — Implemented: BM25 Russian и единый corpus generation

Выбран утверждённый FastEmbed0.7.3 Qdrant/bm25 без обновления Server1.15.1. Client вычисляет TF/length factors, server применяет IDF один раз. k1=1.2,b=0.75; avg_len измеряется тем же analyzer по полным source texts. UTF-8 asset закреплён SHA/revision/license; исправлен platform-dependent open и разделены stemming/stopword toggles. NFKC/casefold/ё-е/каноническийSKU применяются одинаково к document/query. Частицыне/нет/без сохранены; перевод, synonyms и exact catalog filters не симулируются. Альтернатива source-specific boosts/синонимический словарь отклонена на этом этапе для честного baseline без query tuning. Sparse и dense одной identity находятся в одном point; один descriptor и alias исключают публикацию половины representation.

## ADR-021 — Implemented: native RRF и детерминированный visible cutoff

Реальный Server1.15.1 принимает named sparse/idf и FusionQuery RRF. Используется default k=2 при rank0, равные ветви, prefetch20. Независимая сумма обратных рангов сверена с фактическими Server scores. Weighted/configurable RRF из новых версий не переносится. Первый прогон обнаружил перестановки равных fused scores, в том числе на границеtop5: вместо сортировки уже усечённой пятёрки запрашивается полный union, затем UUID tie-break до top-k. Исходный прогон сохранён, labels/weights/depth не менялись. Это детерминированное разрешение равенств, а не reranker. Порядок внутренних branch ties зависит от выбранного Server; проверяется на corpus, не обещается для всех будущих datasets.

## ADR-022 — Accepted: честное многокритериальное сравнение

До изменений dense baseline зафиксирован896cbb0, план эксперимента8669485. Измеряются macro source Recall@3/5, MRR@5 по первому relevant source и warm latency p50/p95 nearest-rank. Три повтора, порядок modes циклически меняется; без query-vector cache. MRR не измеряет полноту multi-source ответа. Общий прирост Recall@5 не скрывает регрессии Recall@3/MRR и отдельных перефразировок. Stemming-off/prefetch5 публикуются как diagnostics, без замены primary конфигурации по известным13 вопросам. Для promotion другой настройки нужен независимый набор; reranker/LLM не реализуются без приёмки.

## ADR-023 — Implemented: компактный multilingual cross-encoder

После приёмки Блока 3 добавлен optional reranker mMARCO MiniLMv2, официальный FP32 ONNX с immutable revision и SHA-256. CPU/RAM бюджет, Apache-2.0, русский mMARCO и отсутствие новых тяжёлых зависимостей определили выбор до оценки результатов. [Сравнение трёх кандидатов](reranker-model-selection.md) отделяет опубликованные характеристики, оценки веса и реально измеренную память/latency. BGE-M3 и business1.1 не заменяются. Прямой pair inference с Identity logit, без silent truncation. Коллекция, ID, dense/sparse представления и правила публикации остаются прежними.

## ADR-024 — Implemented: optional rerank и атомарный fallback

Hybrid RRF выдаёт единый pinned candidate pool. Primary10, final5; размер и отключение доступны через CLI. Cross-encoder ранжирует только полученные тексты; source labels не доступны ranking adapter. Равные logits сохраняют RRF order. Исходный score сохранён отдельно от rerank_score; ответ содержит before/after positions, model signature и времена стадий. Исключение загрузки/инференса, неконечный или неполный score batch возвращает исходный Hybrid top-k целиком с категорией fallback. Ошибки retrieval не маскируются, частичные оценки не публикуются. Фабрика модели вызывается лениво; при выключенном rerank модель не открывается. Детали ошибок/тексты запросов не пишутся в журнал.

## ADR-025 — Accepted: независимый holdout и стоимость дополнительного ранжирования

План и десять новых query/source qrels закоммичены `a82a9ee` до первого cross-encoder inference. Исходные 13 labels и результаты Блока3 сохраняются. На development сравниваются pool5/10/15; holdout оценивается только с заранее выбранным pool10. Метрики macro source recall и MRR, а не точность LLM. Warm latency включает encoding/Server/payload/rerank без cache; времена стадий показаны раздельно. Process working set и peak измеряются средствами ОС, размер checkpoint не выдаётся за runtime RAM. Небольшой holdout не доказывает переносимость на другие магазины. Rerank остаётся явно включаемым режимом до продуктового решения о качестве и latency.


## ADR-026 — Implemented: local-only provider and transparent boundaries

Сравнены Ollama/Qwen3, Gemini Flash и Groq Llama; без разрешения на оплату облачные adapters не подключаются. Существующая Ollama0.33.2 найдена вне PATH, запущена без переустановки и cloud inference. Выбрана локальная Qwen3:0.6b Q4_K_M, digest7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435. Default disabled и отсутствие runtime mocks сохранены. Test doubles не выдаются за real e2e.

## ADR-027 — Implemented: whole-unit grounding, tool routes and source coverage

Ссылка не доказывает истинность свободного текста. Provider возвращает ограниченный план evidence selection; сервер проверяет полный исходный unit и mapping ID. Полные sections сохраняют отрицания и исключения. Цены/SKU находятся в утверждённом snapshot. Сложные деньги и catalog filters выполняются typed deterministic tools, без неоправданной LLM generation. Полный корпус20 используется для domain coverage, сохраняя честный top5 baseline. Этот extractive MVP не является универсальным semantic entailment/intent solver.

## ADR-028 — Implemented: six-way Answer Control and pending handoff

Дополнение владельца заменяет первоначальный status confirmed/insufficient_context/error шестью business outcomes; legacy grounding_status оставлен отдельно. Неподключённые действия не должны зависеть от спекулятивной LLM. Handoff contract1.0 только описывает передачу, created=false; реальное создание требует отдельной интеграции и согласия. Категории считаются на response boundary, включая timeout/busy, без поздних ложных answered. Это не показатель фактически решённых клиентских проблем.

## ADR-029 — Implemented: bounded CPU service and tested configuration

FastAPI endpoints/chat,/health,/ready заменяют старый нереализованный /v1/answers план. Body32KiB/5s, per-credential/process rate30/min, single worker, request IDs, safe errors and no-access-log. Deadline90s не освобождает ещё работающий native worker. Provider retry только один раз при connect failure, без retry read timeout/HTTP500. Cold LLM startup ограничен120s и вынесен в readiness.

32K контекст потребовал около4.4GB по Ollama и cold load превысил30s. Выбран8192, CPU2/GPU0 и compact E01 aliases; source UUID не теряется. Official tokenizer pinned c1899de289a04d12100db370d81485cdf75e47ca, input budget с резервом и проверкой фактического prompt_eval_count. Медленный начальный денежный путь заменён точным инструментом, не mock-ответом. Неудачные результаты и регрессия отрицания «брака нет» сохранены; разметка/бизнес1.1 не менялись.

## ADR-030 — Implemented: frozen independent MVP evaluation

54 новых вопроса зафиксированы241cb9f до inference:12development/42final. После9/12 development исправлены платёжные словоформы, explicit human request и избыточный context lifetime/отмены;212 unit прошли. Runtime89087a9 зафиксирован до единственного final run:29/42,18completed real LLM/21attempts. Final labels/runtime после результата не настраиваются. Recall, source integrity, completeness, tools, statuses, route class и latency разделены; customer resolution/blind human scoring не заявляются.

## ADR-031 — Accepted limitation: MVP PARTIAL and source suitability gap

Citations и source integrity не гарантируют ответ на вопрос: F10 получилPL-01 вместоDR-05 при наличии нужного источника в retrieval. Context выбирают правила из полного corpus20, LLM выполняет evidence selection. Quality/latency gates не выполнены. Не включаем reranker, не меняем business1.1/модели, не добавляем CRM/Orders/frontend ради формального завершения. Следующее решение — ограниченная коррекция intent/context/suitability и новый preregistered набор по отдельному заданию.

## ADR-032 — Verified scope: actual deployment checks and resources

Новая clone/venv47packages:212unit,13real Server contracts(FAQ double),3real HTTP включая Qwen,7actual boundary/dependency probes. Pause Qdrant/unload Qwen даютhealth200/ready503/chat503. Stop/start CLI превысили40s, фактическое восстановление и сохранность20points/full payload/dense/sparse/alias подтверждены отдельно. Windows venv launcher не выдаётся за Uvicorn RAM: actual PID взят из своего server log. Host memory load до96%, HTTP p95≈61s. GPU/HA/load/API container/security scan не заявлены. После тестов API останавливается, Qwen выгружается; один worker/reranker off сохранены.

## ADR-033 — Implemented: bounded corrective intent and evidence obligations

42 final вопроса Блока6 стали regression. Новые24 вопроса/факты/ожидаемые статусы и gates зафиксированы до изменения runtime; SHA проверяется evaluator. Диагностика всех42 сохранена отдельно, включая13 неуспехов и пересекающиеся с ними9 неполных ответов. До независимого запуска выполнен development12/12 и первый regression40/42. Ошибки падежа «денег» и лишнего accrual-раздела в вопросе redemption исправлены на regression, не на holdout. Runtime зафиксирован `d897630` до независимой проверки; последующие изменения результатов не являются настройкой.

Конечная доменная онтология задаёт facets и source obligations вместо одного списка общих ключевых слов. Роль оплаты пересылки отличается от checkout; общий tracking FAQ отличается от личного статуса; местоименный товар без ID вызывает уточнение. Answer Control проверяет реально выбранные разделы по вопросу, а не только declared context coverage. Общая онтология остаётся общей точкой отказа, не универсальным доказательством entailment. Источники по-прежнему целые и сверены с неизменным снимком1.1. Scores не являются вероятностью. Diagnostic trace показывает retrieved/context/selected sections, abstain и missing obligations без записи пользовательских текстов в runtime log.

## ADR-034 — Implemented: smaller CPU budget and reusable evidence prefix

Модель и её digest не меняются. API использует ctx4096/output128 вместо8192/512; LLM25s/API40s, один worker/CPU2, reranker off. Полные units сортируются по section, затем в prompt идут evidence/tools и только потом вопрос, чтобы неизменная часть могла использовать prompt cache. Нет обрезания source text и повторов после read timeout. Целые UUID остаются в публичном контракте, внутренний prompt передаёт компактные aliases/section вместо UUID. Уменьшение timeout не считается успехом без проверки качества и числа ошибок. Небольшой prefix experiment и RAM/latency публикуются отдельно; host RAM может зависеть от чужих приложений, load/SLA не заявлены.
