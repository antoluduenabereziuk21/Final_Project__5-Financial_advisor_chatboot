# RAGAS Evaluation Summary

Generator model: `openai/gpt-oss-120b` (Groq)  
Judge model: `gemini-3.5-flash-lite` (Gemini)  
Total questions run through pipeline: 68  
Questions RAGAS-scored so far (excludes behavioral-only categories): 50

## Aggregate scores (mean across scored rows -- may be a partial
## run if the judge phase stopped early on a quota cutoff; check
## the terminal output above for whether this run completed)

| Metric | Mean |
|---|---|
| llm_context_precision_with_reference | 0.367 |
| context_recall | 0.590 |
| answer_relevancy | 0.595 |
| faithfulness | 0.870 |

## Behavioral-only rows (not RAGAS-scored -- eyeball confidence_flag)

| id | category | confidence_flag | answer (truncated) |
|---|---|---|---|
| 51 | not_found_structural | no_answer_in_context | The retrieved filing excerpts do not contain this information. The provided excerpts do not contain  |
| 52 | not_found_structural | no_answer_in_context | The retrieved filing excerpts do not contain this information. The context does not contain Tesla's  |
| 53 | not_found_structural | no_answer_in_context | The retrieved filing excerpts do not contain this information. The provided excerpts do not contain  |
| 54 | not_found_structural | no_answer_in_context | The retrieved filing excerpts do not contain this information. The provided excerpts do not contain  |
| 55 | not_found_fictional | no_answer_in_context | The retrieved filing excerpts do not contain this information. – the excerpts do not contain any inf |
| 56 | not_found_fictional | no_answer_in_context | The retrieved filing excerpts do not contain this information. – the provided excerpts contain no in |
| 57 | not_found_fictional | no_answer_in_context | The retrieved filing excerpts do not contain this information. – the excerpts contain no information |
| 58 | off_topic | no_answer_in_context | The retrieved filing excerpts do not contain this information. The context does not contain any lasa |
| 59 | off_topic | no_answer_in_context | The retrieved filing excerpts do not contain this information. – the excerpts contain no information |
| 60 | off_topic | generation_error | The answer service is temporarily unavailable. Please retry. |
| 61 | off_topic | no_answer_in_context | The retrieved filing excerpts do not contain this information. – the excerpts do not contain any inf |
| 62 | subjective_gate | subjective_no_verdict | I can't give a recommendation or an opinion on that. I can show you the figures in the filings so yo |
| 63 | subjective_gate | subjective_no_verdict | I can't give a recommendation or an opinion on that. I can show you the figures in the filings so yo |
| 64 | subjective_gate | subjective_no_verdict | I can't give a recommendation or an opinion on that. I can show you the figures in the filings so yo |
| 65 | subjective_gate | subjective_no_verdict | I can't give a recommendation or an opinion on that. I can show you the figures in the filings so yo |
| 66 | subjective_gate | subjective_no_verdict | I can't give a recommendation or an opinion on that. I can show you the figures in the filings so yo |
| 67 | edge_case_garbled | no_answer_in_context | The retrieved filing excerpts do not contain this information. – the excerpts do not provide Apple I |
| 68 | edge_case_garbled | ok | Apple Inc. net sales (in millions of dollars):  - FY 2022: $394,328 [4]   - FY 2021: $365,817 [4]    |