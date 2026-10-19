# Реальные примеры source preparation

Получены CLI из данных 1.0. Fingerprint `9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853`. 7 из 20 чанков; полный manifest описывает все 20. Это metadata/source export без embeddings.

## DR-02 — Способы, стоимость и сроки

```json
{
  "id": "af2794df-bb9a-5a6b-81de-5ef337117dd5",
  "metadata": {
    "chunk_sha256": "ab43a9d451cef5e2d42284eda933198f11f337137b1141d88d29b248711aa749",
    "chunker_version": "structure-v1",
    "data_origin": "fictional",
    "document_id": "delivery_returns",
    "document_version": "1.0",
    "effective_date": "2026-10-19",
    "language": "ru",
    "logical_id": "data/delivery_and_returns.md|delivery_returns|DR-02|1.0|structure-v1",
    "parent_id": "af2794df-bb9a-5a6b-81de-5ef337117dd5",
    "preparation_generation": "9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853",
    "schema_version": "1.0",
    "section": "DR-02",
    "source": "data/delivery_and_returns.md",
    "source_sha256": "6f05f5b604d88d1894b706941fb73aa59e5a8c6dd82ac9af9e6b97e480a85d1c",
    "title": "Способы, стоимость и сроки",
    "token_count": null,
    "tokenizer_id": null,
    "type": "policy"
  },
  "text": "# Доставка и возвраты K-Beauty\n\nПравила относятся к вымышленному магазину K-Beauty и не являются подтверждёнными условиями действующего бизнеса.\n\n## DR-02. Способы, стоимость и сроки\n\n| Зона | Способ | Стоимость | Бесплатно от | Перевозка |\n|---|---|---:|---:|---|\n| Москва | Курьер | 350 ₽ | 3 500 ₽ | 1–2 рабочих дня |\n| Санкт-Петербург | Курьер | 400 ₽ | 3 500 ₽ | 2–3 рабочих дня |\n| Россия, включая Москву и Санкт-Петербург | ПВЗ | 250 ₽ | 2 500 ₽ | 3–7 рабочих дней |\n\nПорог включительный: ровно 3 500 ₽ для курьера или 2 500 ₽ для ПВЗ уже дают бесплатную доставку. Порог определяется стоимостью товаров **после промокода, но до списания бонусов**, без стоимости доставки. Бонусы не меняют право на бесплатную доставку. Один заказ — один адрес и один способ доставки. Срочная доставка не предусмотрена."
}
```

## DR-05 — Повреждение, брак или ошибка комплектации

```json
{
  "id": "3d8ede4c-682f-5ab9-afd6-c6ced2dc8195",
  "metadata": {
    "chunk_sha256": "8feaec6debb778de14f93b942f0c5030a2d03910db326ca4ffe90a63282cfb66",
    "chunker_version": "structure-v1",
    "data_origin": "fictional",
    "document_id": "delivery_returns",
    "document_version": "1.0",
    "effective_date": "2026-10-19",
    "language": "ru",
    "logical_id": "data/delivery_and_returns.md|delivery_returns|DR-05|1.0|structure-v1",
    "parent_id": "3d8ede4c-682f-5ab9-afd6-c6ced2dc8195",
    "preparation_generation": "9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853",
    "schema_version": "1.0",
    "section": "DR-05",
    "source": "data/delivery_and_returns.md",
    "source_sha256": "6f05f5b604d88d1894b706941fb73aa59e5a8c6dd82ac9af9e6b97e480a85d1c",
    "title": "Повреждение, брак или ошибка комплектации",
    "token_count": null,
    "tokenizer_id": null,
    "type": "policy"
  },
  "text": "# Доставка и возвраты K-Beauty\n\nПравила относятся к вымышленному магазину K-Beauty и не являются подтверждёнными условиями действующего бизнеса.\n\n## DR-05. Повреждение, брак или ошибка комплектации\n\nПри повреждении, браке или неверном товаре нужно обратиться в поддержку, указав номер заказа, описание и приложив фото товара и упаковки. Желательно сообщить в течение 48 часов после получения: это рекомендация для быстрой проверки, а не автоматическое основание отказать позже. Вскрытие упаковки для обнаружения дефекта не означает автоматический отказ.\n\nПосле проверки магазин предлагает замену или возврат. Обратную пересылку при подтверждённом дефекте или ошибке оплачивает магазин. Ассистент не подтверждает дефект и не обещает одобрение. Если деньги возвращаются за весь заказ из-за подтверждённого дефекта или ошибки, возвращается и оплаченная исходная доставка; при частичном возврате исходная доставка не возвращается."
}
```

