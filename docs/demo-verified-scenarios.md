# Verified API demonstration

Проверенные примеры из [clean clone](block-6.2-clone-check.json) runtime0fb3183, сохранённые в442c028. При закрытии их повторно не запускали. Полный набор и неуспешные случаи остаются в [отчёте6.2](block-6.2-results.md). Эти три успеха не являются общей приёмкой языка.

## Запуск

1. `git clone https://github.com/KHABAR0611/k-beauty-ai-support.git`, перейти в каталог, проверить commit/tag из передачи результата. Метка `research-cycle-1-partial` — snapshot, не production release.
2. Python3.12, virtual environment; `python -m pip install -r requirements/service-test.lock`; установить `PYTHONPATH=src`. Secrets экспортировать из приватного окружения; Python не читает `.env` автоматически.
3. Выполнить подготовку по [README](../README.md) и [API](api.md): ingestion, pinned model/tokenizer downloads, dense embed, hybrid artifact/index и приватный Qdrant key. Если проверенный индекс20points уже есть, повторная полная индексация для показа не требуется. Веса/cache в Git не входят.
4. `docker compose up -d qdrant`; проверить `/healthz` и `/readyz`. Порт чистого Compose6333, историческая установка6394 — использовать собственный deployment URL. Никакого `down -v`.
5. Запустить установленный Ollama локально, сверить model digest из API docs, выставить `LLM_PROVIDER=ollama`, `LLM_MODEL`, `LLM_MODEL_DIGEST`, `OLLAMA_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `API_ACCESS_KEY`. Cloud API не нужен. Reranker=false, один worker, CPU2, context4096/output128, LLM25s/API40s.
6. `python -m uvicorn kbeauty_support.api.app:app --host 127.0.0.1 --port 8090 --workers 1 --no-access-log --no-proxy-headers`. Дождаться `/ready`200; `/health`200 во время прогрева ещё не означает готовности. Полный runbook: [демонстрация](block-6-demo.md).

Существующая clone-проверка использовала locked environment и pinned caches/Server. Она не доказывает новую сетевую загрузку всех зависимостей на пустой машине. Текущая модель и Python/runtime hashes закреплены; отказ на другой revision не обходить молча.

## HTTP-примеры в PowerShell7

Задать тот же приватный API_ACCESS_KEY локально через `Read-Host -MaskInput`, не вставлять его в публичный файл. Header содержит ссылку на переменную окружения, не реальный token:

```powershell
$headers = @{Authorization = "Bearer $env:API_ACCESS_KEY"}
Invoke-RestMethod http://127.0.0.1:8090/health
Invoke-RestMethod http://127.0.0.1:8090/ready
$body = @{question = "Оплата через СБП: есть комиссия магазина?"} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8090/chat -Method Post -Headers $headers -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

Фактически получено: HTTP200, answered, источник PL-01, комиссия магазина отсутствует; настоящий Qwen, generation_performed=true. Ответ extractive и может включать полный раздел оплаты.

```json
{"question":"Где заказ 84621?"}
```

POST `/chat` с тем же Bearer: HTTP200, requires_external_data, без sources. Номер вымышленный; статус не проверяется и не выдумывается. Это control-only путь, не LLM inference.

```json
{
  "question":"Корзина 2000, WELCOME10, ПВЗ. Итог?",
  "pricing":{
    "subtotal_kopecks":200000,
    "delivery":"pickup",
    "pickup_available":true,
    "registered":true,
    "first_order":true,
    "promo_code":"WELCOME10",
    "bonus_balance":0,
    "bonus_requested":0
  }
}
```

HTTP200, answered, generation_performed=false. Discount20000 коп., goods cash180000, доставка25000, total205000 коп. =2050 ₽, начисление90 бонусов. Bonus cap360, списано0. Источники DR01/02 и PL02/03/04/05. Это условный пример по user-declared корзине, не подтверждение реального заказа/баланса/eligibility.

## Обязательный показ границ

В recorded H13 вопрос «Награда за покупку появляется сразу после получения? Как долго потом хранится баланс?» получил answered с DR-03 о хранении посылки — неправильная пригодность при настоящем source text. H14 о базе5% начисления получил доставку. Не скрывать эти примеры. Новый случай в живом показе может отличаться; deterministic source/model settings не гарантируют полную повторяемость timing/output на другой среде.

После показа остановить собственный API и выгрузить Qwen через локальный Ollama. Не завершать чужие процессы/глобальный Docker и не удалять Qdrant volumes. Для просмотра документации Docker не требуется; Server API-показ требует доступный Qdrant.
