# K-Beauty AI Support

Интеллектуальная система поддержки покупателей интернет-магазина косметики. Назначение: ответы по доставке, возвратам, оплате, бонусной программе и каталогу с проверяемыми источниками.

## Статус и возможности

Версия0.6.0 реализует ingestion, dense embeddings, BM25, hybrid retrieval через RRF и optional multilingual reranking в настоящем Qdrant Server. Один point содержит dense и sparse представления одного исходного чанка. Всего20 points:11 разделов политик и9 товаров, с полными текстами, метаданными и точными характеристиками.

Данные1.1 относятся к вымышленному магазину. Публикация поколения атомарна после проверки всех ID, payload и обоих векторов. Доступны независимые режимы dense-only, BM25-only и hybrid. [Отчёт Блока3](docs/block-3-results.md) содержит baseline, все13 запросов, метрики, latency и регрессии.

Reranker доступен как явно включаемый режим. LLM и HTTP API не реализованы. Retrieval recall не является качеством ответов. Готовность к промышленной эксплуатации не заявляется. Блоки2/3 приняты; результаты Блока4 представлены для инженерной приёмки. Primary rerank pool10 ухудшает полноту@5 на исходном наборе, поэтому рекомендуется сохранять Hybrid до отдельного решения о конфигурации.

## Архитектура и стек

Текущий indexing: sources → validation → chunks → tokenizer gate → dense+BM25 → staging Qdrant → readback → atomic alias. Query: resolve alias once → dense/BM25 query → Qdrant search или RRF → texts, scores, sources и точные product fields.

Python 3.12, PyYAML 6.0.2, Pytest 8.4.1, Qdrant client/server 1.15.1. Dense: официальный FP32 ONNX-export BAAI/bge-m3, revision `5617a9f61b028005a4858fdac845db406aefb181`, 1024 измерения, CLS + L2, Cosine, CPU, batch=1. ONNX Runtime 1.31.0, tokenizers 0.23.3, NumPy 2.5.4; проверенные SHA-256 файлов в `src/kbeauty_support/retrieval/bge-m3.lock.json`. FastEmbed0.7.3 реализует Qdrant/bm25 с русским Snowball stemmer и закреплённым UTF-8 stopword asset. BGE-M3 по-прежнему использует отдельный официальный ONNX adapter. FastAPI/LLM пока не запускаются.

[Архитектура](docs/rag-architecture.md) · [ADR](docs/decision-log.md) · [Контракты](docs/component-contracts.md) · [Эксплуатация](docs/operations.md)

## Установка и запуск

Требуются Python 3.12 и доступ к реестру пакетов. После `git clone https://github.com/KHABAR0611/k-beauty-ai-support.git` перейдите в каталог репозитория:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell:
.venv\Scripts\Activate.ps1
python -m pip install -r requirements/ingestion-test.lock
# PowerShell:
$env:PYTHONPATH = "src"
# Linux/macOS: export PYTHONPATH=src
python -m pytest
python -m kbeauty_support.ingestion.cli --data-dir data --output-dir artifacts/ingestion --dry-run
python -m kbeauty_support.ingestion.cli --data-dir data --output-dir artifacts/ingestion
```

Для установки entry points дополнительно выполните `python -m pip install -e .`: build backend закреплён в pyproject.toml и загружается отдельно. Основной запуск исходников выше не требует build backend. `kbeauty-ingest` эквивалентен модулю ingestion.cli; старый `kbeauty-audit` сохраняется для совместимости. Ingestion выполняет более строгую проверку metadata, JSON и файловой безопасности.

При отсутствии доступа к PyPI допускается установка тех же версий из заранее полученного wheelhouse: `python -m pip install --no-index --find-links <WHEELHOUSE> -r requirements/ingestion-test.lock`. Wheelhouse должен соответствовать Python/ОС (в текущей проверке Windows x64, Python 3.12); он не включается в Git.

## Результат экспорта

```text
artifacts/ingestion/
  CURRENT                         fingerprint активного подготовленного поколения
  generations/<fingerprint>/
    chunks.jsonl                  id, text, metadata; товары также содержат exact product
    catalog.snapshot.json         полный канонический JSON без потери Decimal
    manifest.json                 версии, hashes, counts, stage, embedding gate
    validation.json               результат source validation