## PL-02 — Промокод

```json
{
  "id": "bd26ea39-cec5-52f2-a437-cab928cb1241",
  "metadata": {
    "chunk_sha256": "72b4a9b27133dadeb14b7d22b7563e13b6b0f2b6e8655074308f4efb63d4e75c",
    "chunker_version": "structure-v1",
    "data_origin": "fictional",
    "document_id": "payment_loyalty",
    "document_version": "1.0",
    "effective_date": "2026-10-19",
    "language": "ru",
    "logical_id": "data/payment_and_loyalty.md|payment_loyalty|PL-02|1.0|structure-v1",
    "parent_id": "bd26ea39-cec5-52f2-a437-cab928cb1241",
    "preparation_generation": "9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853",
    "schema_version": "1.0",
    "section": "PL-02",
    "source": "data/payment_and_loyalty.md",
    "source_sha256": "2b6d3c743d1b75b95eadb296e9c9e9c35c3acd83b99595d65ff36fb72ef4e29e",
    "title": "Промокод",
    "token_count": null,
    "tokenizer_id": null,
    "type": "policy"
  },
  "text": "# Оплата и бонусная программа K-Beauty\n\nВсе условия относятся к вымышленному магазину K-Beauty.\n\n## PL-02. Промокод\n\nПромокод WELCOME10 даёт скидку 10% на товары первого заказа зарегистрированного клиента. Минимальная стоимость товаров до скидки — 1 500 ₽ включительно. Он действует на весь каталог, один раз на клиента, не применяется к доставке. В текущем наборе данных даты окончания нет; реальная проверка права на промокод требует системы заказов.\n\nВ одном заказе можно применить один промокод. WELCOME10 нельзя совмещать со списанием бонусов. Можно отказаться от промокода и выбрать бонусы. Начисление бонусов при использовании промокода разрешено."
}
```

## PL-04 — Списание бонусов

```json
{
  "id": "cc0f2ea9-e954-5580-a2a2-ec1c4e60fa3e",
  "metadata": {
    "chunk_sha256": "82dcc544adec67b8b1856a205a48431241a2de4034b443b28af43a4519b1cf5e",
    "chunker_version": "structure-v1",
    "data_origin": "fictional",
    "document_id": "payment_loyalty",
    "document_version": "1.0",
    "effective_date": "2026-10-19",
    "language": "ru",
    "logical_id": "data/payment_and_loyalty.md|payment_loyalty|PL-04|1.0|structure-v1",
    "parent_id": "cc0f2ea9-e954-5580-a2a2-ec1c4e60fa3e",
    "preparation_generation": "9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853",
    "schema_version": "1.0",
    "section": "PL-04",
    "source": "data/payment_and_loyalty.md",
    "source_sha256": "2b6d3c743d1b75b95eadb296e9c9e9c35c3acd83b99595d65ff36fb72ef4e29e",
    "title": "Списание бонусов",
    "token_count": null,
    "tokenizer_id": null,
    "type": "policy"
  },
  "text": "# Оплата и бонусная программа K-Beauty\n\nВсе условия относятся к вымышленному магазину K-Beauty.\n\n## PL-04. Списание бонусов\n\n1 бонус = 1 ₽. Можно списать целое количество бонусов в пределах доступного баланса и не более 20% стоимости товаров без промокода; предел округляется вниз до целого рубля. Доставку бонусами оплатить нельзя. Минимального количества для списания нет.\n\nПример: товары 2 220 ₽, баланс 600 бонусов — максимум списания 444 бонуса, денежная оплата товаров 1 776 ₽. Начислится 88 бонусов, если заказ получен и не возвращён. Право на бесплатную доставку считается до списания бонусов по DR-02."
}
```

