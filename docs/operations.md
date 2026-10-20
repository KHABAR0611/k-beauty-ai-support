# Надёжность, наблюдаемость и безопасность

Статус0.7.0: source preparation, dense/BM25/RRF, optional reranker, controlled generation и FastAPI реализованы. Проверки ниже, не отмеченные результатами Блока2, остаются требованиями последующих этапов. Конфигурация Qdrant одиночная, без HA и без SLA. Фактический runtime зависит от доступности образа и фиксируется в validation-report.md.

## Compose и хранение

Qdrant 1.15.1 публикует REST только на 127.0.0.1 и пишет в named volume `qdrant_storage`; gRPC наружу не опубликован. Ключ задаётся в `.env`, файл игнорируется. Source-audit — отдельная rootless задача, read-only filesystem, без сети. Dockerfile не устанавливает RAG runtime: только локальный audit, которому достаточно stdlib. API/ingestion контейнеры добавляются после реализации, не запускаются заглушками.

У Qdrant контейнера пока нет встроенного Compose healthcheck, чтобы не предполагать наличие curl внутри image. Внешний probe (будущий монитор/CI) должен проверять `GET /readyz` на REST с `api-key`, ожидать 200 с ограниченным timeout и retries. Running container не равен готовому индексу; отдельный probe проверяет active alias и manifest. Перед остановкой убедиться, что job не публикует поколение. Не удалять volume ради исправления запуска.

Backup: перед изменением server/schema создать snapshot collection через административный клиент, сохранить manifest/catalog и checksum вне volume. Restore в отдельную collection, проверить hashes/counts и затем переключить alias. Перезапуск/persistence испытан в Блоке2; restore ещё не испытан; до испытания не заявлять backup готовым.

## Ошибки и deadlines

API: Qdrant query5s, Ollama60s, startup120s, общий HTTP deadline90s. Только connection failure до отправки повторяется один раз; read timeout/HTTP500 не повторяются. Невалидные данные не ретраить. Native inference не имеет hard cancellation: слот удерживается до завершения worker. Для publishing сначала проверить состояние операции, не повторять alias switch вслепую.

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

## Проверенный dense runtime

Фактические проверки и ограничения: [Блок2](block-2-results.md), команды и recovery: [спецификация](block-2-spec.md). Native Docker pull обрывался через Engine CDN/proxy; официальный образ был загружен через прямой Registry API, SHA-256 каждого объекта проверен, затем docker load. Происхождение в block-2-image-provenance.json. Системные DNS/proxy и существующие Docker-данные не изменялись. Python probes Qdrant идут напрямую по loopback; модели скачиваются отдельным downloader с необязательным process-local --direct. Другие deployments должны подтвердить собственную сетевую конфигурацию.

Dense CLI использует Qdrant request timeout30s, без автоматических повторных alias transactions; это отдельный batch CLI, не API deadline90s. JSON logs показывают прогресс encoding/publish и категорию ошибки. Пока нет monitoring service, read-only credentials, load tests и dependency security scan.

## Hybrid runtime0.5.0

Установка: requirements/hybrid-test.lock,43 pinned packages; query BM25 не требует model download. Активный alias может указывать на hybrid collection; legacy dense-mode читает dense representation той же физической генерации. Перед сменой analyzer/k/b/asset/avg_len создайте новый artifact и поколение. Не обновляйте sparse отдельно от dense внутри active collection. Документированные отказы analyzer mismatch и sparse readback блокируют публикацию.

На данном компьютере восстановление накопленных коллекций после restart заняло около65s, больше первоначального30s тестового ожидания. Container running и отсутствиеOOM не означают готовность REST. Integration probes используют ограниченный monotonic deadline180s с небольшими интервалами. Сами query не ждут restart автоматически и возвращают явную ошибку; HA/transparent failover не заявляются. Retention/GC пока отсутствует, старые коллекции сохраняются, поэтому время восстановления необходимо учитывать. Не удалять volume для ускорения теста.

## Optional reranker0.6.0

Установка requirements/rerank-test.lock не добавляет пакетов к hybrid stack. Загрузить pinned official checkpoint через infrastructure/download_reranker.py; cache не переносится в Git. Выделить ещё около471MB disk и измеренный дополнительный private commit; на данном CPU выполнять запросы последовательно, не создавать несколько процессов с двумя моделями без оценки RAM. Для current sources все460 query/document pairs в development+holdout укладываются в512, но gate остаётся обязательным для новых документов.

На query path использовать mode=rerank явно; для возврата к Hybrid — mode=hybrid или --disable-rerank в rerank mode. Текущий рекомендуемый режим Hybrid: primary pool10 потерял необходимые источники в отдельных составных вопросах. Модельный failure не должен менять membership исходного top-k: проверяется весь score batch, затем применяется новый порядок. В JSON сохраняются applied/fallback category, source fields и stage timings. Нет автоматического retry native inference, hard deadline или circuit breaker; перед HTTP-нагрузкой нужны отдельный worker/лимиты/наблюдаемость и утверждённый SLO. GPU latency и серверная многопользовательская эксплуатация не проверялись.

## API/Ollama0.7

API проверен нативным Uvicorn на loopback, Qdrant в Compose; API image не собирался. Запуск/секреты/ready описаны в api.md. Один API worker, CPU2 threads; reranker=false, provider=disabled до конфигурации. Qwen8192/output512 с pinned tokenizer/digest. keep_alive=-1 удерживает RAM; после остановки API владелец может явно unload только эту модель. Не завершать чужие процессы/не удалять volumes. Счётчики process-local, не customer-resolution rate. HA/load SLO не заявлены.
