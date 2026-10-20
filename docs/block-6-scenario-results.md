# Независимый финальный набор

54 новых формулировки:12 development и42 final, заморожены до inference. После development исправлены подтверждённые дефекты, код89087a9 зафиксирован до первого final query. Final выполнен один раз, runtime/labels после результатов не настраивались. Все HTTP наблюдения реальные, без provider doubles. Отдельно указано, где LLM не вызывалась. Неуспехи сохранены.

| ID | Expected | Actual | Contract | Completed LLM | HTTP,s | Missing answer sources | Missing retrieval top5 |
|---|---|---|---|---|---:|---|---|
| F01 | answered | insufficient_context | FAIL | yes | 35.363 | DR-01, DR-02 | — |
| F02 | answered | insufficient_context | FAIL | no | 0.696 | DR-01 | — |
| F03 | answered | requires_external_data | FAIL | no | 0.667 | — | — |
| F04 | answered | answered | PASS | yes | 21.933 | — | — |
| F05 | answered | insufficient_context | FAIL | no | 0.702 | DR-01 | — |
| F06 | answered | answered | PASS | yes | 22.264 | — | DR-01 |
| F07 | answered | answered | PASS | yes | 21.852 | — | — |
| F08 | answered | insufficient_context | FAIL | yes | 33.024 | DR-04, DR-06 | — |
| F09 | answered | answered | PASS | yes | 23.928 | — | — |
| F10 | answered | answered | FAIL | yes | 10.649 | DR-05 | — |
| F11 | answered | system_error | FAIL | no | 62.867 | DR-05, DR-06 | — |
| F12 | answered | answered | PASS | yes | 32.532 | — | — |
| F13 | answered | answered | PASS | yes | 10.342 | — | — |
| F14 | answered | answered | PASS | yes | 10.155 | — | — |
| F15 | answered | system_error | FAIL | no | 60.927 | PL-02 | — |
| F16 | answered | answered | PASS | yes | 17.167 | — | — |
| F17 | answered | answered | PASS | yes | 45.878 | — | — |
| F18 | answered | answered | PASS | yes | 12.305 | — | — |
| F19 | clarification_needed | clarification_needed | PASS | no | 0.070 | — | — |
| F20 | clarification_needed | clarification_needed | PASS | no | 0.025 | — | — |
| F21 | clarification_needed | system_error | FAIL | no | 63.499 | — | — |
| F22 | clarification_needed | insufficient_context | FAIL | no | 1.176 | — | — |
| F23 | answered | answered | PASS | no | 1.213 | — | DR-02, PL-03 |
| F24 | answered | answered | PASS | no | 1.451 | — | DR-01, DR-02, PL-02 |
| F25 | answered | answered | PASS | no | 0.996 | — | PL-03 |
| F26 | answered | answered | PASS | no | 0.686 | — | DR-01, PL-02 |
| F27 | answered | answered | PASS | no | 1.015 | — | DR-01 |
| F28 | clarification_needed | clarification_needed | PASS | no | 0.009 | — | — |
| F29 | insufficient_context | insufficient_context | PASS | no | 0.903 | — | — |
| F30 | insufficient_context | insufficient_context | PASS | no | 0.888 | — | — |
| F31 | requires_external_data | requires_external_data | PASS | no | 0.901 | — | — |
| F32 | requires_external_data | insufficient_context | FAIL | no | 0.862 | — | — |
| F33 | requires_external_data | requires_external_data | PASS | no | 0.810 | — | — |
| F34 | answered | answered | PASS | yes | 13.996 | — | — |
| F35 | answered | answered | PASS | yes | 35.843 | — | — |
| F36 | handoff_required | handoff_required | PASS | no | 0.003 | — | — |
| F37 | answered | answered | PASS | yes | 10.405 | — | — |
| F38 | clarification_needed | insufficient_context | FAIL | no | 1.016 | — | — |
| F39 | answered | answered | PASS | yes | 9.406 | — | — |
| F40 | answered | answered | PASS | yes | 22.631 | — | — |
| F41 | answered | insufficient_context | FAIL | no | 0.841 | DR-03 | — |
| F42 | handoff_required | handoff_required | PASS | no | 0.003 | — | — |

Полные вопросы/запросы/ответы/usage: [HTTP trace](block-6-final-answers.json). Исходные expectations: [final fixture](../tests/fixtures/block6/final.json). Отдельные ranks: [retrieval trace](block-6-final-retrieval.json). Missing answer source не всегда является retrieval loss: source мог быть найден, но исключён rule-based context или LLM selection.

Последовательные диалоги: A=F37/F38/F39; B=F40/F41/F42. Сообщения отправлены подряд, без клиентского переписывания. API stateless; память диалога не подменялась тестовым helper. F38/F41 демонстрируют неудачные продолжения. Это реальные вызовы с синтетическими вопросами, не переписка покупателей.
