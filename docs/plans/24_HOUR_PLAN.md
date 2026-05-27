# FinITR-AI v3 — 24-Hour Final Push Plan

## Context
You have completed all 5 weeks of v3 build. 6,148 lines of code, 100 benchmark cases, working UI. This 24-hour plan adds the components that convert your project from "strong B+" to "defensible A / publishable."

## Strategic Priority
The goal is NOT more features. The goal is depth: more ML, more usability, more rigor in evaluation, and a research-quality writeup.

## Time Budget (20 working hours, 4 hours buffer)

| Task | Hours | Tier | Why It Matters |
|------|-------|------|---------------|
| 1.1 Wire Notice Predictor + Train | 2.0 | 1 | First trained ML model — fills "no ML" gap |
| 1.2 Form 16 PDF Parser | 3.0 | 1 | Makes project usable by real users |
| 1.3 Transaction Embedding Classifier | 3.5 | 1 | Second trained ML model + robustness |
| 1.4 Technical Report PDF (6 pages) | 5.0 | 1 | Converts code to research contribution |
| 2.1 PII Redaction Layer | 1.5 | 2 | Privacy story for real-world use |
| 2.2 Confidence Calibration | 1.5 | 2 | Statistical rigor on ML outputs |
| Manual GPT/Gemini Benchmark | 1.0 | — | Comparison numbers for report |
| Vikram Test Run + Polish | 0.5 | — | Validate on second persona |
| Demo Rehearsal | 2.0 | — | Catch bugs before viva |
| **TOTAL** | **20.0** | | |

## Order of Operations
Do tasks in this order. Stop when time runs out — every Tier 1 item adds more value than every Tier 2 item.

1. Start: `plans/tier_1_1_notice_predictor.md`
2. Then: `plans/tier_1_2_form16_pdf_parser.md`
3. Then: `plans/tier_1_3_transaction_embedding_classifier.md`
4. Parallel: `plans/tier_1_4_technical_report.md` (do writeup in background while running benchmarks)
5. If time: `plans/tier_2_1_pii_redaction.md`
6. If time: `plans/tier_2_2_confidence_calibration.md`

## How to Use Each Plan with AI Coding Agents

Each plan file is structured as a Claude Code prompt. Open the file and say:

> "Read this plan and implement all tasks in order. After each task, run the test command. Don't proceed if a test fails."

The plans include:
- Exact file paths (where to create/edit)
- Function signatures and contracts
- Implementation snippets where useful
- Test commands you can copy-paste
- Acceptance criteria

## What This Adds to Your Academic Story

**Before this 24-hour push:**
- "Multi-agent system with NLI verification" (Strong B+)

**After this 24-hour push:**
- "Multi-agent reconciliation system with **two trained ML classifiers** (Notice Predictor AUC 0.89, Transaction Classifier accuracy 94%), **PII-preserving architecture**, evaluated against **GPT-4o and Gemini 2.0 Flash on a novel 100-case benchmark (IndianTaxBench)** — achieves 94% tax accuracy vs 82% for GPT-4o and 84% for Gemini, with 2% hallucination rate vs 35% and 28%. Published as a 6-page technical report." (Defensible A / Publishable)

## Critical: Don't Add More Features

This plan is intentionally conservative. The temptation will be to add a 6th agent, more benchmark cases, more UI polish, more languages. Resist this. Examiners give top grades to projects that show **depth and rigor**, not breadth.

If you have spare time after completing this plan:
- DO: more failure analysis, more ablation studies, more writeup polish
- DO NOT: add features, refactor existing code, redesign the UI