```

Читатель сначала читает CURRENT один раз, затем все четыре файла из указанного поколения. Идентичные входы дают одинаковые байты; повторный запуск проверяет существующее поколение и не создаёт дубли. Новые/удалённые записи отражаются в новом поколении, прежнее остаётся доступным. ID chunk зависит от источника, логического раздела и версии схемы/chunker, а не от текста. Source hash считается по исходным байтам, chunk hash — по нормализованному UTF-8/LF тексту. Изменение CRLF может изменить fingerprint, сохранив текст чанков.

Секции сохраняются целиком, без overlap и обрезания условий. 12 000 символов на смысловую единицу — защитный предел, не модельный token limit. Превышение вызывает явную ошибку. Стабильные UUID пригодны для будущего Qdrant upsert; генерация здесь — подготовка файлов, не опубликованный Qdrant index.

## Ошибки, конфигурация и безопасность

CLI: --data-dir, --output-dir, --dry-run. Dry-run ничего не записывает и не требует сети. Exit 0 — успех, 2 — ошибка источника/конфигурации, 3 — I/O или занятый writer lock, 130 — прерывание. JSON events выводятся в stderr, итог — в stdout. Логи содержат job_id, этап и результат, без тела документов и абсолютных путей.

Allowlist — только три файла data/. UTF-8, JSON/YAML duplicate keys, версии, provenance, SKU, цены и характеристики проверяются. Symlinks/junctions и пересечение input/output запрещены. Каждый источник ≤5 MiB. Ошибка записи не переключает CURRENT. После аварийного завершения stale .ingest.lock требует проверки отсутствия writer перед ручным снятием; автоматического захвата lock нет. Папки .tmp-* не читаются как поколения.

.env для ingestion не требуется. В .env.example заданы переменные Compose и Qdrant CLI; реальные ключи не коммитятся. CLI читает environment, а не .env автоматически. HTTP API ещё отсутствует, его [контракт](docs/api.md) описывает будущую границу. Нет реальных заказов, платежей, возвратов денег или медицинских назначений.

## Docker

Docker не нужен для source preparation. Для инфраструктуры скопируйте .env.example в .env и задайте собственный локальный QDRANT_API_KEY:

```sh
docker compose config --quiet
docker compose up -d qdrant
docker compose --profile tools run --rm --build source-audit
```

Qdrant слушает loopback; данные в named volume qdrant_storage. Не используйте down -v для данных, которые нужно сохранить. Source-audit — отдельная офлайн-задача, не API и не model worker. Фактический статус Engine/health/persistence отдельно указан в [отчёте Блока 2](docs/block-2-results.md); валидная конфигурация не доказывает runtime.

## Структура, проверки и следующий этап

```text
data/                           политики и каталог
src/kbeauty_support/ingestion/   readers, validation, preparation, export, CLI
src/kbeauty_support/             contracts; api/retrieval/reranking/generation stubs
tests/unit/                     поведенческие проверки и денежные эталоны
tests/acceptance-tests.md        12 будущих e2e сценариев
examples/                       реальные подготовленные chunks и manifest
requirements/                   lock для ingestion/test
infrastructure/                 Dockerfile аудита
docs/                           ADR, спецификации, отчёты, API, эксплуатация
```

[Примеры чанков](docs/chunk-examples.md) · [Результаты повторной проверки](docs/business-review-results.md) · [Спецификация Блока 1](docs/block-1-spec.md) · [Roadmap](docs/roadmap.md) · [Публикация](docs/github-setup.md)

Блоки1–2 приняты. Dense/BM25/RRF реализованы; переход к reranking и LLM требует приёмки Блока3. Source export остаётся неизменным; token counts и vectors находятся в отдельном dense artifact.

Бизнес-данные версии1.1 пересмотрены по уточнению владельца: [аудит происхождения и зависимостей](docs/business-change-audit.md). Действующие правила определяются data/1.1 и ADR-016, а не историческим отчётом для1.0.

## Dense indexing и поиск

Полный пошаговый запуск и интеграционные проверки: [Блок 2](docs/block-2-spec.md). Установка проверенного набора Windows x64 / Python 3.12:

```powershell
python -m pip install -r requirements/dense-test.lock
$env:PYTHONPATH = "src"
python infrastructure/download_dense_model.py
# Если текущий прокси обрывает загрузку, доступен --direct только для этого процесса.
python -m kbeauty_support.retrieval.cli tokens
python -m kbeauty_support.retrieval.cli embed
$env:QDRANT_URL = "http://127.0.0.1:6333"
$env:QDRANT_API_KEY = "<YOUR_LOCAL_QDRANT_KEY>"
# Подставьте имя artifact из результата embed; модельные веса в Git не входят.
python -m kbeauty_support.retrieval.cli index --artifact artifacts/dense/<GENERATION>.json
python -m kbeauty_support.retrieval.cli search --query "Можно вернуть повреждённую косметику через три дня?"
python -m kbeauty_support.retrieval.cli evaluate
```

Загрузка модели требует около 2,3 ГБ на диске. На 8 ГБ RAM CPU-запуск возможен, но тяжёлый и медленный; держите batch=1 и не запускайте несколько encoder-процессов одновременно. Обязательный token gate измерил 140–268 токенов на chunk с special tokens при лимите 8192. Обрезание запрещено. Для другой модели, квантования или GPU требуется новый manifest и отдельная оценка.

Dense-only baseline: Recall@3=0,734615; Recall@5=0,820513 на13 замороженных запросах. Это macro recall источников, а не точность денежных расчётов или ответов LLM. Составные вопросы с несколькими товарами теряют источники: dense baseline требует дальнейшей работы. [Полные результаты](docs/block-2-retrieval-results.json).

## BM25 и Hybrid Search

Установите проверенный Windows/Python3.12 набор `requirements/hybrid-test.lock` (43 пакета). В editable installation также доступен extra `[hybrid,test]`. Модель BGE-M3, исходный ingestion export и dense artifact должны быть подготовлены по инструкции выше. Для BM25-only запроса веса BGE-M3 не загружаются.

```powershell
python -m pip install -r requirements/hybrid-test.lock
$env:PYTHONPATH = "src"
python -m kbeauty_support.retrieval.cli hybrid-build --artifact artifacts/dense/<DENSE_GENERATION>.json
python -m kbeauty_support.retrieval.cli index --artifact artifacts/hybrid/<HYBRID_GENERATION>.json
python -m kbeauty_support.retrieval.cli search --mode dense --query "KB-004"
python -m kbeauty_support.retrieval.cli search --mode bm25 --query "KB004"
python -m kbeauty_support.retrieval.cli search --mode hybrid --query "Первый заказ, WELCOME10 и бонусы, доставка в ПВЗ"
python -m kbeauty_support.retrieval.cli compare --repetitions 3 --prefetch 20
```

BM25: k1=1.2,b=0.75,avg_len=69.9 для текущего корпуса, IDF только на сервере. Русские словоформы обрабатывает stemming, а не лемматизация/перевод. NFKC, casefold, ё/е и KB-004/KB004 нормализуются одинаково при indexing/query. Подробности, лицензия assets и ограничения: [русский BM25](docs/bm25-russian.md).

Hybrid использует равные ветви с prefetch20 и серверный RRF Qdrant1.15.1. При равных итоговых scores применяется стабильный UUID tie-break до top-k. Hybrid увеличивает полноту@5 на текущем наборе, но имеет регрессии раннего ранжирования; победители и проигравшие опубликованы без изменения эталонов. Полное сравнение и результаты каждого запроса: [block-3-comparison.json](docs/block-3-comparison.json).

## Cross-encoder reranking

Используется `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision `1427fd652930e4ba29e8149678df786c240d8825`, Apache-2.0, официальный FP32 ONNX. Query и каждый полный документ кодируются совместно; raw logit задаёт порядок, а не вероятность ответа. Дополнительные runtime-пакеты не требуются: `requirements/rerank-test.lock` включает закреплённый hybrid lock. [Сравнение моделей](docs/reranker-model-selection.md), [результаты](docs/block-4-results.md), [все запросы](docs/block-4-query-results.md).

