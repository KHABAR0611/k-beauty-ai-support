# Проверки reranking

## Локальные контракты

Установить `requirements/rerank-test.lock`, установить `PYTHONPATH=src`, выполнить `python -m pytest`. Модели и Server для unit suite не нужны. Синтетический scorer проверяет ordering/fallback/generation safety, но не используется для quality scores. Все quality traces получены настоящим pinned ONNX checkpoint.

Проверяются: неполный/NaN/Inf/bool score batch, initialization/inference failures, неизменность payload и original score, точное сохранение Hybrid top-k при disabled/failure, отсутствие model load при disabled, stable equal-logit ties, пустой pool, invalid depths, retrieval error propagation, смена поколения во время scoring без повторного чтения, неизменность исходных qrels. Старые тесты источников, бизнес-правил, 9 товаров и atomic indexing сохраняются.

## Настоящие модели и Qdrant Server

Тесты используют подготовленные ingestion/dense/hybrid artifacts и два проверенных model caches. Должен быть доступен настоящий Qdrant Server1.15.1 с Hybrid active alias. Секрет передаётся через окружение, не аргумент командной строки или Git. Пример переменных (значения путей задаёт оператор):

```powershell
$env:PYTHONPATH = "src"
$env:QDRANT_URL = "http://127.0.0.1:6394"
$env:QDRANT_API_KEY = "<YOUR_LOCAL_QDRANT_KEY>"
$env:KBEAUTY_MODEL_DIR = "model-cache/bge-m3/5617a9f61b028005a4858fdac845db406aefb181"
$env:KBEAUTY_RERANKER_DIR = "model-cache/mmarco-minilm/1427fd652930e4ba29e8149678df786c240d8825"
$env:KBEAUTY_EMBEDDING_ARTIFACT = "artifacts/dense/<DENSE_GENERATION>.json"
$env:KBEAUTY_HYBRID_ARTIFACT = "artifacts/hybrid/<HYBRID_GENERATION>.json"
$env:KBEAUTY_SERVER_TESTS = "1"
$env:KBEAUTY_HYBRID_SERVER_TESTS = "1"
$env:KBEAUTY_RERANK_SERVER_TESTS = "1"
# Restart проверяет только изолированный Compose project kbeauty-review-check/port6394.
# Не задавать для чужого deployment; существующие volumes не удаляются.
$env:KBEAUTY_ALLOW_SMOKE_RESTART = "1"
python -m pytest tests/integration -q
```

Тесты Блоков2/3 создают собственные уникальные aliases/collections. Reranker suite читает активное поколение и проверяет реальные pair logits, одинаковый порядок в повторах, сохранность source/product/price, disabled/failure эквивалентность Hybrid, отклонение отсутствующего/неутверждённого cache, длины всех23×20 пар и сохранение полного point payload/двух vectors/alias/результатов после restart. Expected quality не встроено в integration assertions: отдельный benchmark показывает и неудачи модели.

Readiness ожидается с bounded monotonic deadline180s. Рестарт существующего isolated project не удаляет контейнеры, образы, коллекции или named volume. Контракт restart не является проверкой hardware power loss или backup restore. Не выполнять `down -v` для данных.

## Оценка качества и cold start

Команда `rerank-compare` описана в README. В stdout JSON, в stderr safe progress logs. Исходные13 qrels имеют SHA-256 `d7b1bbd56f943e1f9e56255b6a7fa822965ec8b480a38c6ec7a4660f848573cd`. Дополнительные10 были зафиксированы коммитом a82a9ee до inference. Планы и исходные Block3 traces не перезаписаны. Warm models, no query/score cache, 3 repetitions, rotating mode order; все результаты и memory snapshots доступны в development/holdout JSON. Cold initialization измерена отдельно. Это последовательный desktop benchmark, не изолированный нагрузочный тест и не service SLO. Во время начальной загрузки development runtime также выполнялся unit suite; независимый holdout запускался без него.

Process working set/peak/private commit измерены через Windows GetProcessMemoryInfo; Linux adapter поддерживает `/proc/self/status`, но Linux inference здесь не проверен. GPU не использовался. CI source/contracts не объявляется проверкой настоящих весов или Server.

Фактические counts и имена выполненных тестов: [test-results](block-4-test-results.json). Проверка clone и Docker: [runtime-check](block-4-runtime-check.json). Raw JUnit остаётся локальным, поскольку содержит hostname и абсолютные пути.
