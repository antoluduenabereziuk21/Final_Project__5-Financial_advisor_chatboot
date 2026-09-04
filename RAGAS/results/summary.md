# RAGAS Evaluation Summary

Generator model: `openai/gpt-oss-120b` (Groq)  
Judge model: `gemini-3.5-flash-lite` (Gemini)  
Total questions run through pipeline: 50  
Questions RAGAS-scored so far (excludes behavioral-only categories): 50

## Aggregate scores (mean across scored rows -- may be a partial
## run if the judge phase stopped early on a quota cutoff; check
## the terminal output above for whether this run completed)

| Metric | Mean |
|---|---|
| llm_context_precision_with_reference | 0.363 |
| context_recall | 0.600 |
| answer_relevancy | 0.599 |
| faithfulness | 0.867 |

## Behavioral-only rows (not RAGAS-scored -- eyeball confidence_flag)

| id | category | confidence_flag | answer (truncated) |
|---|---|---|---|