## PL-05 — Порядок расчёта

```json
{
  "id": "6f5d0530-8e9f-501c-a763-30712243ed06",
  "metadata": {
    "chunk_sha256": "bfad041edca3101b6857d191ae00c7e300ab660364d0bbd21fb86d22c9420d1e",
    "chunker_version": "structure-v1",
    "data_origin": "fictional",
    "document_id": "payment_loyalty",
    "document_version": "1.0",
    "effective_date": "2026-10-19",
    "language": "ru",
    "logical_id": "data/payment_and_loyalty.md|payment_loyalty|PL-05|1.0|structure-v1",
    "parent_id": "6f5d0530-8e9f-501c-a763-30712243ed06",
    "preparation_generation": "9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853",
    "schema_version": "1.0",
    "section": "PL-05",
    "source": "data/payment_and_loyalty.md",
    "source_sha256": "2b6d3c743d1b75b95eadb296e9c9e9c35c3acd83b99595d65ff36fb72ef4e29e",
    "title": "Порядок расчёта",
    "token_count": null,
    "tokenizer_id": null,
    "type": "policy"
  },
  "text": "# Оплата и бонусная программа K-Beauty\n\nВсе условия относятся к вымышленному магазину K-Beauty.\n\n## PL-05. Порядок расчёта\n\n1. Сложить цену × количество товаров из актуального каталога.\n2. Если выбран и применим WELCOME10, уменьшить стоимость товаров на 10%, округлив скидку до копеек. Иначе скидка равна нулю.\n3. Определить стоимость доставки по зоне, способу и стоимости товаров после промокода, до бонусов (DR-02).\n4. При отсутствии промокода списать запрошенные целые бонусы в пределах баланса и лимита 20% стоимости товаров.\n5. Денежный итог = товары − скидка − списанные бонусы + доставка.\n6. Будущее начисление = округлённые вниз 5% денежной оплаты товаров; доставка не учитывается.\n\nАссистент может рассчитать расчётный пример по данным пользователя, но не подтверждает баланс, право на промокод, наличие товара или окончательную сумму реального заказа. Не хватает города, способа доставки, количества, статуса первого заказа или баланса — нужно уточнить соответствующие данные."
}
```

## KB-004 — Jeju Cloud Крем с керамидами

```json
{
  "currency": "RUB",
  "id": "3f82f2d0-1298-5752-9534-ea56e6bcd15e",
  "metadata": {
    "chunk_sha256": "e61112eeff2d809261fef3e10e8a967633569c1fc2bc9aa7451ab0405918d999",
    "chunker_version": "structure-v1",
    "data_origin": "fictional",
    "document_id": "kbeauty_demo",
    "document_version": "1.0",
    "effective_date": "2026-10-19",
    "language": "ru",
    "logical_id": "data/products.json|kbeauty_demo|KB-004|1.0|structure-v1",
    "parent_id": "3f82f2d0-1298-5752-9534-ea56e6bcd15e",
    "preparation_generation": "9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853",
    "product_id": "KB-004",
    "schema_version": "1.0",
    "section": "KB-004",
    "source": "data/products.json",
    "source_sha256": "471bac949d3d7eb0c6f6fe3495e8bc5d57d55f784b48d46b1e70066c7b68e617",
    "title": "Jeju Cloud Крем с керамидами",
    "token_count": null,
    "tokenizer_id": null,
    "type": "product"
  },
  "price_kopecks": 179000,
  "product": {
    "characteristics": {
      "category": "крем",
      "fragrance_free": true,
      "key_ingredients": [
        "керамиды",
        "сквалан"
      ],
      "skin_types": [
        "сухая",
        "нормальная"
      ],
      "usage": "Нанести завершающим этапом увлажняющего ухода.",
      "volume_ml": 50
    },
    "description": "Питательный крем для поддержания увлажнённости кожи.",
    "id": "KB-004",
    "name": "Jeju Cloud Крем с керамидами",
    "price": 1790
  },
  "text": "# KB-004: Jeju Cloud Крем с керамидами\n\n{\"characteristics\":{\"category\":\"крем\",\"fragrance_free\":true,\"key_ingredients\":[\"керамиды\",\"сквалан\"],\"skin_types\":[\"сухая\",\"нормальная\"],\"usage\":\"Нанести завершающим этапом увлажняющего ухода.\",\"volume_ml\":50},\"currency\":\"RUB\",\"description\":\"Питательный крем для поддержания увлажнённости кожи.\",\"id\":\"KB-004\",\"name\":\"Jeju Cloud Крем с керамидами\",\"price\":1790}"
}
```

