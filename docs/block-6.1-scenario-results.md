# Результаты corrective sprint по каждому запросу

Ожидания42 regression и24 новых независимых запросов сохранены. Runtime d897630; после независимого запуска не настраивался. False answered означает несоответствие полному заданию/статусу по замороженной рубрике, а не обязательно выдуманный факт.

| Набор | ID | Было PASS | Стало PASS | Status | Real LLM | HTTP,s | Missing sources/facts |
|---|---|---|---|---|---|---:|---|
| regression | F01 | False | True | answered | True | 23.644 | — |
| regression | F02 | False | True | answered | True | 4.351 | — |
| regression | F03 | False | True | answered | True | 7.958 | — |
| regression | F04 | True | True | answered | True | 4.273 | — |
| regression | F05 | False | True | answered | True | 4.198 | — |
| regression | F06 | True | True | answered | True | 4.940 | — |
| regression | F07 | True | True | answered | True | 4.481 | — |
| regression | F08 | False | True | answered | True | 21.470 | — |
| regression | F09 | True | True | answered | True | 4.782 | — |
| regression | F10 | False | True | answered | True | 10.574 | — |
| regression | F11 | False | True | answered | True | 13.407 | — |
| regression | F12 | True | True | answered | True | 4.423 | — |
| regression | F13 | True | True | answered | True | 9.045 | — |
| regression | F14 | True | True | answered | True | 3.156 | — |
| regression | F15 | False | True | answered | True | 8.353 | — |
| regression | F16 | True | True | answered | True | 9.319 | — |
| regression | F17 | True | True | answered | True | 21.380 | — |
| regression | F18 | True | True | answered | True | 8.206 | — |
| regression | F19 | True | True | clarification_needed | False | 0.003 | — |
| regression | F20 | True | True | clarification_needed | False | 0.003 | — |
| regression | F21 | False | True | clarification_needed | False | 0.003 | — |
| regression | F22 | False | True | clarification_needed | False | 0.003 | — |
| regression | F23 | True | True | answered | False | 0.684 | — |
| regression | F24 | True | True | answered | False | 0.685 | — |
| regression | F25 | True | True | answered | False | 0.658 | — |
| regression | F26 | True | True | answered | False | 1.033 | — |
| regression | F27 | True | True | answered | False | 0.666 | — |
| regression | F28 | True | True | clarification_needed | False | 0.003 | — |
| regression | F29 | True | True | insufficient_context | False | 0.548 | — |
| regression | F30 | True | True | insufficient_context | False | 0.547 | — |
| regression | F31 | True | True | requires_external_data | False | 0.606 | — |
| regression | F32 | False | True | requires_external_data | False | 0.614 | — |
| regression | F33 | True | True | requires_external_data | False | 0.639 | — |
| regression | F34 | True | True | answered | True | 3.324 | — |
| regression | F35 | True | True | answered | True | 5.257 | — |
| regression | F36 | True | True | handoff_required | False | 0.003 | — |
| regression | F37 | True | True | answered | True | 6.809 | — |
| regression | F38 | False | True | clarification_needed | False | 0.003 | — |
| regression | F39 | True | True | answered | True | 3.358 | — |
| regression | F40 | True | True | answered | True | 3.783 | — |
| regression | F41 | False | True | answered | True | 2.755 | — |
| regression | F42 | True | True | handoff_required | False | 0.004 | — |
| independent | N01 | — | False | insufficient_context | False | 1.090 | DR-01, только по России |
| independent | N02 | — | True | answered | True | 23.295 | — |
| independent | N03 | — | True | answered | True | 5.554 | — |
| independent | N04 | — | True | answered | True | 8.967 | — |
| independent | N05 | — | False | clarification_needed | False | 0.003 | DR-05, фото товара и упаковки, оплачивает магазин |
| independent | N06 | — | False | insufficient_context | False | 1.195 | DR-05, не автоматическое основание отказать позже, не обещает одобрение |
| independent | N07 | — | True | answered | True | 22.148 | — |
| independent | N08 | — | True | answered | True | 7.098 | — |
| independent | N09 | — | True | answered | True | 9.548 | — |
| independent | N10 | — | True | answered | True | 2.961 | — |
| independent | N11 | — | True | answered | True | 8.537 | — |
| independent | N12 | — | False | system_error | False | 25.723 | PL-02, PL-03, PL-04, PL-05, Сначала применяется промокод, 20% стоимости товаров после применения промокода |
| independent | N13 | — | True | answered | True | 9.385 | — |
| independent | N14 | — | False | system_error | False | 25.575 | PL-03, 5%, без доставки |
| independent | N15 | — | True | answered | True | 10.498 | — |
| independent | N16 | — | True | answered | True | 6.672 | — |
| independent | N17 | — | True | clarification_needed | False | 0.003 | — |
| independent | N18 | — | True | clarification_needed | False | 0.003 | — |
| independent | N19 | — | True | requires_external_data | False | 0.632 | — |
| independent | N20 | — | False | insufficient_context | False | 0.594 | — |
| independent | N21 | — | False | answered | True | 4.766 | — |
| independent | N22 | — | False | insufficient_context | False | 0.732 | PL-01, Наличными, при получении и в рассрочку оплатить нельзя |
| independent | N23 | — | False | answered | True | 7.088 | — |
| independent | N24 | — | True | answered | False | 0.607 | — |
