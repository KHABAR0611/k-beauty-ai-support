# Повторная архитектурная проверка — версия 0.3.1 / данные 1.1

## Итог бизнес-проверки

Четыре спорных значения присутствовали уже в первом доступном локальном commit de005cd (19.10.2026, 15:55 МСК), затем без смыслового изменения прошли через fa83298, eddc7e9 и ac18b91. Поздний переход с заявленных исходных условий на эти значения в доступном Git не обнаружен. Нельзя приписывать его Блоку 1 или выдумывать отсутствующее согласование.

По уточнению владельца восстановлены: доставка после promo и бонусов, совместимость WELCOME10 со списанием, KB-004=1890 ₽, KB-005=1590 ₽. Отдельно подтверждено: cap20% считается после промокода. Версия всех трёх источников1.1; остальные цены/характеристики неизменны по структурному сравнению с ac18b91. История и исходный архив не переписывались.

Полная таблица «когда/commit/основание/согласование/зависимости» — [business-change-audit.md](business-change-audit.md); выбранные факты из четырёх снимков — [business-history-evidence.json](business-history-evidence.json). ADR-004 superseded, действующее решение ADR-016. Более ранняя до-Git версия не доступна для независимой проверки; сопоставление Barrier Cream с KB-004 выполнено по единственному крему с керамидами.

## Проверки и результаты

**91 tests passed, 0 skipped**, Python3.12.14/Pytest8.4.1 на Windows. 66 исходных проверок актуализированы; добавлены24 бизнес-regression cases и1 проверка безопасной диагностики Docker. Ни один pass не используется как самостоятельное доказательство бизнес-согласования: эталон — уточнённые требования владельца.

Обновлены все12 expected records, статическая сверка sources/facts и отдельные денежные эталоны. T03=3532 ₽/156 бонусов; T05 promo-only=2500/112, bonus-only=2250/100, combined=2050/90 (списание450); T06=3150/140; T09 не находит крем≤1800, альтернатива KB-004 превышает бюджет на90. Остальные сценарии предметно неизменны. Прямая корзина со SPF отсутствовала среди12 сценариев; теперь цена1590 и подготовленный payload защищены отдельным regression test.

Проверены включительность порогов после реального списания, совместимость promo/bonus, cap после discount и его округление вниз, баланс/запрошенное количество, обе цены, отсутствие бюджетного крема, актуальность7 примеров/manifest, нечисловые границы и все12 ID/source mappings. Pricing reference находится только в tests, а не выдаётся за production calculator. T11/T12 всё ещё требуют будущих e2e проверок сервиса/LLM.

Реальный ingestion 1.1 выполнен:20 chunks (11+9), все20 logical UUID сохранены; новая generation `f62c8bbe398110d2010ca66d2a314cd692fbf43861317f1b38bc12157d22e223`. CURRENT, snapshot, manifest и7 публичных примеров обновлены. Старое поколение осталось локально для аудита; embedding_ready=false.

## Docker: фактический статус

Engine29.8.0 и Composev5.5.1 работают; Compose config валиден. Готовый локальный образ qdrant/qdrant:v1.15.1 не обнаружен ни в начале, ни после неуспешного pull. Desktop CLI в одном probe сообщал stopped при работающем Engine и присутствующих backend processes; состояние Engine установлено через API, а не GUI-label.

DNS для auth.docker.io и registry-1.docker.io разрешался, direct TLS1.3 проходил. /v2/ отвечал401, anonymous token endpoint однажды ответил200 с token (сам token не логировался). 401 здесь — штатный registry authentication challenge, а не доказательство неверного аккаунта: [Docker registry auth](https://docs.docker.com/reference/api/registry/auth/).

Engine сообщил proxy http.docker.internal:3128; Windows user proxy включён на loopback, без обнаруженных embedded credentials; PAC не задан. WinHTTP отдельно сообщил Direct access (no proxy server): настройки разных клиентов отличаются, но это ещё не доказывает ошибочную конфигурацию. В проверенной user daemon.json custom DNS/mirrors не обнаружены. Proxy-режим Desktop не удалось достоверно извлечь из проверенной выборки settings. Значения/секреты credential store не читались. Настройки не менялись; Desktop proxy относится к Desktop settings, а не исправляется произвольной записью daemon.json: [Docker proxy docs](https://docs.docker.com/engine/daemon/proxy/).

При повторе pull прошёл token stage и скачал часть слоёв, но затем CDN production.cloudfront.docker.com оборвал blob с EOF. Native pull сообщил short read: expected28230270, got11788347 bytes. Новый host registry probe также получил ConnectionResetError. Таким образом, подтверждён нестабильный transport/TLS/передача по маршруту, а не постоянный DNS NXDOMAIN, отсутствие Docker или доказанный неверный пароль. Какой конкретно hop (proxy/VPN/канал/CDN) закрывает соединение, не установлено. Статичный DNS/proxy fix без доказательств не применялся.

`python infrastructure/verify_qdrant.py` реально вызван. Он использует отдельный Compose project kbeauty-review-check, loopback6394 и изолированный named volume. Запуск остановился на pull. Контейнер Qdrant не запущен; health/readiness и сохранение synthetic point после restart **не выполнены**, успешный статус не заявляется. Машиночитаемое свидетельство: [docker-review-result.json](docker-review-result.json); signed URL query/credentials удалены из диагностики.

Для продолжения нужен стабильный доступ Docker Engine к auth/registry и blob CDN; список необходимых направлений описан в [Docker allowlist](https://docs.docker.com/desktop/enterprise/allow-list/). Существующие контейнеры, images и volumes не удалялись; down -v не применялся. Бизнес-данные и model embeddings в Qdrant не загружались. Скрипт готов к проверке только синтетических данных после восстановления доступа.

## Ограничения и gate

До-Git история исходного бизнеса, точная сетевая первопричина, Qdrant runtime/health/persistence, backup/restore, Linux, optional editable install0.3.1, dense tokenizer/model limits и будущие API/LLM сценарии не подтверждены. Полный security audit не выполнялся; scanners проверяют известные шаблоны и не являются абсолютной гарантией.

Блок2 не начат. Business corrections и regression coverage завершены, Docker gate остаётся заблокирован передачей образа. Для перехода нужны приёмка уточнённых данных1.1 и завершение требуемой инфраструктурной проверки. GitHub remote не задан; push не выполнялся.
