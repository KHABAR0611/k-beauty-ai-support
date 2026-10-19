# API contract — проект

HTTP-приложение ещё не реализовано. Документ фиксирует будущую границу, не работающие endpoints.

`POST /v1/answers`: JSON `question` (1–4000 символов), optional `basket` (SKU и положительное целое quantity), `city`, `delivery_method`, `is_registered`, `is_first_order`, `bonus_balance`, `bonus_requested`, `promo_code`. Числа валидируются, unknown extra fields отклоняются. Нельзя принимать client prices как канонические. Нет доступа к реальному балансу: ответ помечает расчёт по переданным условиям.

Ответ: `request_id`, `status` (`answered`, `needs_clarification`, `insufficient_evidence`), `answer`, `sources` (source_path, section/product_id, version, chunk_id), `index_generation`, optional `calculation` (integer kopecks and whole bonuses). Источники должны существовать в закреплённом snapshot. Не возвращать системные инструкции, provider keys или внутренний stack trace.

Пример формы запроса:

```json
{"question":"Сколько стоит доставка в ПВЗ?","city":"Казань","delivery_method":"pickup","basket":[{"product_id":"KB-001","quantity":1}]}
```

200 — подтверждённый ответ или предметное уточнение; 422 — невалидный вход; 429 — ограничение частоты; 503 — зависимость/индекс не готовы; 504 — deadline. Ошибка: `request_id`, stable `code`, безопасное `message`, `retryable`. Текст исключения provider наружу не передаётся.

`GET /health/live` — только жизнеспособность процесса, без LLM call. `GET /health/ready` — Qdrant, alias и согласованный manifest/catalog, конфигурация обязательных моделей; 503 при неподготовленности. Разделить API readiness от доступности внешней LLM, которую показывать как отдельную dependency status с коротким cache. Ingestion не доступен через публичный HTTP API.

До публичного доступа нужны authentication, TLS, request size/rate limits и CORS allowlist. Сейчас этих механизмов и endpoints нет.
