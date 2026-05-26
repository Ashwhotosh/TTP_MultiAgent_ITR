# IndianTaxBench Comparison Results

| Metric | GPT-4o | Gemini 2.0 Flash | FinITR-AI v3 |
|--------|--------|-----------------|--------------|
| Overall Accuracy | 83.7% | 83.7% | 97.8% |
| Tax Computation Accuracy | 75.0% | 75.0% | 100.0% |
| Rule & Regime Accuracy | 87.5% | 87.5% | 96.5% |
| Form Selection Accuracy | 100.0% | 100.0% | 94.0% |
| Schedule Precision | 100.0% | 100.0% | 98.1% |
| Schedule Recall | 100.0% | 100.0% | 88.0% |
| Schedule Mapping F1 | 100.0% | 100.0% | 90.9% |

GPT-4o and Gemini evaluated on 16 representative prompts via web interface.
FinITR-AI v3 evaluated on 100 full benchmark cases using automated runner.

> Schedule Mapping F1 — For GPT-4o/Gemini: derived from form/schedule categorical accuracy on manual eval prompts. For FinITR-AI v3: F1 score over required tax schedules across 100 automated cases.
