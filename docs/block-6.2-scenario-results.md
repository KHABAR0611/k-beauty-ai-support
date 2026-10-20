# Results by scenario — frozen final candidate

Runtime0fb3183; business1.1. Known42 and24 retain original labels; new24 evaluated once. A failed answered means an unsuitable/incomplete task response, not necessarily a fabricated source fact.

| Set | ID | Prior PASS | PASS | Expected → actual | Qwen completed request | HTTP s | Missing sources/facts or error |
|---|---|---|---|---|---|---:|---|
| regression | F01 | True | False | answered → system_error | False | 14.496 | DR-01, DR-02, День оплаты не считается, после передачи, не включают сборку |
| regression | F02 | True | False | answered → system_error | False | 4.874 | DR-01, остальных населённых пунктах — только в ПВЗ |
| regression | F03 | True | True | answered → answered | True | 5.530 | — |
| regression | F04 | True | False | answered → system_error | False | 7.636 | DR-01, только по России |
| regression | F05 | True | False | answered → system_error | False | 4.533 | DR-01, Если ПВЗ нет, оформление недоступно |
| regression | F06 | True | True | answered → answered | True | 5.678 | — |
| regression | F07 | True | True | answered → answered | True | 4.971 | — |
| regression | F08 | True | True | answered → answered | True | 11.092 | — |
| regression | F09 | True | True | answered → answered | True | 4.234 | — |
| regression | F10 | True | True | answered → answered | True | 7.050 | — |
| regression | F11 | True | True | answered → answered | True | 8.973 | — |
| regression | F12 | True | True | answered → answered | True | 3.448 | — |
| regression | F13 | True | True | answered → answered | True | 5.311 | — |
| regression | F14 | True | True | answered → answered | True | 3.255 | — |
| regression | F15 | True | True | answered → answered | True | 5.686 | — |
| regression | F16 | True | True | answered → answered | True | 6.244 | — |
| regression | F17 | True | True | answered → answered | True | 8.297 | — |
| regression | F18 | True | True | answered → answered | True | 8.344 | — |
| regression | F19 | True | True | clarification_needed → clarification_needed | False | 0.366 | — |
| regression | F20 | True | True | clarification_needed → clarification_needed | False | 0.261 | — |
| regression | F21 | True | True | clarification_needed → clarification_needed | False | 0.369 | — |
| regression | F22 | True | True | clarification_needed → clarification_needed | False | 0.239 | — |
| regression | F23 | True | True | answered → answered | False | 0.608 | — |
| regression | F24 | True | True | answered → answered | False | 0.612 | — |
| regression | F25 | True | True | answered → answered | False | 0.667 | — |
| regression | F26 | True | True | answered → answered | False | 0.613 | — |
| regression | F27 | True | True | answered → answered | False | 0.609 | — |
| regression | F28 | True | True | clarification_needed → clarification_needed | False | 0.179 | — |
| regression | F29 | True | True | insufficient_context → insufficient_context | False | 0.671 | — |
| regression | F30 | True | False | insufficient_context → answered | True | 8.033 | — |
| regression | F31 | True | True | requires_external_data → requires_external_data | False | 0.256 | — |
| regression | F32 | True | True | requires_external_data → requires_external_data | False | 0.186 | — |
| regression | F33 | True | True | requires_external_data → requires_external_data | False | 0.877 | — |
| regression | F34 | True | True | answered → answered | True | 5.395 | — |
| regression | F35 | True | False | answered → system_error | False | 8.356 | DR-01, DR-02, 350 ₽, 3 500 ₽, после применения промокода |
| regression | F36 | True | True | handoff_required → handoff_required | False | 0.003 | — |
| regression | F37 | True | True | answered → answered | True | 6.256 | — |
| regression | F38 | True | True | clarification_needed → clarification_needed | False | 0.133 | — |
| regression | F39 | True | True | answered → answered | True | 3.232 | — |
| regression | F40 | True | True | answered → answered | True | 4.504 | — |
| regression | F41 | True | True | answered → answered | True | 4.975 | — |
| regression | F42 | True | True | handoff_required → handoff_required | False | 0.003 | — |
| known24 | N01 | False | False | answered → system_error | False | 7.490 | DR-01, только по России |
| known24 | N02 | True | False | answered → system_error | False | 4.561 | DR-01, Если ПВЗ нет, оформление недоступно |
| known24 | N03 | True | True | answered → answered | True | 5.060 | — |
| known24 | N04 | True | True | answered → answered | True | 5.612 | — |
| known24 | N05 | False | True | answered → answered | True | 7.161 | — |
| known24 | N06 | False | True | answered → answered | True | 3.362 | — |
| known24 | N07 | True | True | answered → answered | True | 10.064 | — |
| known24 | N08 | True | True | answered → answered | True | 4.114 | — |
| known24 | N09 | True | True | answered → answered | True | 5.635 | — |
| known24 | N10 | True | True | answered → answered | True | 2.955 | — |
| known24 | N11 | True | True | answered → answered | True | 5.582 | — |
| known24 | N12 | False | True | answered → answered | True | 10.993 | — |
| known24 | N13 | True | True | answered → answered | True | 5.652 | — |
| known24 | N14 | False | True | answered → answered | True | 3.012 | — |
| known24 | N15 | True | True | answered → answered | True | 7.197 | — |
| known24 | N16 | True | True | answered → answered | True | 6.080 | — |
| known24 | N17 | True | True | clarification_needed → clarification_needed | False | 0.270 | — |
| known24 | N18 | True | True | clarification_needed → clarification_needed | False | 0.620 | — |
| known24 | N19 | True | True | requires_external_data → requires_external_data | False | 0.220 | — |
| known24 | N20 | False | True | handoff_required → handoff_required | False | 0.180 | — |
| known24 | N21 | False | False | insufficient_context → answered | True | 4.122 | — |
| known24 | N22 | False | True | answered → answered | True | 5.614 | — |
| known24 | N23 | False | True | clarification_needed → clarification_needed | False | 0.185 | — |
| known24 | N24 | True | True | answered → answered | False | 0.528 | — |
| holdout | H01 | — | False | answered → system_error | False | 8.039 | DR-01, только по России, остальных населённых пунктах |
| holdout | H02 | — | True | answered → answered | True | 14.789 | — |
| holdout | H03 | — | True | answered → answered | True | 5.143 | — |
| holdout | H04 | — | True | answered → answered | True | 5.561 | — |
| holdout | H05 | — | False | answered → system_error | False | 9.046 | DR-05, фото товара и упаковки, оплачивает магазин |
| holdout | H06 | — | False | answered → answered | True | 7.462 | DR-04, DR-06, 7 календарных дней, 10 календарных дней |
| holdout | H07 | — | True | answered → answered | True | 17.399 | — |
| holdout | H08 | — | True | answered → answered | True | 10.029 | — |
| holdout | H09 | — | True | answered → answered | True | 5.560 | — |
| holdout | H10 | — | True | answered → answered | True | 3.317 | — |
| holdout | H11 | — | True | answered → answered | True | 5.459 | — |
| holdout | H12 | — | False | answered → answered | True | 8.580 | PL-03 |
| holdout | H13 | — | False | answered → answered | True | 5.468 | PL-03, 14 календарных дней, 180 календарных дней |
| holdout | H14 | — | False | answered → answered | True | 8.686 | PL-03, 5%, без доставки |
| holdout | H15 | — | True | answered → answered | True | 3.180 | — |
| holdout | H16 | — | True | answered → answered | True | 3.400 | — |
| holdout | H17 | — | True | clarification_needed → clarification_needed | False | 0.355 | — |
| holdout | H18 | — | False | clarification_needed → system_error | False | 4.907 | ungrounded_request_parameter |
| holdout | H19 | — | False | clarification_needed → insufficient_context | False | 0.708 | — |
| holdout | H20 | — | True | insufficient_context → insufficient_context | False | 0.624 | — |
| holdout | H21 | — | True | requires_external_data → requires_external_data | False | 0.268 | — |
| holdout | H22 | — | True | handoff_required → handoff_required | False | 0.196 | — |
| holdout | H23 | — | True | answered → answered | False | 0.544 | — |
| holdout | H24 | — | True | answered → answered | True | 5.628 | — |
