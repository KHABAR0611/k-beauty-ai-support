# Dense embedding и публикация индекса

## Область поставки

Данные 1.1 и 12 бизнес-эталонов неизменны относительно b252ca3. Вход — проверенное поколение экспорта Блока 1, 20 chunks. Выход — отдельный immutable dense artifact и опубликованное поколение Qdrant. Реализованы только dense-векторы и поиск источников; sparse/RRF/rerank/LLM/API не вызываются.

## Установка и модель

На Windows x64 с Python 3.12 установите `requirements/dense-test.lock`; это полный набор из37 пакетов, включая HTTP/2 extras клиента. Другие платформы не проверены; перенос требует собственного lock. Для установки package entry points используйте `pip install -e .[dense,test]`; source launch через PYTHONPATH не требует build backend.

1. Выполните ingestion по README.
2. `python infrastructure/download_dense_model.py` загружает только семь файлов официального ONNX checkpoint, проверяет размер и все SHA-256. `--direct` отключает прокси только у downloader. Нет remote Python/trust_remote_code, внешних API embeddings или автоматической смены модели. При сбое retained .part не считается готовым; следующая попытка скачивает файл заново. Один downloader на cache.
3. `python -m kbeauty_support.retrieval.cli tokens` проверяет все chunks с special tokens, без truncation. Manifest, файлы и source text hashes проверяются до кодирования.
4. `python -m kbeauty_support.retrieval.cli embed` пишет `artifacts/dense/<generation>.json`. Generation зависит от source generation, catalog hash, revision, файлов, pooling, normalization, threads и runtime versions. Artifact защищён content hash. Сам source export не изменяется.

Encoder: BAAI/bge-m3, pinned revision 5617a9f61b028005a4858fdac845db406aefb181; официальный ONNX FP32, input_ids/attention_mask, CLS последнего hidden state, L2 normalization, CPUExecutionProvider, intra threads2/inter1, batch1. Размерность1024; токены ≤8192. Encoder для query идентичен encoder индекса, без разных prefixes. [Model card](https://huggingface.co/BAAI/bge-m3), [CLS config](https://huggingface.co/BAAI/bge-m3/blob/5617a9f61b028005a4858fdac845db406aefb181/1_Pooling/config.json).

## Qdrant Server

Создайте .env из .env.example, замените ключ и запустите `docker compose up -d qdrant`. Затем экспортируйте в environment те же QDRANT_URL и QDRANT_API_KEY. QDRANT_COLLECTION_ALIAS по умолчанию kbeauty_active. CLI не загружает .env; ключ не передаётся аргументом. Удалённый сервер требует HTTPS, локальный HTTP допускается только на loopback. Python SDK не использует системный proxy для Qdrant; прокси-конфигурация remote deployment требует отдельного рассмотрения.

Если native pull обрывается на CDN, `python infrastructure/cache_qdrant_image.py --direct` получает официальный linux/amd64 manifest по закреплённому digest, проверяет каждый blob и выполняет docker load. Это необязательная процедура для проверенной платформы linux/amd64 Engine; образ другой архитектуры автоматически не подменяется. Настройки Desktop, DNS, proxy и существующие данные не меняются. Bearer token и signed URLs не логируются. Затем повторите Compose startup. Downloader выполняет одну попытку на объект с timeout, без бесконечных повторов.

`index --artifact artifacts/dense/<generation>.json` создаёт `kbeauty_dense_<generation>`, named vector dense, Cosine,1024, on_disk_payload=true, стандартные HNSW/optimizer настройки Qdrant1.15.1. На20 points порог HNSW не достигается: это маленький dense corpus, не benchmark ANN.

Upsert выполняется batch4, wait=true. Все ID, count, полные payload и vector readback сверяются. Выполняется search smoke, затем одна alias transaction. Старое поколение не удаляется. Тот же manifest проверяется как no-op; после interrupted staging повтор завершает upsert. Изменённые и удалённые записи отражаются новым полным поколением, поэтому в active generation нет stale records. Старые physical collections остаются для rollback; retention/GC — отдельно.

## Поиск и оценка

`search --query "KB-005" --limit 5` возвращает collection/generation, score, text, metadata и точные product поля. Alias разрешается один раз; query остаётся на одной physical collection даже при переключении. Model signature должна совпадать. Score не является вероятностью правильного ответа.

`evaluate` читает frozen `tests/fixtures/retrieval-qrels-v1.1.json`, запрашивает top5 и считает macro Recall@3/5: усреднённую долю найденных релевантных source sections для каждого вопроса. Оригинальные12 acceptance cases остаются эталонами последующей проверки системы. T11 и медицинская/отрицательная catalog частьT12 не оцениваются retrieval recall. Для T12 отдельно измеряется поиск платёжной политики. Добавлены paraphrase и exact SKU. Composite cases с6 источниками имеют ceiling@5=5/6; их не сокращают ради улучшения метрики. Набор небольшой и не независимый holdout после будущей настройки.

## Тестирование

`python -m pytest` запускает unit/regression suite; локальный режим Qdrant проверяет контракт, не заменяет Server. Явная серверная проверка:

```powershell
python infrastructure/verify_qdrant.py
# Этот smoke создаёт isolated project kbeauty-review-check, port6394.
# Экспортируйте QDRANT_API_KEY из ignored artifacts/docker-review/connection.env.
$env:QDRANT_URL = "http://127.0.0.1:6394"
$env:KBEAUTY_SERVER_TESTS = "1"
$env:KBEAUTY_EMBEDDING_ARTIFACT = "artifacts/dense/<GENERATION>.json"
$env:KBEAUTY_ALLOW_SMOKE_RESTART = "1"
python -m pytest tests/integration/test_qdrant_server.py -q
```

Server tests используют отдельный уникальный alias, реальные1024d embeddings, synthetic modified generation для fault injection; источники data/ и product alias не меняются. Проверяют health/readiness, idempotency, partial upsert, readback failure, удаление из active поколения и restart persistence. Экспериментальные коллекции сохраняются; тесты не удаляют контейнеры, образы, volumes или прежние collections. При отсутствии opt-in suite явно skipped; это не положительный результат интеграции.

## Ограничения надёжности

Один publisher на одной машине с фиксированным output-dir и O_EXCL lock. Multi-host writers и распределённый CAS не поддержаны. В случае stale lock сначала подтвердите отсутствие writer, затем снимите lock вручную. При timeout alias transaction сначала проверьте alias; повтор безопасно сверит состояние. Не удаляйте неполное поколение, пока writer работает. Failed staging никогда не переключает alias. Нет автоматического retry storm, silent degradation, GC, backup/restore, HA или гарантий после power loss.

CLI выдаёт UTF-8 JSON в stdout, JSON logs в stderr без текста вопросов, документов, API keys и абсолютных путей. Exit0=успех,2=ошибка,130=прерывание. SDK exceptions логируются только по категории. Ошибка операции требует проверки server/alias и исходного artifact; traceback не публикуется.
