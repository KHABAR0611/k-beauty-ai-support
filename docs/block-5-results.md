# Блок5: контролируемая генерация и API

Проверено2026-10-20. Бизнес-данные1.1,20 чанков и13 relevance labels не изменены. Начальная версия32a3ae3. Представлен на приёмку; следующий этап не начат.

## Поставка и модель

FastAPI0.116.1/Uvicorn0.35.0: POST /chat, GET /health, GET /ready, защищённый GET /metrics. Цепочка: authenticated request → Hybrid dense/BM25/RRF → approved snapshot/provenance → whole-unit context → typed calculator/catalog либо local LLM evidence selection → отдельный Answer Control → answer/sources/status/request_id/timings.

Reranker опционален и выключен. Retrieval pool20 позволяет проверить нужные источники составного вопроса; это не улучшение top5 и не стратегия большого каталога. Context ограничен14 источниками/24000 UTF-8 bytes, без обрезания исключений. Pinned официальный tokenizer контролирует prompt/schema+output reserve, silent truncation отсутствует.

Модель выбирает evidence IDs через JSON schema. Сервер проверяет allowlist, полный текст/metadata/версию/SHA относительно approved snapshot и рендерит исходные units. Денежный tool считает в копейках с Decimal ROUND_HALF_UP: promo → cap20% после promo → delivery после бонусов. Неполные typed inputs требуют уточнения. Это extractive MVP, не свободный синтез и не универсальный semantic entailment checker.

Сравнены Ollama/Qwen3:0.6b, Gemini2.5Flash и Groq/Llama3.3-70B: [решение](block-5-provider-decision.md). Выбран уже установленный Ollama0.33.2, local qwen3:0.6b GGUF Q4_K_M,522653767bytes, metadata parameter_size=751.63M. Digest `7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435`, manifest и blobs проверены SHA-256. CPU2 threads/GPU0, context8192/output512,temp0/seed42,think=false,keep_alive=-1. Tokenizer Qwen/Qwen3-0.6B revision c1899de289a04d12100db370d81485cdf75e47ca. Default provider disabled. Платных и облачных inference-запросов0; API fee0 не включает электричество/оборудование. Отсутствие команды в PATH первоначально не доказало отсутствие Ollama: установка найдена в стандартном каталоге и запущена без переустановки.

## Фактические проверки

| Проверка | Результат | Граница |
|---|---|---|
| Unit/regression |197 passed,0 failures,49.58s |6 statuses, negative inputs, calculations, provider/dependency errors |
| Server/API contracts |13 passed,96.44s |реальный Qdrant/BGE; FAQ provider double явно помечен |
| HTTP smoke без LLM |8 passed |настоящий Uvicorn/TCP, readiness503 и control-only |
| Реальный HTTP e2e |12/12 business contracts |без doubles:8 tools,2 external control,2 actual LLM |
| Дополнительные атаки |2/2 безопасных исхода |реальная LLM injection и pending human handoff |
| Benchmark |13 queries +12 contracts,3 повтора |неизменная разметка, FAQ double явно помечен |

[Все12 результатов](block-5-scenario-results.md), [реальные запросы/ответы](block-5-live-e2e.json), [test summary](block-5-test-results.json), [contract benchmark](block-5-contract-benchmark.json).

Source macro Recall@3=0.726923, Recall@5=0.917949, MRR@5=0.903846 на13 frozen queries. Recall — доля релевантных уникальных разделов в top-k, усреднённая по запросам. Это coverage, не точность ответа. Результат равен прежнему Hybrid baseline; qrels SHA-256 d7b1bbd56f943e1f9e56255b6a7fa822965ec8b480a38c6ec7a4660f848573cd. Полный pool20 затем domain coverage проверяет нужные источники, поэтому12/12 API pass не означает Recall@5=1.

Final-answer checks: полный ожидаемый source set/critical fragments, точные totals/начисления, отрицательный подбор каталога, невозможность внешних действий и safe status. Это синтетические контрактные проверки, не слепая human evaluation или общая вероятность корректности модели. В business run10 answered/2 requires_external_data. После ещё2 атак /metrics считает14 responses:11 answered,2 requires_external_data,1 handoff_required. Реальная доля решённых клиентских проблем неизвестна.

## Производительность

Intel i5-3470S4cores/4threads, RAM около7.94GiB, Windows/Python3.12.14. GPU не использовалась. Startup до полной readiness59.55s при уже прогретом Ollama; это не полностью холодный запуск всей системы.

Retrieval39 наблюдений p50=0.662s,p95=1.075s. Business HTTP12 p50=0.868s,p95=24.768s. Typed tools8 p50=0.804s,p95=1.440s. LLM business всего2 наблюдения:2.614–24.768s HTTP; p95 при n=2 равен максимуму и не является стабильным SLO. Prompt cache заметно влияет на разброс.

