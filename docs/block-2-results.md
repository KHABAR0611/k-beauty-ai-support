# Проверка Dense Embeddings & Qdrant Indexing 0.4.0

Дата:19.10.2026. База:b252ca3, бизнес-данные1.1. Реализация Блока2 завершена и представлена на приёмку. Блок3 не начат. Настоящая интеграция Qdrant Server проверена.

## Модель и ресурсы

- CPU: Intel Core i5-3470S @2.90GHz,4 ядра/4 потока; encoder CPUExecutionProvider,2 intra-op threads, batch1.
- RAM:8 325 792KiB видимой памяти, при исходной проверке свободно2 735 964KiB. Во время первого model run было свободно около650MiB; это одиночный замер, не профиль peak memory. GPU:NVIDIA GeForce GTX660M, WMI сообщил512MiB adapter memory; nvidia-smi не найден. GPU inference не использовался и не проверялся.
- BAAI/bge-m3, revision5617a9f61b028005a4858fdac845db406aefb181, официальный FP32 ONNX. Все7 файлов проверены SHA-256; основной внешний weights file2 266 820 608bytes. CLS+L2,1024 dimensions, limit8192, no truncation. [Назначение и multilingual support модели](https://huggingface.co/BAAI/bge-m3), [официальный CLS config](https://huggingface.co/BAAI/bge-m3/blob/5617a9f61b028005a4858fdac845db406aefb181/1_Pooling/config.json).
- Все20 чанков:140–268 tokens с special tokens, полный [замер](block-2-token-counts.json). Политики и товары не дробились ради модели.
- Python3.12.14; ONNX Runtime1.31.0, tokenizers0.23.3, NumPy2.5.4, Qdrant client/server1.15.1. [Полный Windows lock37 пакетов](../requirements/dense-test.lock) установлен в пустой venv, pip check успешен. FastEmbed0.7.3 не содержит bge-m3, поэтому для dense используется прямой ONNX adapter; новый checkpoint не подменял утверждённую модель.
- Полное повторное вычисление20 embeddings в чистом окружении заняло91.094s вместе с проверкой files/session startup/export. Это единичный batch run, не latency/SLA benchmark. Получены байт-в-байт одинаковые artifact files; другие CPU/OS не проверены.

Более лёгкая альтернатива для отдельного согласования — intfloat/multilingual-e5-small,384d/max512 с query/passage prefixes. Она не использовалась и не сравнивалась: изменение модели требует новой коллекции и оценки, а меньшая размерность не гарантирует достаточное качество. Текущая bge-m3 выполняется на данном CPU, но требует запаса памяти и ограниченной параллельности.

## Конфигурация и публикация

Индекс:kbeauty_dense_2876d48f2f3195816de340f42faa6c37ab24dd9d8fde1abc04eef4c1e9837670; alias:kbeauty_active. Named vector:dense, размер1024, metric:Cosine,20 points (11 policies+9 products), on_disk_payload=true. Стандартные HNSW/optimizer настройки1.15.1; при20 points корпус мал и обычно сканируется напрямую.

Payload содержит полный текст, source/section/type/version/product_id, source/chunk hashes, реальные token_count/tokenizer_id, полный product object, price_kopecks/currency и index descriptor. [Сводка реальных векторов](../examples/dense-summary.json). Source preparation generation f62c8bbe398110d2010ca66d2a314cd692fbf43861317f1b38bc12157d22e223 сохранена без изменений.

Публикация проверяет IDs/count/full payload/vector readback/search smoke, затем атомарно меняет alias. Неизменный manifest — verified no-op. Изменения/удаления дают новое полное поколение; старое остаётся для rollback. При injected interruption после4 records active index оставался прежним с20 records; повтор успешно завершил19-record test generation. Тестовое изменение изолировано уникальным integration alias и не меняет data/ или product alias. Query фиксирует physical collection до кодирования; unit test переключает alias в середине query и подтверждает отсутствие смешивания.

## Фактически выполненные проверки

- 114 unit/regression tests,0 failures/errors/skips в чистой venv. Сохраняются проверки всех12 бизнес-сценариев и ограничений1.1.
- 5 real Qdrant Server integration tests,0 failures/errors/skips: health/readiness,20 real1024d vectors и exact payload, idempotency, partial upsert+resume, отказ readback до alias, restart persistence.
- Повторные real embeddings байт-в-байт совпали; artifact SHA-256:70f6251d209bb5977571ce509bdb52d52375da569c4765b1b668d4a11c2ac31c.
- Самостоятельный CLI search через реальную модель/Server вернул KB-005 первым для запроса KB-005.
- Docker29.8.0, Compose5.5.1, Qdrant1.15.1. Engine работает. /healthz и /readyz200 до/послеrestart; реальные vectors/payload/alias сохранены в named volume kbeauty-review-check_qdrant_storage, loopback6394.
- Исходныеdata/ и business acceptance fixture/12 вопросов не менялись относительноb252ca3. Исходный архив не используется как рабочая копия.
- JSON evidence: [tests](block-2-test-results.json), [reproduction](block-2-reproduction.json), [infra smoke](block-2-docker-result.json).

## Dense retrieval: заранее размеченные источники

13 запросов зафиксированы commit1003d53 до первого поиска. SHA-256 labels:d7b1bbd56f943e1f9e56255b6a7fa822965ec8b480a38c6ec7a4660f848573cd. Эталон не менялся по результатам. Для каждого query Recall@k=число найденных релевантных source sections/общее число relevant sections, затем среднее по13 queries.

**Recall@3=0.734615; Recall@5=0.820513.** Теоретический macro ceiling фиксированного k:0.842308/0.974359, поскольку два composite cases требуют6 sections. Это не нормализованный на ceiling показатель и не оценка качества LLM. T11 и отсутствие retinol/медицинская частьT12 требуют других проверок; они явно исключены из retrieval recall, а не объявлены пройденными.

| Query | Top5 sections | Recall@3 | Recall@5 |
|---|---|---:|---:|
| R01 | DR-02, PL-03, PL-05, DR-01, PL-02 | 0.500 | 1.000 |
| R02 | DR-02, PL-01, KB-007, PL-02, PL-03 | 0.200 | 0.200 |
| R03 | PL-02, PL-05, DR-02, PL-03, DR-01 | 0.500 | 0.667 |
| R04 | PL-04, PL-03, PL-05, KB-007, PL-02 | 0.500 | 0.500 |
| R05 | PL-02, PL-05, PL-03, PL-04, PL-01 | 0.600 | 0.800 |
| R06 | PL-03, PL-05, PL-04, DR-02, DR-06 | 0.750 | 1.000 |
| R07 | DR-05, DR-06, DR-04, DR-02, PL-01 | 1.000 | 1.000 |
| R08 | DR-05, DR-04, DR-06, KB-003, DR-03 | 1.000 | 1.000 |
| R09 | KB-004, KB-008, KB-006, KB-009, KB-001 | 1.000 | 1.000 |
| R10 | PL-01, DR-01, DR-02, PL-05, DR-05 | 0.500 | 0.500 |
| R12 | PL-01, DR-02, PL-05, DR-04, PL-04 | 1.000 | 1.000 |
| R13 | DR-05, DR-06, DR-03, DR-04, PL-03 | 1.000 | 1.000 |
| R14 | KB-005, KB-007, KB-002, KB-004, KB-003 | 1.000 | 1.000 |

Примеры:

- Успех R08: «Получила сыворотку три дня назад, вскрыла и обнаружила повреждение флакона. Уже прошло48 часов. Мне откажут?» → DR-05 первым; relevant recall@3/5=1.
- Неудача R02: составной вопрос о KB-001/006/009 и доставке в ПВЗ → DR-02, PL-01, KB-007, PL-02, PL-03. Найдена доставка, но не три нужных товара и не сборка: recall@5=0.2. Похожий денежный/доставочный контекст вытесняет точные product sources. Эталоны не сокращались для улучшения цифры.
- Русская перефразировка R13: «Развернула посылку только на третий день, а баночка разбита. Срок жалобы уже вышел?» → DR-05 первым, recall@3/5=1.
- Точный артикул R14: «KB-005» → KB-005 первым, затем KB-007, KB-002, KB-004, KB-003. Это успешный пример, не гарантия точного SKU lookup для произвольного query; точная проверка каталога остаётся необходимой.

Полные scores/IDs/источники и frozen relevance sets: [retrieval results](block-2-retrieval-results.json). Нет BM25/RRF/reranking, query decomposition или LLM. Эти результаты — неизменённый dense baseline для сравнения после отдельной приёмки.

## Проблемы и исправления

1. Native Docker pull обрывался на auth/CDN через текущий proxy route. Host direct requests проходили. Официальные manifest/config/layers получены через Registry API по TLS и проверены SHA-256, затем docker load; Compose startup успешно использовал cache. Точный неисправный узел proxy/CDN не установлен, системные proxy/DNS не менялись. Глобальное исправление native pull не заявляется. [Provenance](block-2-image-provenance.json), воспроизводимый fallback: infrastructure/cache_qdrant_image.py --direct.
2. Docker29/containerd при docker-save import синтезирует новый image ID. Вместо ошибочного сравнения imageID=configDigest проверяются platform, все RootFS diff_ids и runtime config относительно проверенного официального config blob. Добавлены positive/negative regression tests.
3. Системный proxy затрагивал и локальные HTTP probes: loopback Qdrant probes/SDK теперь используют прямое соединение. Desktop settings не менялись.
4. Decimal-oriented source serializer намеренно отвергает floats; dense artifacts получили отдельный finite-float serializer. Денежные правила/исходники не менялись.
5. QdrantClient1.15.1 не поддерживает context manager; используется closing. UTF-8 JSON stdout явно кодируется bytes, независимо от Windows cp1251. Dependency closure включает HTTP/2 extras; чистая установка выявила пропуск до исправления.
6. Timeout Docker CLI на Windows может оставить plugin с наследованными pipes. Infra smoke ограничивает время и завершает только своё дочернее дерево.

## Ограничения и следующий gate

Один локальный publisher; нет distributed CAS, HA, restore drills, power-loss проверки, нагрузочных тестов или security/dependency audit. Старые physical generations и тестовые collections сохраняются, GC не реализован. Показатели малого13-query набора не доказывают обобщение, а CPU timing не задаёт SLA. Другие ОС/CPU/GPU и установка из GitHub ещё не проверены; локальный clone проверяется отдельно при передаче.

Нет API/LLM и end-to-end ответов; денежные регрессии не означают, что retrieval всегда нашёл все необходимые правила. Для Блока3 требуется приёмка владельца и согласование hybrid/retrieval scope с сохранением baseline; автоматически переходить к нему нельзя. Remote не настроен, GitHub push не выполнялся.
