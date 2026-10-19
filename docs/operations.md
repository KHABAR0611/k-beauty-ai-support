# Надёжность, наблюдаемость и безопасность

Статус: local source preparation и его JSON-события реализованы; остальные требования ниже относятся к последующим этапам, кроме существующей Compose-конфигурации. Конфигурация Qdrant одиночная, без HA и без SLA. Фактический runtime зависит от доступности образа и фиксируется в validation-report.md.

## Compose и хранение

Qdrant 1.15.1 публикует REST только на 127.0.0.1 и пишет в named volume `qdrant_storage`; gRPC наружу не опубликован. Ключ задаётся в `.env`, файл игнорируется. Source-audit — отдельная rootless задача, read-only filesystem, без сети. Dockerfile не устанавливает RAG runtime: только локальный audit, которому достаточно stdlib. API/ingestion контейнеры добавляются после реализации, не запускаются заглушками.

У Qdrant контейнера пока нет встроенного Compose healthcheck, чтобы не предполагать наличие curl внутри image. Внешний probe (будущий монитор/CI) должен проверять `GET /readyz` на REST с `api-key`, ожидать 200 с ограниченным timeout и retries. Running container не равен готовому индексу; отдельный probe проверяет active alias и manifest. Перед остановкой убедиться, что job не публикует поколение. Не удалять volume ради исправления запуска.

Backup: перед изменением server/schema создать snapshot collection через административный клиент, сохранить manifest/catalog и checksum вне volume. Restore в отдельную collection, проверить hashes/counts и затем переключить alias. Перезапуск/persistence и restore ещё не испытаны; до испытания не заявлять backup готовым.

## Ошибки и deadlines

Начальная политика (требует измерений): connect timeout 2 s, Qdrant query 5 s, rerank 10 s, LLM 30 s, общий HTTP deadline 45 s. Максимум два retry с jitter на transient read errors и 429 с Retry-After в пределах deadline. Невалидные данные не ретраить. Для publishing сначала проверить состояние операции, не повторять alias switch вслепую.

Отказ mandatory retriever/reranker/provider по умолчанию завершает запрос явной 503/504; скрытое отключение стадии запрещено. Будущий degraded mode потребует ADR, отдельного статуса ответа и оценки качества. Ingestion failure не должен затронуть active index.

## Наблюдаемость

Будущие JSON logs: timestamp UTC, level, request/job_id, stage, duration_ms, generation, model/analyzer revision, result_count, error_code, retry_count. Не логировать полный вопрос, документы, email, keys или CVV; диагностические traces только обезличенные и с retention.

Метрики: request/error counters, stage latency histograms, empty retrieval rate, citation validation failures, token usage, job outcomes, active generation и data age. Алерты на отсутствие alias/manifest mismatch, рост dependency errors и failed publish. Нулевые метрики не выдавать за измеренную надёжность.

## Безопасность

Ingestion: фиксированный allowlist, запрет symlink/path traversal, ограничение размера и UTF-8; source text недоверенный. Разделить read-only query credential и index-admin credential при реализации; текущий локальный Qdrant key не означает это разделение. Секреты в environment/secret manager, не в Git и не в model context. Публичный ingress только после TLS/auth/rate limits. Provider egress только к разрешённым endpoints, без пользовательских URLs (SSRF).

Prompt injection — отдельный набор атак на user и retrieved text; одних инструкций модели недостаточно. Никаких инструментов платежа/возврата. Генерация проверяется по evidence и точным числам; медицинские назначения и гарантии излечения не допускаются.

## Воспроизводимость

Основные версии закреплены; полный transitive lock, image digests, model revisions и smoke на чистой машине — gate перед развёртыванием API. Текущий Dockerfile предназначен только для аудита; build и Qdrant startup должны иметь отдельное доказательство в validation report. Dependency/security scan не выполнялся.

## Изолированная проверка Qdrant

`python infrastructure/verify_qdrant.py` запускает только Compose project kbeauty-review-check на loopback6394, в отдельном named volume. Создаётся уникальная infra_smoke collection и один синтетический point с literal vector[1.0]/случайным marker, затем проверяются health/readiness и тот же point после restart. Источники data/ не читаются, модели не вызываются. Существующие контейнеры/образы/volumes и collections не удаляются. Результат в artifacts/docker-review/result.json, локальный test API key — в connection.env того же игнорируемого каталога; ключ не логируется и не коммитится. Не запускайте тот же project для других данных. Проверка не является backup/restore или промышленным SLA.