| Live FAQ | Input tokens | Output tokens | LLM stage,s | HTTP,s |
|---|---:|---:|---:|---:|
| T07 | 1084 | 32 | 23.723 | 24.768 |
| T08 | 640 | 26 | 1.723 | 2.614 |

Дополнительная LLM injection:1014 input/32 output,22.634s HTTP. У tools/control usage=null.

Отдельный contract benchmark process peak working set=1.524GiB; process CPU=30.81s за23.43s wall (131.5% на шкале одного ядра; не host CPU). В12 поздних resource samples живого прогона максимальный working set: API/BGE=1.545GiB, llama-server=1.492GiB, Ollama=20.8MiB. Docker/OS исключены; shared pages могут учитываться дважды. Это наблюдаемый интервал, не весь прогон. Private commit и historical peak отдельно в [resource trace](block-5-live-resources.json). /api/ps сообщает1528142233bytes (~1.423GiB), VRAM0/context8192. CPU-only LLM latency заметна; мгновенные FAQ ответы не обещаются.

## Неудачные подходы и исправления

1. Context32768 требовал около4.397GB оценочной RAM, cold call не укладывался в30s. Ограничены context8192, warmup120s, call60s/API90s, compact evidence aliases вместо UUID внутри prompt; публичные полные UUID сохранены.
2. Денежные задачи через LLM дали пять последовательных60s timeouts; диагностика остановлена. [Первые5 наблюдений](block-5-live-initial.json) сохранены, остальные не выдуманы. Добавлены явные typed tool routes с provenance и generation_performed=false.
3. Следующий run был10/12: «брака нет» ошибочно выбирало DR-05; неподключённая операция возврата T11 зря ожидала LLM. Исправлены negation routing и control-only. [Run10/12](block-5-live-before-control-fix.json) сохранён отдельно от финального12/12. Бизнес-правила/ожидания не менялись.
4. Provider-disabled обслуживает безопасные control/tools, но FAQ не маскируется под успешную генерацию. Полная readiness503 без всех зависимостей. Deadline не освобождает слот до окончания native worker, late response не увеличивает answered.

## Надёжность и ограничения

Docker Engine29.8.0, Compose5.5.1, реальный Qdrant1.15.1, health/readiness200,20points. API читает индекс, не переиндексирует бизнес-данные. Persistence/restart доказаны Блоком4, здесь заново не проверялись. API проверен нативным Uvicorn, его Docker image не собирался. [Runtime audit](block-5-runtime-check.json) подтверждает неизменность37 архивных файлов/HEAD, бизнес-данных и baseline.

Проверены safe Qdrant/LLM failures, schema/IDs/tampered sources, source conflict, budgets, auth/body/rate/request UUID/safe logs. Answer Control имеет6 исходов, scores не вероятности. Handoff1.0 — pending/created=false; CRM, заказы, оплаты, реальный баланс и наличие не подключены. Конфликт payload одного section определяется, универсального semantic conflict detector/NLI нет.

Не проверены HA, публичный TLS deploy, concurrent load, GPU, vulnerability audit, multi-user auth и distributed limits. Один worker, ограниченный backlog, без обещания hard cancellation native inference. Extractive ответы длинные, доменная coverage эвристическая; schema/allowlist защищают факты, но не доказывают понимание любого вопроса. Temp0/seed42 не гарантируют битовую идентичность на другом runtime/hardware.

## Следующий этап после приёмки

Независимый holdout с отрицаниями/составными вопросами, слепая оценка полезности/полноты, reranker/context ablations, повторные cold/warm latency, нагрузочный профиль, security/dependency scan, clean deployment. Варианты ускорения: короткий проверяемый renderer, versioned prompt cache, более быстрый CPU/GPU либо согласованный внешний LLM с оценкой качества/стоимости. Реализация следующего блока не начата.

## Проверка чистого клона

Код4e6176961096d7e787ee28fb7721c4e2c0903de7 получен через git clone --no-hardlinks. Повторно прошли197 тестов, source export дал прежний fingerprint, восемь настоящих HTTP smoke проверок без LLM прошли. Использовано ранее созданное чистое окружение47 pinned packages; модели не скачивались заново и live LLM в клоне не проверялась. [Машиночитаемый результат](block-5-clone-check.json). Клон предназначен только для проверки, активная версия остаётся одна.

После испытаний собственный Qwen runtime выгружен из RAM; веса/кеш сохранены, loopback Ollama и Qdrant оставлены работающими. Повторный запуск API прогреет модель.