После подготовки и публикации hybrid artifact по предыдущим разделам:

```powershell
python -m pip install -r requirements/rerank-test.lock
python infrastructure/download_reranker.py
# При проблеме текущего прокси: --direct действует только на этот процесс.
python -m kbeauty_support.retrieval.cli search --mode rerank --candidate-pool 10 --limit 5 --query "Развернула посылку на третий день, баночка разбита"
python -m kbeauty_support.retrieval.cli search --mode rerank --disable-rerank --query "KB-005"
python -m kbeauty_support.retrieval.cli rerank-compare --pools 5,10,15 --repetitions 3
# Независимый holdout: только заранее выбранный pool10, не для настройки.
python -m kbeauty_support.retrieval.cli rerank-compare --pools 10 --labels tests/fixtures/retrieval-holdout-v1.1.json --repetitions 3
python -m pytest
```

Candidate pool1–20, final_k не больше pool, prefetch не меньше pool. По умолчанию pool10/final5/prefetch20; старые dense/BM25/hybrid команды сохранены, default CLI mode=dense не изменён. Режим rerank надо указать явно. Отключение не загружает cross-encoder и сохраняет исходный Hybrid top-k. Ошибка модели или пара больше512 токенов даёт тот же Hybrid top-k с `reranking.applied=false` и категорией fallback; неполная пересортировка не публикуется. Ошибка Qdrant остаётся ошибкой запроса. В stdout — UTF-8 JSON с timings, scores, sources и before/after positions; журналы в stderr не содержат query text.

Веса reranker занимают ещё около471 МБ на диске. CLI search загружает модели заново при каждом процессе; опубликованная warm latency относится к повторным запросам в одном процессе. Отдельный HTTP-процесс и warm readiness пока не реализованы. Память, стоимость rerank и случаи регрессии приведены в отчёте; GPU и конкурентная нагрузка не проверены. Pool5 улучшает ранние позиции на 13 запросах без изменения их состава top5, но не проверен на независимом holdout и не заменяет primary задним числом.

Unit/regression tests не скачивают модели. Real Server tests требуют явных opt-in переменных и подготовленных pinned caches, описанных в [проверках Блока4](docs/block-4-testing.md). CI проверяет contracts и источники; результаты реальных моделей/Server опубликованы отдельно.
