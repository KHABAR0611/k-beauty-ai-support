# Исторический отчёт для данных1.0

Ниже сохранены результаты предыдущей поставки. Действующая версия данных1.1 и результаты повторной приёмки — в [business-review-results.md](business-review-results.md). Старые денежные значения и fingerprint ниже не являются текущим эталоном.

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

Публичная история создана отдельно, прежняя .git не импортирована. Исходный архив проверен по HEAD, Git status и SHA-256 всех 37 отслеживаемых файлов: сохранён без изменений. Root commit `eddc7e9389810e681a20e74ad44edfa45a4ec4be` не имеет родителей. Проверены имена и содержимое всех 46 файлов этого коммита, а также техническая author identity: чувствительных находок по проверенным шаблонам и просмотру нет. Это не универсальная гарантия regex-сканера и не полный security audit.

Выполнен независимый `git clone --no-local`, создано чистое Python 3.12 окружение. Runtime/test зависимости установлены из локального wheel cache в точных версиях lock; `pip check` успешен. В клоне **66 tests passed, 0 skipped**, реальный module CLI dry-run и export завершились с exit 0. Все четыре выходных файла совпали с основной копией побайтно, fingerprint одинаков. Код, тесты и бизнес-данные после clone smoke не изменялись; уточнены только инструкции запуска/проверки и состав source/test lock.

Online установка при clone smoke была заблокирована сбросом TLS соединения с PyPI; поэтому проверен описанный в README source/module режим с offline wheelhouse. Build backend не нужен этому режиму и исключён из source/test lock, оставаясь pinned в pyproject.toml для optional package installation. Editable package install версии 0.3.0 в чистой среде, Linux и Docker build не подтверждены.

GitHub remote не указан, авторизация не подтверждена, push не выполнялся. CI workflow подготовлен, но на GitHub ещё не запускался. Основная активная версия — этот checkout; исходный репозиторий остаётся архивом.
