# K-Beauty AI Support

Интеллектуальная система поддержки покупателей интернет-магазина косметики. Назначение: ответы по доставке, возвратам, оплате, бонусной программе и каталогу с проверяемыми источниками.

## Статус и возможности

Версия 0.4.0 реализует подготовку источников, dense embeddings BAAI/bge-m3 и семантический поиск с источниками в Qdrant Server. Индекс содержит 20 векторов: 11 разделов политик и 9 товаров; точные характеристики и цены сохраняются в payload. Данные версии 1.1 относятся к вымышленному магазину, а не к подтверждённым условиям действующего бизнеса.

Публикация нового поколения атомарно переключает alias после проверки всех ID, payload и векторов. Повторная загрузка проверяется как no-op. Проверены настоящий Qdrant Server, частичная загрузка, повтор, сохранность после restart и поиск. [Отчёт Блока 2](docs/block-2-results.md).

BM25, RRF, reranking, LLM и HTTP API остаются следующими этапами. Качество ответов ассистента пока не оценивалось. Готовность к промышленной эксплуатации не заявляется.

## Архитектура и стек

Текущий indexing: sources → validation → chunks → tokenizer gate → dense → staging Qdrant → readback → atomic alias. Query: resolve alias once → dense query → Qdrant search → texts, scores, sources и точные product fields.

Python 3.12, PyYAML 6.0.2, Pytest 8.4.1, Qdrant client/server 1.15.1. Dense: официальный FP32 ONNX-export BAAI/bge-m3, revision `5617a9f61b028005a4858fdac845db406aefb181`, 1024 измерения, CLS + L2, Cosine, CPU, batch=1. ONNX Runtime 1.31.0, tokenizers 0.23.3, NumPy 2.5.4; проверенные SHA-256 файлов в `src/kbeauty_support/retrieval/bge-m3.lock.json`. FastEmbed 0.7.3 остаётся зависимостью будущей sparse-стадии: эта версия не содержит bge-m3 в реестре. FastAPI/LLM пока не запускаются.

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

Блок 1 принят. Реализация и проверки Блока 2 представлены на приёмку; Блок 3 не начат. Source export остаётся неизменным; token counts и vectors находятся в отдельном dense artifact.

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

Recall@3=0,734615; Recall@5=0,820513 на 13 замороженных запросах. Это macro recall источников, а не точность денежных расчётов или ответов LLM. Составные вопросы с несколькими товарами теряют источники: dense baseline требует дальнейшей работы. [Полные результаты](docs/block-2-retrieval-results.json).
