# FastAPI contract0.7

Независимая приёмка: [Блок6 PARTIAL](block-6-results.md), [запуск и реальные примеры](block-6-demo.md). API stateless; выбор context ограничен доменными правилами. Подбор/расчёт используют явные typed fields; полное понимание произвольного русского запроса/продолжения диалога не заявляется. Источники проходят integrity gate, но F10 выявил недостаточную suitability проверку.

Реализованы POST /chat, GET /health, GET /ready и защищённый GET /metrics. Это синхронный доменный pipeline за отдельным вычислительным worker; ASGI event loop не выполняет нейросетевой inference. Default provider=disabled, reranker=false. В API нет runtime mock/provider переключателя для клиента.

## Запуск

Установить requirements/service-test.lock, задать PYTHONPATH=src. Python не читает .env автоматически: это пример переменных, а Compose использует свой .env. Секреты задаются окружением и не передаются в аргументах CLI. API_ACCESS_KEY и QDRANT_API_KEY должны быть локальными приватными значениями.

```powershell
python -m pip install -r requirements/service-test.lock
$env:PYTHONPATH = "src"
$env:API_ACCESS_KEY = Read-Host "Private local API access key" -MaskInput
$env:QDRANT_URL = "http://127.0.0.1:6333"
$env:QDRANT_API_KEY = Read-Host "Private Qdrant key" -MaskInput
$env:LLM_PROVIDER = "disabled"
python -m uvicorn kbeauty_support.api.app:app --host 127.0.0.1 --port 8090 --workers 1 --no-access-log --no-proxy-headers
```

Для запуска существующей установки вне PATH доступен PowerShell7 helper infrastructure/start_local_ollama.ps1 (опционально -Direct только для дочернего процесса). Он переиспользует работающий сервер, не переустанавливает Ollama и не скачивает модель автоматически. Для живой локальной генерации нужен доступный Ollama, локальная модель qwen3:0.6b и утверждённый digest. Установка Ollama не является частью pip requirements. Model weights не входят в Git. На проверенной машине использовалась существующая установка Ollama0.33.2; cache модели расположен внутри игнорируемого model-cache/ollama, а не публичного source tree. Прежде чем ollama pull, подтвердите OLLAMA_MODELS/OLLAMA_HOST и отсутствие cloud-моделей. При другом digest не подменяйте модель молча.

```powershell
python infrastructure/download_llm_tokenizer.py
# При проблеме прокси: --direct меняет только этот процесс.
$env:LLM_PROVIDER = "ollama"
$env:OLLAMA_URL = "http://127.0.0.1:11434"
$env:LLM_MODEL = "qwen3:0.6b"
$env:LLM_MODEL_DIGEST = "7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435"
$env:LLM_TIMEOUT_SECONDS = "25"
# Повторно запустить API после изменения окружения.
```

Текущие defaults после corrective sprint: LLM timeout25s, общий API deadline40s. Отдельный startup warmup LLM ограничен120s. Health доступен во время background initialization, readiness503 до завершения прогрева BGE/LLM и проверки всех20 source payload. Qwen context4096/output128, temperature0/seed42, CPU2 threads/GPU0. Модель закрепляется keep_alive=-1: это занимает RAM до явного unload. После потери/выгрузки модели readiness падает; восстановление через повторный startup. Автоматическое HA/перезапуск не заявлены. Старые измерения8192/512/60s/90s сохранены в исторических отчётах; они не являются текущими defaults. При большем контексте provider отклоняет запрос, не обрезая условия. Read timeout не повторяется и не становится `answered`.

## POST /chat

Authorization: Bearer <API_ACCESS_KEY>. question1–4000 символов; JSON body≤32768bytes, неизвестные поля и bool вместо числовых значений отклоняются. Тело принимается не дольше5s. Локальный общий лимит30 запросов/минуту на одну настроенную API credential, отдельно в каждом процессе; X-Forwarded-For не меняет бюджет. Второй вычислительный запрос во время занятого worker получает503. Один worker — сознательное ограничение RAM.

