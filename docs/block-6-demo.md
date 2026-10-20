# Воспроизводимый показ K-Beauty AI Support

Бизнес-данные 1.1 вымышлены. Показываются работающий API, поиск и границы возможностей; реальных заказов, оплат и операторской системы нет. Полный итог независимой проверки находится в block-6-results.md. Не выдавайте удачные примеры за качество на всём наборе.

## Подготовка

1. Получить `main` через git clone и проверить SHA из итогового отчёта. Python 3.12; установка `python -m pip install -r requirements/service-test.lock`, затем `$env:PYTHONPATH="src"` в PowerShell 7.
2. Подготовить локальный `.env` по `.env.example`, заменить оба приватных ключа. Python сам `.env` не читает; секреты экспортируются окружением и не коммитятся.
3. Запустить Qdrant через `docker compose up -d qdrant`. Проверить настоящий `/healthz` и `/readyz`, а не только running. Не удалять volume для восстановления и не использовать `down -v`.
4. На первом запуске выполнить ingestion → официальный model download → embed → hybrid-build → index по командам README. Активный alias должен указывать на проверенное поколение 20 points. Существующий проверенный индекс не нужно заново кодировать перед каждым показом.
5. Запустить установленный Ollama через `infrastructure/start_local_ollama.ps1`. Модель `qwen3:0.6b` должна быть заранее загружена, digest сверяется с API-документацией. Установка Ollama и model weights не входят в pip/Git. Скачать закреплённый tokenizer командой `python infrastructure/download_llm_tokenizer.py`.
6. Экспортировать `QDRANT_URL`, `QDRANT_API_KEY`, `API_ACCESS_KEY`, `LLM_PROVIDER=ollama`, `OLLAMA_URL`, `LLM_MODEL`, `LLM_MODEL_DIGEST` по [API contract](api.md). Для локального показателя из отчёта Qdrant слушал6394, но чистый Compose по умолчанию6333; не копировать номер порта без проверки собственного deployment.
7. Запустить `python -m uvicorn kbeauty_support.api.app:app --host 127.0.0.1 --port 8090 --workers 1 --no-access-log --no-proxy-headers`. `/health` должен отвечать200 ещё при прогреве, `/ready` остаётся503 до готовности всех зависимостей. Один worker, reranker выключен.

Полностью холодный старт может занимать десятки секунд и более; дождаться readiness до показа. На машине8GB не запускать несколько BGE/LLM-процессов одновременно. Проверенные caches можно переиспользовать с обязательной проверкой SHA; это не чистая загрузка моделей через сеть.

## API-примеры для показа

В отдельной PowerShell7-консоли задайте тот же приватный API_ACCESS_KEY через `Read-Host -MaskInput`, затем:

```powershell
$headers = @{Authorization = "Bearer " + $env:API_ACCESS_KEY}
$payload = @{question = "Курьером в СПб: от какой суммы бесплатно и сколько дней везут?"} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8090/chat -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($payload)) | ConvertTo-Json -Depth 12
```

Другие тела запросов:

```json
{"question":"Корзина 2000, WELCOME10, ПВЗ доступен, бонусов нет. Рассчитай оплату.","pricing":{"subtotal_kopecks":200000,"delivery":"pickup","pickup_available":true,"registered":true,"first_order":true,"promo_code":"WELCOME10","bonus_balance":0,"bonus_requested":0}}
```

```json
{"question":"Подбери тонер для сухой кожи без отдушки до 1400 рублей.","catalog_query":{"category":"тонер","skin_type":"сухая","fragrance_free":true,"max_price_kopecks":140000}}
```

```json
{"question":"Где заказ 84621?"}
```

```json
{"question":"Мне нужен сотрудник поддержки."}
```

Покажите отдельно FAQ через настоящую LLM, точный расчёт без LLM, структурированный подбор, неизвестный заказ и pending handoff. Не скрывайте `diagnostics.generation_performed`, `usage`, `status`, sources и ограничения. Текстовые запросы подбора могут требовать структурированных параметров; stateless API не обещает память между сообщениями. Не утверждать, что справочная выдержка всегда достаточно отвечает вопросу.

Для воспроизведения известной regression, а не только удачных примеров:

```powershell
python infrastructure/evaluate_corrective.py --phase answers --split regression --allow-local-inference --url http://127.0.0.1:8090 --output artifacts/regression-evaluation.json
```

Результаты не отправляются в runtime как hints. Разметку после результата менять нельзя.24 новых вопроса corrective sprint уже оценены один раз; `--split holdout` воспроизводит их, но не создаёт новую независимую проверку после знакомства с результатами. Нельзя называть этот набор real customer resolution rate. Для отдельного retrieval прогона `--phase retrieval`; не держать второй BGE процесс одновременно с API на8GB. Текущие бюджеты Qwen4096/output128, LLM25s/API40s; исторические8192/512/60s/90s не копировать как defaults. Текущий итог: [PARTIAL, все ограничения](block-6.1-results.md).

## Нужен ли web chat

Для технического показа достаточно HTTP-примеров, trace и встроенной `/docs` со схемой API. Bearer проверяется middleware; Swagger здесь не настроен как полноценный чат или авторизованный frontend. Полноценный frontend в Блоке6 не добавлялся.

Если позже нужен показ нетехническому человеку, минимальный вариант — одна локальная страница/форма с вопросом, явными полями корзины/подбора, sources и статусом. Не хранить API key в localStorage/публичном JS, не обещать память диалога. Это отдельное небольшое решение после устранения обнаруженных quality gaps, не автоматическое расширение MVP.

## После показа

Остановить собственный API. Через локальный Ollama unload только модель проекта (`keep_alive:0`), не удаляя weights. При отсутствии других задач завершить Docker Desktop штатно; named volume сохраняет данные. Не останавливать чужие контейнеры и процессы. Следующий запуск снова требует warm readiness. Предпочтение: запускать ресурсоёмкие компоненты только на время показа/проверки.