## KB-005 — Morning Seoul Солнцезащитный флюид

```json
{
  "currency": "RUB",
  "id": "8c6e0976-f69c-5e16-8412-fa9888fb71d1",
  "metadata": {
    "chunk_sha256": "fce7b2543694baac28e1b0fcb933fa3b15bd37e8fe66a4c35a0ed9b836657b41",
    "chunker_version": "structure-v1",
    "data_origin": "fictional",
    "document_id": "kbeauty_demo",
    "document_version": "1.0",
    "effective_date": "2026-10-19",
    "language": "ru",
    "logical_id": "data/products.json|kbeauty_demo|KB-005|1.0|structure-v1",
    "parent_id": "8c6e0976-f69c-5e16-8412-fa9888fb71d1",
    "preparation_generation": "9badfe621f8ead8bb27be31138422446ac07491a391b96456fbb7ad38291a853",
    "product_id": "KB-005",
    "schema_version": "1.0",
    "section": "KB-005",
    "source": "data/products.json",
    "source_sha256": "471bac949d3d7eb0c6f6fe3495e8bc5d57d55f784b48d46b1e70066c7b68e617",
    "title": "Morning Seoul Солнцезащитный флюид",
    "token_count": null,
    "tokenizer_id": null,
    "type": "product"
  },
  "price_kopecks": 149000,
  "product": {
    "characteristics": {
      "category": "солнцезащита",
      "fragrance_free": true,
      "key_ingredients": [
        "пантенол",
        "экстракт риса"
      ],
      "pa": "++++",
      "skin_types": [
        "нормальная",
        "комбинированная"
      ],
      "spf": "50+",
      "usage": "Использовать по инструкции на упаковке; сервис не подтверждает испытания SPF.",
      "volume_ml": 50
    },
    "description": "Дневной солнцезащитный флюид с заявленной в описании вымышленного товара защитой SPF 50+ PA++++.",
    "id": "KB-005",
    "name": "Morning Seoul Солнцезащитный флюид",
    "price": 1490
  },
  "text": "# KB-005: Morning Seoul Солнцезащитный флюид\n\n{\"characteristics\":{\"category\":\"солнцезащита\",\"fragrance_free\":true,\"key_ingredients\":[\"пантенол\",\"экстракт риса\"],\"pa\":\"++++\",\"skin_types\":[\"нормальная\",\"комбинированная\"],\"spf\":\"50+\",\"usage\":\"Использовать по инструкции на упаковке; сервис не подтверждает испытания SPF.\",\"volume_ml\":50},\"currency\":\"RUB\",\"description\":\"Дневной солнцезащитный флюид с заявленной в описании вымышленного товара защитой SPF 50+ PA++++.\",\"id\":\"KB-005\",\"name\":\"Morning Seoul Солнцезащитный флюид\",\"price\":1490}"
}
```
