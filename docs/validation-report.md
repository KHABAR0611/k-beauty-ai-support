# Проверка Data Ingestion, Chunking & Metadata 0.3.0

Дата: 19.10.2026. Среда: Python 3.12.14, Pytest 8.4.1, Windows. Подготовка источников не требует сети, Docker или моделей.

## Подтверждено

- Реальный CLI dry-run и экспорт завершились с exit 0: **20 чанков = 11 policy sections + 9 товаров**. Fingerprint `9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853`.
- **66 tests passed, 0 failures, 0 skipped**. Включены 27 ранее существовавших проверок и 39 проверок ingestion/export.
- Проверены все товары и точные поля без смешения; критические таблицы/пороги/исключения; полный текст каждого раздела; metadata/UUID; byte-deterministic repeat; изменения и удаление товара; Decimal без потери копеек; hashes и изменение CRLF.
- Отрицательные проверки: JSON syntax/duplicate keys/NaN/Infinity; неправильные цены, характеристики, даты и версии; YAML duplicate keys, пустые/неизвестные/повторные разделы; UTF-8, size limit, traversal, реальный Windows junction, input/output overlap, semantic-unit limit без truncation.
- Проверены writer lock, integrity refusal для повреждённого поколения, PermissionError/I/O/interrupt при записи, отказ замены CURRENT и повтор после сбоя. Прежний CURRENT остаётся неизменным.
- Семь реальных чанков с metadata экспортированы в examples/prepared-chunks.jsonl и docs/chunk-examples.md. Пример manifest относится ко всем 20 чанкам.
- Все 12 эталонных вопросов сопоставлены с источниками; существенных противоречий не обнаружено. Подробности в acceptance-consistency.md. Денежные проверки подтверждают эталоны, не реализацию будущего calculator/API.

## Docker: реальные проверки

Docker CLI 29.8.0 и Compose v5.5.1 доступны. Docker Desktop штатно запущен, Engine 29.8.0 отвечает. `docker compose config --quiet` успешен.

Реальная попытка `docker compose -p kbeauty-block1-verification up -d qdrant` выполнена. Запуск заблокирован pull образа qdrant/qdrant:v1.15.1: обращение к https://auth.docker.io/token завершается EOF. Повторные попытки после запуска Desktop и подтверждения доступности Docker дали ту же ошибку. Это проблема получения образа, не отсутствие установленного Docker; точная сетевая причина не установлена.

Qdrant-контейнер не запущен. Поэтому health/readiness и persistence после restart не проверены; успешный статус им не приписывается. Существующие контейнеры, образы и volumes не удалялись, down -v не применялся. Бизнес-данные/embeddings в Qdrant не загружались. Для продолжения инфраструктурной проверки нужен доступ Engine к registry/auth Docker Hub.

## Границы

Source export имеет status=validated, stage=source_preparation, embedding_ready=false. Tokenizer и модель не выбраны, token_count=null. Token budget, revisions, dense/BM25 vectors, Qdrant publishing/rollback, hybrid retrieval, reranking, LLM и HTTP API не проверялись и не реализованы этим блоком. Power-loss durability, Linux runner, backup/restore и security scan остаются непроверенными.

## Git и воспроизведение

Публичная история создаётся отдельно, прежняя .git не импортируется. Исходный архив проверен по HEAD, Git status и SHA-256 отслеживаемых файлов: сохранён без изменений. Новый root commit проверяется по именам и содержимому blobs на secrets, PII, локальные абсолютные пути и личные материалы; результат проверки и clone smoke будут зафиксированы перед передачей.

GitHub remote не указан, авторизация не подтверждена, push не выполнялся. CI workflow подготовлен, но на GitHub ещё не запускался. Основная активная версия — этот checkout; исходный репозиторий остаётся архивом.
