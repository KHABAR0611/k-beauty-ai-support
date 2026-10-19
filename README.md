# K-Beauty AI Support

Интеллектуальная система поддержки покупателей интернет-магазина косметики. Назначение: ответы по доставке, возвратам, оплате, бонусной программе и каталогу с проверяемыми источниками.

## Статус и возможности

Версия 0.3.0 реализует Data Ingestion, Chunking & Metadata: безопасное чтение трёх источников, строгую валидацию, структуру смысловых разделов, отдельные товарные документы, UUIDv5, SHA-256, детерминированный JSONL и атомарную публикацию подготовленных поколений на диске.

Текущий набор даёт **20 чанков: 11 разделов политик и 9 товаров**. Магазин, бренды и политики вымышлены; данные не являются подтверждёнными условиями действующего бизнеса. Цены — RUB за единицу.

Embeddings, загрузка в Qdrant, hybrid retrieval, reranking, LLM и HTTP API пока не реализованы. Экспорт проверен как source preparation; token_count=null, embedding_ready=false. Следующий обязательный gate — проверка длины токенизатором выбранной dense-модели, без молчаливого truncation. Готовность к промышленной эксплуатации не заявляется.

## Архитектура и стек

Indexing: sources → validation → structure-aware chunks/metadata → [следующий этап: dense + BM25 → Qdrant]. Query: FastAPI → dense/BM25 → RRF → reranking → context → LLM → sources. Точные цены и SKU сохраняются независимо от semantic similarity.

Python 3.12, PyYAML 6.0.2; Pytest 8.4.1. Сервисные зависимости закреплены отдельно: FastAPI 0.116.1, Uvicorn 0.35.0, Pydantic 2.11.7, Qdrant client/server 1.15.1; FastEmbed 0.7.3 — retrieval extra. Dense-модель, reranker и LLM ещё не выбраны. Ingestion не устанавливает и не вызывает модели.

[Архитектура](docs/rag-architecture.md) · [ADR](docs/decision-log.md) · [Контракты](docs/component-contracts.md) · [Эксплуатация](docs/operations.md)

## Установка и запуск

Требуются Python 3.12 и доступ к реестру пакетов. После `git clone <REPOSITORY_URL>` перейдите в каталог репозитория:

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

.env для ingestion не требуется. В .env.example заданы переменные будущего сервиса и текущего Compose; реальные ключи не коммитятся. HTTP API ещё отсутствует, его [контракт](docs/api.md) описывает будущую границу. Нет реальных заказов, платежей, возвратов денег или медицинских назначений.

## Docker

Docker не нужен для source preparation. Для инфраструктуры скопируйте .env.example в .env и задайте собственный локальный QDRANT_API_KEY:

```sh
docker compose config --quiet
docker compose up -d qdrant
docker compose --profile tools run --rm --build source-audit
```

Qdrant слушает loopback; данные в named volume qdrant_storage. Не используйте down -v для данных, которые нужно сохранить. Source-audit — отдельная офлайн-задача, не API и не model worker. Фактический статус Engine/health/persistence отдельно указан в [отчёте](docs/validation-report.md); валидная конфигурация не доказывает runtime.

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

[Примеры чанков](docs/chunk-examples.md) · [Результаты проверки](docs/validation-report.md) · [Спецификация Блока 1](docs/block-1-spec.md) · [Roadmap](docs/roadmap.md) · [Публикация](docs/github-setup.md)

Блок 2 начинается только после приёмки Блока 1: выбрать model/tokenizer revisions, проверить token budgets, реализовать encoders и проверяемый publish в Qdrant. До этого экспорт не считается embedding-ready.
