"""
make_diagrams.py -- Generate the 6 thesis diagrams as PNGs via Graphviz.

Outputs (into 2.Thesis_Image/):
    block_diagram.png      architecture.png
    module1_flow.png       module2_flow.png
    module3_flow.png       module4_flow.png

These match the captions in the Thesis_Text drafts and the specs in
IMAGE_PLAN.txt. Labels are exact (section names, percentages) so they are
thesis-grade -- no AI-image garbling.

REQUIREMENTS:
    1. Graphviz system binary (provides `dot`):
         winget install Graphviz.Graphviz
       (or download from https://graphviz.org/download/), then open a NEW
       terminal so `dot` is on PATH. Verify with:  dot -V
    2. Python wrapper:  pip install graphviz

RUN:
    python Thesis_MP/make_diagrams.py
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from graphviz import Digraph
except ImportError:
    sys.exit("Missing dependency. Run:  pip install graphviz")

# ---- consistent palette (see IMAGE_PLAN.txt) -------------------------------
AGENT  = {"style": "filled,rounded", "shape": "box", "fillcolor": "#D6E4FF",
          "color": "#2A4B8D", "fontcolor": "#11224D", "penwidth": "1.6"}
TOOL   = {"style": "filled,rounded", "shape": "box", "fillcolor": "#D8F3DC",
          "color": "#2D6A4F", "fontcolor": "#13351F", "penwidth": "1.6"}
DATA   = {"style": "filled", "shape": "box", "fillcolor": "#E9ECEF",
          "color": "#495057", "fontcolor": "#212529", "penwidth": "1.4"}
CTX    = {"style": "filled,rounded,bold", "shape": "box", "fillcolor": "#FFF3BF",
          "color": "#B8860B", "fontcolor": "#5C4400", "penwidth": "2.2"}
ML     = {"style": "filled,rounded", "shape": "box", "fillcolor": "#E5DBFF",
          "color": "#5F3DC4", "fontcolor": "#2E1A66", "penwidth": "1.6"}
CRIT   = {"style": "filled,rounded", "shape": "box", "fillcolor": "#FFE3E3",
          "color": "#B91C1C", "fontcolor": "#6A0F0F", "penwidth": "1.6"}
DEC    = {"style": "filled", "shape": "diamond", "fillcolor": "#FFE8CC",
          "color": "#B45309", "fontcolor": "#5C3200", "penwidth": "1.6"}
GO     = {"style": "filled,rounded", "shape": "box", "fillcolor": "#C3FAE8",
          "color": "#0CA678", "fontcolor": "#0B3D2E", "penwidth": "1.8"}
# risk-band colours
BAND = {
    "LOW":      {"fillcolor": "#B2F2BB", "color": "#2B8A3E", "fontcolor": "#1B4332"},
    "MEDIUM":   {"fillcolor": "#FFEC99", "color": "#E67700", "fontcolor": "#5C4400"},
    "HIGH":     {"fillcolor": "#FFC078", "color": "#D9480F", "fontcolor": "#7A2E0E"},
    "CRITICAL": {"fillcolor": "#FFA8A8", "color": "#C92A2A", "fontcolor": "#6A0F0F"},
}

OUT = Path(__file__).resolve().parent / "2.Thesis_Image"

COMMON_GRAPH = {"fontname": "Helvetica", "dpi": "200", "bgcolor": "white",
                "fontsize": "11"}
COMMON_NODE  = {"fontname": "Helvetica", "fontsize": "10", "margin": "0.12,0.07"}
COMMON_EDGE  = {"fontname": "Helvetica", "fontsize": "9", "color": "#343A40",
                "arrowsize": "0.8"}


def _new(name: str, rankdir: str = "TB") -> Digraph:
    g = Digraph(name)
    g.attr(rankdir=rankdir, **COMMON_GRAPH)
    g.attr("node", **COMMON_NODE)
    g.attr("edge", **COMMON_EDGE)
    return g


def _render(g: Digraph, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = g.render(filename=name, directory=str(OUT), format="png",
                    cleanup=True)
    print(f"  wrote {path}")


# ===========================================================================
# 1. block_diagram.png  -- data flow, AgentContext as the hub
# ===========================================================================
def block_diagram() -> None:
    g = _new("block_diagram", rankdir="TB")
    g.attr(label="FinITR-AI -- System Block Diagram (data flow)",
           labelloc="t", fontsize="14")

    with g.subgraph(name="cluster_in") as c:
        c.attr(label="Input Documents", color="#ADB5BD", style="rounded")
        for nid, lbl in [("d_f16", "Form 16\n(PDF / JSON)"),
                         ("d_ais", "AIS\n(JSON)"),
                         ("d_bank", "Bank Statement\n(CSV)"),
                         ("d_26as", "Form 26AS\n(JSON, optional)")]:
            c.node(nid, lbl, **DATA)

    with g.subgraph(name="cluster_parse") as c:
        c.attr(label="Parsers", color="#ADB5BD", style="rounded")
        for nid, lbl in [("p_f16", "Form16 Parser"), ("p_ais", "AIS Parser"),
                         ("p_bank", "CSV Parser"), ("p_26as", "Form26AS Parser")]:
            c.node(nid, lbl, **DATA)

    g.node("ctx", "AgentContext  (shared state)\n"
                  "gross_income | bank_transactions | ais_data | form16_data\n"
                  "reconciliation | regime_comparison | schedule_mapping\n"
                  "risk_score | agent_trace | critic_feedback", **CTX)

    with g.subgraph(name="cluster_agents") as c:
        c.attr(label="Multi-Agent Core (ReAct loop)", color="#2A4B8D",
               style="rounded")
        c.node("a_aud", "Auditor", **AGENT)
        c.node("a_opt", "Optimizer", **AGENT)
        c.node("a_com", "Compliance", **AGENT)
        c.node("a_cri", "Critic", **CRIT)
        c.edge("a_aud", "a_opt")
        c.edge("a_opt", "a_com")
        c.edge("a_com", "a_cri")
        c.edge("a_cri", "a_aud", label="re-run (<=3x)", style="dashed",
               color="#B45309", fontcolor="#B45309", constraint="false")

    with g.subgraph(name="cluster_ml") as c:
        c.attr(label="Inline ML Models", color="#5F3DC4", style="rounded")
        c.node("m_tc", "TransactionClassifier\n(3-stage)", **ML)
        c.node("m_np", "NoticePredictor\n(LogReg, 14 features)", **ML)

    with g.subgraph(name="cluster_out") as c:
        c.attr(label="Output Layer", color="#ADB5BD", style="rounded")
        c.node("o_rep", "Final Report", **DATA)
        c.node("o_itr", "ITR-2 JSON", **DATA)
        c.node("o_brief", "CA Brief (PDF)", **DATA)
        c.node("o_api", "FastAPI", **DATA)
        c.node("o_ui", "Streamlit UI", **DATA)

    # cross-band flow (representative edges)
    g.edge("d_f16", "p_f16"); g.edge("d_ais", "p_ais")
    g.edge("d_bank", "p_bank"); g.edge("d_26as", "p_26as")
    for p in ("p_f16", "p_ais", "p_bank", "p_26as"):
        g.edge(p, "ctx")
    g.edge("ctx", "a_aud", label="Form16 vs AIS <=3% -> trust AIS")
    g.edge("a_cri", "ctx", label="verified", color="#0CA678",
           fontcolor="#0CA678")
    g.edge("ctx", "m_tc", style="dotted"); g.edge("ctx", "m_np", style="dotted")
    g.edge("m_np", "o_rep"); g.edge("ctx", "o_rep")
    g.edge("o_rep", "o_itr"); g.edge("o_rep", "o_brief")
    g.edge("o_rep", "o_api"); g.edge("o_api", "o_ui")
    _render(g, "block_diagram")


# ===========================================================================
# 2. architecture.png  -- control flow, ReAct loop + shared tools
# ===========================================================================
def architecture() -> None:
    g = _new("architecture", rankdir="LR")
    g.attr(label="FinITR-AI -- System Architecture (control flow)",
           labelloc="t", fontsize="14")

    g.node("orch", "Orchestrator\n(ReAct loop)", **AGENT)

    with g.subgraph(name="cluster_pipe") as c:
        c.attr(label="Agent Pipeline", color="#2A4B8D", style="rounded")
        c.node("aud", "AUDITOR", **AGENT)
        c.node("opt", "OPTIMIZER", **AGENT)
        c.node("com", "COMPLIANCE", **AGENT)
        c.node("cri", "CRITIC", **CRIT)
        c.edge("aud", "opt"); c.edge("opt", "com"); c.edge("com", "cri")

    g.node("done", "Finalize report", **GO)

    with g.subgraph(name="cluster_tools") as c:
        c.attr(label="Shared Deterministic Tools", color="#2D6A4F",
               style="rounded")
        c.node("t_calc", "CalculatorTool\n(deterministic FY25-26 engine)", **TOOL)
        c.node("t_ret", "PageIndex Retriever\n(RAG, 80+ nodes)", **TOOL)
        c.node("t_vec", "VectorStore\n(ChromaDB)", **TOOL)
        c.node("t_ver", "FaithfulnessVerifier\n(NLI / DeBERTa)", **TOOL)

    g.edge("orch", "aud", label="run")
    g.edge("cri", "orch", label="issues -> re-run\nflagged agent (max 3)",
           style="dashed", color="#B45309", fontcolor="#B45309")
    g.edge("cri", "done", label="satisfied", color="#0CA678",
           fontcolor="#0CA678")

    for a in ("aud", "opt", "com", "cri"):
        for t in ("t_calc", "t_ret", "t_vec", "t_ver"):
            g.edge(a, t, style="dotted", arrowhead="none", color="#CED4DA",
                   constraint="false")

    g.node("note", "LLM = qwen2.5:7b via Ollama\n"
                   "language only; arithmetic via CalculatorTool",
           shape="note", style="filled", fillcolor="#FFF9DB",
           color="#B8860B", fontsize="9")
    _render(g, "architecture")


# ===========================================================================
# 3. module1_flow.png  -- Auditor
# ===========================================================================
def module1_flow() -> None:
    g = _new("module1_flow", rankdir="TB")
    g.attr(label="Module One -- Auditor Agent", labelloc="t", fontsize="14")

    g.node("in", "Bank transactions + AIS + Form 16", **DATA)
    g.node("clf", "TransactionClassifier (3-stage)\n"
                  "Regex (56.3%, <1ms) -> kNN MiniLM (26%) -> LLM fallback (18%)\n"
                  "-> 12 income labels", **AGENT)
    g.node("rec", "Reconcile AIS SFT entries vs Form 16", **AGENT)
    g.node("led", "Reconciliation Ledger\n(matched / AIS-only / mismatch)", **DATA)
    g.node("risk", "Additive Risk Scoring\n"
                   "crypto=60  CG=55  AIS mismatch=25  cash=15", **AGENT)
    g.node("q", "Generate interview questions\n(items needing user input)", **AGENT)

    with g.subgraph(name="cluster_band") as c:
        c.attr(label="Risk band (score 0-100)", color="#ADB5BD", style="rounded")
        c.node("b_low", "LOW (<20)", style="filled", shape="box", **BAND["LOW"])
        c.node("b_med", "MEDIUM (<50)", style="filled", shape="box", **BAND["MEDIUM"])
        c.node("b_high", "HIGH (<75)", style="filled", shape="box", **BAND["HIGH"])
        c.node("b_crit", "CRITICAL (>=75)", style="filled", shape="box", **BAND["CRITICAL"])

    g.edge("in", "clf"); g.edge("clf", "rec"); g.edge("rec", "led")
    g.edge("led", "risk"); g.edge("risk", "b_low"); g.edge("risk", "b_med")
    g.edge("risk", "b_high"); g.edge("risk", "b_crit")
    g.edge("led", "q", style="dashed", constraint="false")
    _render(g, "module1_flow")


# ===========================================================================
# 4. module2_flow.png  -- Optimizer
# ===========================================================================
def module2_flow() -> None:
    g = _new("module2_flow", rankdir="TB")
    g.attr(label="Module Two -- Optimizer Agent", labelloc="t", fontsize="14")

    g.node("in", "Gross income + deductions + basic salary", **DATA)
    g.node("calc", "CalculatorTool  (deterministic, no LLM math)", **TOOL)
    g.node("old", "OLD REGIME\nstd Rs.50,000; 80C/80D/24(b)/HRA;\n"
                  "slabs; 87A (<=5L); surcharge; 4% cess", **AGENT)
    g.node("new", "NEW REGIME (115BAC)\nstd Rs.75,000; 80CCD(2)/80CCH;\n"
                  "slabs; 87A (<=12L)+marginal relief; surcharge; 4% cess", **AGENT)
    g.node("cmp", "Compare total liability", **AGENT)
    g.node("rec", "Recommend lower-tax regime", **GO)
    g.node("ctc", "CTC restructuring\nemployer NPS 80CCD(2) up to 10% of basic\n"
                  "-> annual savings", **AGENT)
    g.node("llm", "LLM phrases explanation\n(template fallback if Ollama down)", **AGENT)

    g.edge("in", "calc")
    g.edge("calc", "old"); g.edge("calc", "new")
    g.edge("old", "cmp"); g.edge("new", "cmp")
    g.edge("cmp", "rec"); g.edge("rec", "llm")
    g.edge("in", "ctc", style="dashed", constraint="false")
    g.edge("ctc", "llm", style="dashed", constraint="false")
    _render(g, "module2_flow")


# ===========================================================================
# 5. module3_flow.png  -- Compliance
# ===========================================================================
def module3_flow() -> None:
    g = _new("module3_flow", rankdir="TB")
    g.attr(label="Module Three -- Compliance Agent", labelloc="t", fontsize="14")

    g.node("in", "Income types identified by Auditor", **DATA)
    g.node("d_bus", "Business income?", **DEC)
    g.node("d_pre", "Presumptive (44ADA)?", **DEC)
    g.node("d_cg", "Capital gains / crypto / foreign?", **DEC)
    g.node("itr3", "ITR-3", **GO)
    g.node("itr4", "ITR-4", **GO)
    g.node("itr2", "ITR-2", **GO)
    g.node("itr1", "ITR-1 (Sahaj)", **GO)

    g.edge("in", "d_bus")
    g.edge("d_bus", "itr3", label="yes")
    g.edge("d_bus", "d_pre", label="no")
    g.edge("d_pre", "itr4", label="yes")
    g.edge("d_pre", "d_cg", label="no")
    g.edge("d_cg", "itr2", label="yes")
    g.edge("d_cg", "itr1", label="no")

    g.node("sched", "Signal-based Schedule Mapping\n"
                    "Schedule Salary (if salary)\n"
                    "Schedule CG  <- capital-gains signal\n"
                    "Schedule VDA <- crypto signal\n"
                    "Schedule OS  <- ONLY if bank INT CR / AIS SFT-004 /\n"
                    "                deduction evidence  (no blanket guess)", **AGENT)
    g.node("call", "Signal-based inference -> precision 96.2%",
           shape="note", style="filled", fillcolor="#FFF9DB", color="#B8860B",
           fontsize="9")
    for f in ("itr1", "itr2", "itr3", "itr4"):
        g.edge(f, "sched", style="dotted", arrowhead="none", color="#CED4DA",
               constraint="false")
    g.edge("sched", "call", style="dashed", arrowhead="none", constraint="false")
    _render(g, "module3_flow")


# ===========================================================================
# 6. module4_flow.png  -- Critic
# ===========================================================================
def module4_flow() -> None:
    g = _new("module4_flow", rankdir="TB")
    g.attr(label="Module Four -- Critic Agent", labelloc="t", fontsize="14")

    g.node("in", "Claims from Auditor / Optimizer / Compliance", **DATA)
    g.node("ver", "FaithfulnessVerifier (NLI; keyword fallback)\n"
                  "check each claim vs (a) source documents\n"
                  "and (b) PageIndex legal corpus", **CRIT)
    g.node("dec", "All claims\ngrounded?", **DEC)
    g.node("ok", "Finalize report", **GO)
    g.node("block", "Block ungrounded claim\n(e.g. 80C under New Regime)", **CRIT)
    g.node("record", "Record offending agent + constraints", **AGENT)
    g.node("rerun", "Orchestrator re-runs that agent", **AGENT)
    g.node("call", "Removing the Critic: hallucination 6.8% -> 18.4%",
           shape="note", style="filled", fillcolor="#FFF9DB", color="#B8860B",
           fontsize="9")

    g.edge("in", "ver"); g.edge("ver", "dec")
    g.edge("dec", "ok", label="yes", color="#0CA678", fontcolor="#0CA678")
    g.edge("dec", "block", label="no", color="#B91C1C", fontcolor="#B91C1C")
    g.edge("block", "record"); g.edge("record", "rerun")
    g.edge("rerun", "ver", label="max 3 iterations", style="dashed",
           color="#B45309", fontcolor="#B45309", constraint="false")
    g.edge("dec", "call", style="dashed", arrowhead="none", constraint="false")
    _render(g, "module4_flow")


def main() -> None:
    print("Generating thesis diagrams ->", OUT)
    block_diagram()
    architecture()
    module1_flow()
    module2_flow()
    module3_flow()
    module4_flow()
    print("Done. 6 PNGs written to 2.Thesis_Image/")


if __name__ == "__main__":
    main()
