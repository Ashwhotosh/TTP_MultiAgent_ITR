# FinITR-AI v3 — Master Build Plan

## Problem Statement
**"FinITR-AI: An Agentic Multi-Document Reconciliation System for Notice-Risk Prevention in Indian Income Tax Filing, with Schedule-Mapped Filing Guidance and IndianTaxBench for Evaluation"**

## 5-Week Sprint Overview

| Week | Focus | Key Deliverable | Files Created/Modified |
|------|-------|-----------------|----------------------|
| 1 | Foundation: Parsers + Tools + AIS Reconciliation | AuditorAgent works end-to-end on synthetic data | parsers/*, tools/*, agents/auditor_agent.py |
| 2 | Multi-Agent Architecture + Critic Loop | 4 agents running with real ReAct feedback loop | agents/*, critic catches hallucinations in demo |
| 3 | Deep Vertical: Schedule CG/VDA + CA Brief | Zerodha/WazirX CSV → Schedule entries + PDF brief | schedules/*, frontend/components/report.py |
| 4 | IndianTaxBench + Evaluation | 100+ test cases, baseline comparison report | benchmarks/*, evaluation/* |
| 5 | Polish: Voice Demo + ITR JSON + Streamlit UI | Full demo-ready application | frontend/*, api/* |

## Architecture Decisions (Locked)
- **UI**: Streamlit (with FastAPI backend for agent orchestration)
- **Retrieval**: Hybrid — PageIndex (CriticAgent) + ChromaDB Vector RAG (OptimizerAgent)
- **LLM**: Ollama with qwen2.5:7b (primary) or llama3.1:8b (fallback)
- **Tax Engine**: Deterministic Python (NO LLM math) — both Old + New regime
- **Verification**: NLI cross-encoder (DeBERTa-v3-small) + arithmetic re-check

## What to Migrate from v2
- `components/05_calculator/calculator.py` → `tools/calculator.py` (add Old Regime)
- `components/07_verifier/verifier.py` → `tools/verifier.py` (copy directly)
- `components/01_csv_parser/parser.py` → `parsers/csv_parser.py` (adapt output format)
- `components/04_pageindex/retriever.py` → `tools/retriever.py` (expand tree)
- `corpus/` → `corpus/` (expand knowledge base)
- Vendor regex lists from `components/02_classifier/predict.py` → `agents/auditor_agent.py`

## What NOT to Migrate
- MuRIL training pipeline (train.py, evaluate.py, config.yaml) — not used
- Old pipeline.py — replaced by orchestrator
- Old generator.py — rewritten with better prompting
- Old mapper.py — logic absorbed into agents

## How to Use These Plans with AI Coding Agents
Each `week_N.md` file is structured as a prompt. Open it in Claude Code or your IDE's AI assistant and say:
> "Read plans/week_1.md and implement all tasks in order. After each task, run the test command to verify."

The plans include:
- Exact file paths to create/modify
- Input/output contracts for each function
- Test commands to verify each task
- Acceptance criteria (what "done" looks like)
