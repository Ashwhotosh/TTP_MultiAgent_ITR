# FinITR-AI v3: Agentic Multi-Document Reconciliation for Indian ITR Filing

**Problem:** Indian salaried taxpayers with capital market exposure face an asymmetric
information problem — the IT Department (via AIS) already knows their transactions,
but existing tools only process self-reported data. This gap causes 143(1) notices.

**Solution:** A locally-runnable multi-agent system that reconciles Form 16 + Bank Statement
+ AIS, detects notice risks, determines the correct ITR form, maps income to schedules,
and generates a CA-ready brief — with every claim citation-verified.

## Architecture

```
Documents (Bank CSV + Form 16 + AIS JSON)
    ↓
┌─────────────────────────────────────────────┐
│           ORCHESTRATOR (ReAct Loop)         │
│                                             │
│  ┌──────────┐   ┌───────────┐              │
│  │ AUDITOR  │──→│ OPTIMIZER │              │
│  │ Agent    │   │ Agent     │              │
│  └──────────┘   └───────────┘              │
│       ↓              ↓                      │
│  ┌───────────┐  ┌──────────┐               │
│  │COMPLIANCE │  │  CRITIC  │←── Hybrid     │
│  │ Agent     │  │  Agent   │    Retrieval  │
│  └───────────┘  └──────────┘   (PageIndex  │
│                                 + Vector)   │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  Tools: Calculator │ Retriever │ Verifier   │
└─────────────────────────────────────────────┘
    ↓
Outputs: Risk Report │ CA Brief │ Schedule Map │ ITR JSON
```

## Quick Start

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Pull LLM (pick one)
ollama pull qwen2.5:7b        # recommended
ollama pull llama3.1:8b       # alternative
ollama serve &

# Run on synthetic test data
python -m agents.orchestrator \
    --bank data/synthetic/sample_bank_statement.csv \
    --ais data/synthetic/sample_ais.json \
    --form16 data/synthetic/sample_form16.json

# Launch demo
streamlit run frontend/app.py

# Run IndianTaxBench evaluation
python -m benchmarks.indian_tax_bench.runner --skip-baselines
```

## Project Layout

```
FinITR-AI-v3/
├── agents/           ← Multi-agent orchestration (ReAct)
├── parsers/          ← Document parsers (CSV, Form 16, AIS, 26AS)
├── schedules/        ← ITR schedule builders (CG, VDA)
├── tools/            ← Calculator, PageIndex, VectorStore, Verifier
├── corpus/           ← Tax knowledge base + legal text
├── api/              ← FastAPI backend
├── frontend/         ← Streamlit UI
├── benchmarks/       ← IndianTaxBench (100+ adversarial cases)
├── evaluation/       ← Metrics, baselines, ablation
├── data/             ← Raw, processed, synthetic test fixtures
├── plans/            ← Weekly build plans (for AI coding agents)
└── tests/            ← Unit + integration tests
```

## Weekly Build Plans

See `plans/` directory for detailed week-by-week implementation prompts
designed for use with Claude Code and other AI coding assistants.

## Hardware

- Python 3.10+
- 8GB RAM minimum (16GB recommended)
- GPU optional (RTX 3060+ for faster LLM inference)
- Ollama with qwen2.5:7b or llama3.1:8b
