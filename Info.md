# FinITR-AI v3 — Pipeline & Architecture

---

## Overview

FinITR-AI v3 is a **multi-agent Indian ITR (Income Tax Return) filing assistant**. It takes your financial documents as input, runs them through a chain of 4 specialized AI agents, and produces a complete tax report — regime recommendation, ITR form selection, schedule mapping, risk score, and notice probability.

---

## Input Documents

| Document | Format | What it contains |
|----------|--------|-----------------|
| **Form 16** | PDF or JSON | Employer-declared salary, TDS deducted, deductions (80C/HRA/80D) |
| **AIS (Annual Information Statement)** | JSON | Everything the IT Department knows about you — SFT entries from banks, brokers, crypto exchanges |
| **Bank Statement** | CSV | All transactions for the FY (salary credits, expenses, investments) |
| **Form 26AS** | JSON (optional) | TDS credit summary |
| **Zerodha/WazirX CSV** | CSV (optional) | Capital gains / crypto trade history |

---

## Component Architecture

```
INPUT DOCS
    │
    ▼
┌─────────────┐
│   PARSERS   │  form16_pdf_parser, ais_parser, csv_parser, form26as_parser
└──────┬──────┘
       │  structured data → AgentContext
       ▼
┌──────────────────────────────────────────────────────┐
│              ORCHESTRATOR  (ReAct loop)               │
│                                                       │
│  ┌─────────────┐   ┌──────────────┐                  │
│  │ AuditorAgent│──▶│OptimizerAgent│                  │
│  └─────────────┘   └──────┬───────┘                  │
│         │                  │                          │
│         ▼                  ▼                          │
│  ┌─────────────────┐  ┌─────────────┐                │
│  │ComplianceAgent  │  │  CriticAgent│◀──── re-loop   │
│  └─────────────────┘  └─────────────┘                │
└──────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────┐
│  ML MODELS (inline)  │
│  • TransactionClassifier (3-stage)
│  • NoticePredictor (LogReg)
└──────────────────────┘
       │
       ▼
  FINAL REPORT  →  FastAPI  →  Streamlit UI
```

---

## Stage-by-Stage Pipeline

### Stage 1 — AuditorAgent

**What it does:** Cross-references AIS vs Form 16 vs Bank Statement to find mismatches.

- Runs the **TransactionClassifier** on every bank transaction (3-stage: Regex → kNN/MiniLM embeddings → LLM fallback) to label each as SALARY, CAPITAL_MARKET, CRYPTO, INTEREST_INCOME, etc.
- Compares AIS SFT entries against Form 16 — finds income the government knows about but you haven't declared
- Assigns a **risk score** (LOW/MEDIUM/HIGH/CRITICAL) based on risk weights (crypto=60, CG=55, AIS mismatch=25, cash=15)
- Produces a **reconciliation ledger** of all matched/mismatched items

### Stage 2 — OptimizerAgent

**What it does:** Picks the better tax regime and optimizes deductions.

- Calls **CalculatorTool** (deterministic Section 115BAC slab engine) to compute exact tax under Old Regime vs New Regime
- Applies Section 87A rebate, surcharge, cess, marginal relief
- Recommends the regime that saves you more tax
- Uses **Ollama LLM** (qwen2.5:7b local model) to generate a natural-language explanation; falls back to a template if Ollama is unavailable

### Stage 3 — ComplianceAgent

**What it does:** Selects the correct ITR form and maps required schedules.

- Decides ITR form: ITR-1 (salary only) → ITR-2 (CG/foreign) → ITR-3 (business) → ITR-4 (presumptive)
- Maps required schedules: Schedule Salary, Schedule CG, Schedule VDA (crypto), Schedule OS (interest/dividends)
- Schedule OS inference is **signal-based**: only added if bank INT CR, AIS SFT-004, or explicit deduction evidence exists — never a blanket guess

### Stage 4 — CriticAgent (ReAct loop)

**What it does:** Verifies all claims made by the previous agents.

- Uses **FaithfulnessVerifier** (NLI model or keyword fallback) to check every claim against source documents
- Blocks hallucinated deductions (e.g., 80C under New Regime)
- If issues found, sends feedback to Orchestrator → Orchestrator re-runs the offending agent (up to 3 iterations)

---

## Shared Tools

| Tool | Role |
|------|------|
| **CalculatorTool** | Deterministic tax engine — implements 2024-25 slabs, surcharge, 87A rebate exactly. Removing it drops tax accuracy from 100% to 55%. |
| **PageIndexRetriever** | Retrieves relevant Income Tax Act sections from a local corpus (RAG) to cite legal basis |
| **VectorStore** | Stores document embeddings for semantic search across input documents |
| **FaithfulnessVerifier** | NLI-based claim verification; falls back to keyword matching |
| **OllamaClient** | Calls local Ollama LLM (qwen2.5:7b) for natural language generation |

---

## ML Models

### 1. TransactionClassifier (inside AuditorAgent)

- 3-stage pipeline: Regex patterns (56%) → kNN on multilingual-MiniLM embeddings (26%) → LLM fallback (18%)
- 12 labels, 92.5% accuracy, all income-class labels 100% F1
- Critical classes (CAPITAL_MARKET, CRYPTO, FREELANCE, INTEREST, DIVIDEND) are never misclassified

### 2. NoticePredictor (standalone)

- LogisticRegression on 14 engineered features extracted from the pipeline output
- Predicts probability of receiving a Section 143(1) income tax notice
- Recall-tuned threshold (0.032) to achieve 100% notice-recall (zero false negatives)
- Test AUC: 0.9524 — outperforms GradientBoosting (AUC 0.875) on this dataset size

---

## Output

The final report contains:

- **Recommended regime** — Old vs New with exact tax saving amount
- **ITR form** — ITR-1 / ITR-2 / ITR-3 / ITR-4 with justification
- **Required schedules** — Schedule Salary, CG, VDA, OS with income breakdown
- **Risk level** — LOW / MEDIUM / HIGH / CRITICAL with reason and AIS flag details
- **Notice probability** — 0.0 to 1.0 with human-readable interpretation
- **Reconciliation ledger** — every AIS item vs Form 16 item (matched / AIS-only / mismatch)
- **CA Brief** — structured summary a Chartered Accountant can review before filing

This report is served via **FastAPI** and displayed in a **Streamlit** frontend.

---

## Benchmark Performance

| Metric | Training Suite (100 cases) | Held-Out Set (40 cases) |
|--------|---------------------------|------------------------|
| Tax Computation Accuracy | 100% | 43.1% (noisy inputs) |
| ITR Form Accuracy | 97.0% | 87.5% |
| Risk Accuracy | 96.5% | 91.3% |
| Schedule Precision | 98.1% | 95.8% |
| Schedule Recall | 88.0% | 82.9% |
| Schedule F1 | 90.9% | 85.4% |

**Key design principle:** Minimize False Negatives. A missed notice risk causes direct financial harm (penalty + interest). An over-flag costs the user nothing. The pipeline is tuned so that no genuine HIGH or CRITICAL risk case is ever scored LOW.