```json
{"question":"Первый заказ: KB-003 и KB-004, WELCOME10, курьер СПб. Итог и бонусы?","pricing":{"items":[{"product_id":"KB-003","quantity":1},{"product_id":"KB-004","quantity":1}],"delivery":"spb_courier","registered":true,"first_order":true,"promo_code":"WELCOME10","bonus_balance":0,"bonus_requested":0}}
```

pricing: items(product_id,quantity) либо subtotal_kopecks, delivery=pickup/moscow_courier/spb_courier, registered, first_order, promo_code, bonus_balance, bonus_requested=целое или maximum, pickup_available, compare_options. Для ПВЗ нужна явная доступность пункта. Items используют канонические цены, клиентские цены позиций не принимаются. Subtotal — только заявленная пользователем оценка, не подтверждённый заказ. Право на промокод, баланс и регистрация передаются как условия примера, не проверяются во внешнем магазине.

catalog_query: category, skin_type, fragrance_free, max_price_kopecks, ingredient. Фильтрация выполняется по всему утверждённому каталогу, не по top5. Ночная маска не становится кремом из-за бюджета. Отсутствие ингредиента в текущем snapshot не является сведением о будущих поставках или наличии. Неструктурированные денежные/подборочные запросы получают clarification_needed вместо ненадёжного извлечения чисел LLM.

Ответ: answer, sources, status, grounding_status, request_id, latency_ms, index_generation; optional calculation, catalog_result, missing_fields, usage, handoff, external_data, error_code, diagnostics. status имеет шесть значений из [Answer Control](answer-control.md). Grounding confirmed относится только к проверенным утверждениям/инструментам, не к реальному заказу. Текст основан на целых source units; это extractive MVP, не свободный проверенный paraphrase.

Денежные и структурированные catalog-запросы обслуживаются детерминированными инструментами с provenance. Запросы неподключённых внешних действий получают control-only ответ. Их diagnostics.generation_performed=false, usage=null; они не выдаются за LLM inference. Остальные FAQ проходят настоящую LLM selection и проверку evidence allowlist. Источники сохраняют полные UUID, source, section, version и product_id. Компактные E01-алиасы существуют только внутри provider prompt и отображаются обратно сервером; они не заменяют source IDs публичного контракта.

401 — API access,413 — body,422 — schema/input/context gate,429 — rate,502 — невалидный provider output,503 — dependency/busy,504 — deadline. Во всех ошибках безопасный error_code, без vendor messages/stacktrace или echo input. При native inference deadline ответ504, но слот остаётся занят до фактического окончания операции; поздний результат не учитывается как answered. Платёжные секреты не принимаются. Нет доступа к оплатам, заказам и исполнительным действиям.

## Проверки и примеры

GET /health — процесс, без внешней LLM. GET /ready — полная готовность snapshot/index/encoder/provider/API access; не генерирует бизнес-ответ. GET /metrics требует Bearer и отдаёт категории технических исходов, не customer-resolution rate. [Реальные запросы/ответы](block-5-live-e2e.json), [HTTP без LLM](block-5-http-smoke.json), [12 business contracts с test provider](block-5-contract-benchmark.json).

```powershell
python -m pytest
python infrastructure/smoke_api.py
# Только явный contract benchmark, не настоящая LLM:
python infrastructure/benchmark_api_contracts.py --allow-provider-double
# Для уже запущенного ready API с настоящим локальным LLM:
python infrastructure/evaluate_live_api.py --allow-local-inference --url http://127.0.0.1:8090
```

Для real Server contract tests: KBEAUTY_API_SERVER_TESTS=1, QDRANT_URL/key и KBEAUTY_MODEL_DIR; выполнить python -m pytest tests/integration/test_api_server.py. Только provider заменён явным test double. Влияние живой модели оценивается отдельно через real HTTP. API container image не собирался: backend проверен нативным Uvicorn, Qdrant — существующим Compose Server. Перед публичным доступом нужны отдельная эксплуатационная оценка, TLS, многопользовательская авторизация, retention/log policy и нагрузочный профиль.
