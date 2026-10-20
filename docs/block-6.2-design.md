# Generalization: diagnosis and bounded semantic adapter

Baseline48a5f04. Nine original failures are preserved in block-6.2-diagnosis.json, including actual retrieval/context, old intent, operation, LLM completion and control. Source loss is visible per case; the dominant confirmed failures occur after retrieval. Five lexical misses never reached relevant LLM interpretation, two cases accepted source quotations for a different/incomplete task, and two exceeded CPU deadlines with overbroad context. A specific hallucination is not invented for timed-out calls without a draft.

## Rejected approaches

General multi-label Qwen routing selected many unrelated capabilities on known cases. A named operation/topic JSON contract also failed. These component variants were rejected, not promoted to production. Binary answerability verification confused a documented negative business answer with lack of knowledge. A small delivery-parameter extraction was useful as a conservative unknown-method veto, but sometimes returned “not specified” for explicit known methods: it is not used to infer a payable tariff or populate a financial tool.

## Implemented minimum

The existing lexical router remains a compatibility path. Existing BGE-M3 performs a small semantic prototype comparison for operation and policy topic; no new classifier weights/dependencies/framework are installed. Strong calculate/recommend/human actions are separate from source selection. The action margin boundary0.10 is a routing rule, never a probability. The semantic layer can recover a missing/misclassified policy topic by intersecting its topic with the first three actual retrieved candidates. Similarity minimum0.55 and topic margin0.01 are bounded fallback gates, not semantic truth. Strong topic conflicts and narrow accrual/promo questions use margin0.08; exact source families and typed product references remain checked. Thresholds were fixed on known development data before independent inference.

Typed pricing/catalogue contracts remain authoritative. Natural-language numbers are not silently converted into a valid basket. Missing inputs produce clarification. Human handoff is pending only; Orders API remains unavailable. Several policy parts continue to be supported together; the legacy complete bundles are retained unless a bounded semantic refinement applies.

## Claims and question parameters

Actual Qdrant payloads must match the entire approved snapshot. Each selected section produces bindings: source UUID/hash, a literal anchor and its exact offsets/hash; product claims additionally bind a validated product_id. An internal deterministic support bundle contains policy scopes, literal supporting sentences and exact product data. Qwen selects this allowlisted bundle rather than repeatedly processing four full loyalty sections. The final response expands only a valid selection into the original whole source sections. Important output conditions are not truncated. Bundle IDs are internal context identities, not additional Qdrant points or public source IDs.

This separates short LLM support selection from authoritative source compilation. The LLM does not receive every full business paragraph and is not claimed to perform universal entailment or free-form grounded synthesis. Explicit diagnostics identify registered_support_descriptors and physical source bindings. A valid source is still not a universal proof of question suitability: semantic routing, requested operation, required data and independent evaluation remain separate boundaries.

Delivery parameters are extracted from the user question alone, in a separate tiny schema call; source text cannot supply the requested method. An unknown named method vetoes answered. “Not specified” is not treated as a valid basket delivery choice and never populates the calculator. The two calls share a total25s LLM budget, without retry after a read timeout. API deadline40s, CPU2,ctx4096/output128, one worker and reranker-off remain unchanged. Parameter-call time is nested within LLM time; semantic routing is nested within preparation.

## Evaluation boundary

Known42 and24 remain regression. First implemented-adapter run22/24 is retained; source rank2 versus rank1 and source-contaminated parameter extraction were corrected before freeze. New24 expectations and criteria are fixed in block-6.2-evaluation-plan.json. The independent run occurs once after runtime/configuration freeze, with no subsequent tuning. Exact quote integrity is measured separately from task completeness, source suitability, tool/status correctness and refusal rate. No mass-abstention success or customer-resolution claim is allowed.
