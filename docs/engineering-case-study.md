# K-Beauty AI Support — engineering case study

## Задача и граница результата

Система отвечает по документам о доставке/возвратах/оплате/лояльности и структурированному каталогу косметики. Данные вымышлены, версия1.1;11 policy sections и9 товаров. Нужны проверяемые источники, точные вычисления и безопасные исходы при отсутствии знаний/доступов. Итог цикла — **Engineering Prototype / MVP PARTIAL**. Свободная клиентская поддержка не принята.

## Инженерные решения

Структурные смысловые units сохраняют сроки/пороги/исключения; stable logical ID отделён от content hash. Immutable export и model/analyzer manifests обеспечивают воспроизводимость. Dense BGE-M3 и русский BM25 находятся в одном Qdrant point, новое поколение проверяется полностью до atomic alias switch; query фиксирует физическую коллекцию. Реальные Server tests включают no-op/update/delete/interruption/readback/restart.

Hybrid RRF совмещает ранги разных шкал. Optional MiniLM reranker добавлен как отдельный эксперимент, затем оставлен off: функциональная интеграция не оправдала default promotion. Точные цены/свойства и денежные операции проверяются typed tools. FastAPI различает шесть статусов, readiness проверяет реальные зависимости. Local Qwen3 выбирает допустимые источники или support bundle; это extractive architecture, а не свободный синтез.

## Что показали эксперименты

На13 заранее размеченных retrieval queries Hybrid Recall5 вырос82,05→91,79%, но MRR снизился96,15→90,38%; DR05 в одной перефразировке опустился с первого на четвёртое место. Reranker pool10 поднял ранние позиции, но потерял необходимые sources: Recall5=87,69%, p50≈3,179 s против Hybrid≈0,653 s в том опыте. Поэтому наличие технологии не выдано за выигрыш продукта. [Retrieval](block-3-results.md), [reranking](block-4-results.md).

Ранняя генерационная проверка12/12 включала лишь два фактических LLM-вопроса. Более широкий final дал29/42. После исправлений known42 достигли42/42, но новые24 —15/24. Последняя ограниченная попытка дала21/24 на known24 и16/24 на новых, при регрессии known42 до36/42. Это показало ограниченность routing/context heuristics и BGE prototypes. [Evaluation](block-6.2-results.md).

На финальном новом наборе Recall5=95,83%, completeness=66,67%, три семантически неподходящих answered. True source quote не означает подходящий ответ: вопрос о сроке хранения бонусов получил правила хранения посылки. Отдельный user-span guard дал10 safe502 на90 запросах и не решил классификацию неизвестного транспорта. Frozen labels и официальные результаты после прогона не менялись.

## Проверенные достижения

Работающий ingestion/indexing/retrieval/API/local inference pipeline, атомарная публикация и точные typed tools;259 unit,13 real Qdrant/BGE integration contracts с явно doubled FAQ provider,90 actual HTTP evaluation requests, clean clone и CI. Семь точных расчётов корректны. На новом наборе warm HTTP p50/p95=5,46/14,79 s, cold ready≈100 s, host RAM94% на8GB. Real integration и CI имеют разные scopes; API fee0 не означает нулевую вычислительную стоимость.

## Вывод и закрытие

Сохранены проверенные компоненты и отрицательные результаты. Решение владельца — завершить цикл без нового tuning sprint. Для надёжной свободной поддержки остаются P1 по intent/подзадачам/semantic adequacy и ресурсные ограничения. Переиспользуемы generation contracts, exact tools, failure/status boundaries и evaluation discipline; доменные keywords/thresholds не универсальная архитектура. [Финальная схема и Known Limitations](project-closure.md), [проверенный показ](demo-verified-scenarios.md).
