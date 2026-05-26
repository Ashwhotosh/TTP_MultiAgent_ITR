"""
orchestrator.py — ReAct-style agent orchestrator.

Routes between AuditorAgent → OptimizerAgent → ComplianceAgent → CriticAgent.
If the CriticAgent raises issues, the orchestrator re-invokes the relevant
agent with constraints from the critic feedback (up to max_iterations).

This is the ONLY entry point for running the full system.

CLI:
    python -m agents.orchestrator \
        --bank data/synthetic/sample_bank_statement.csv \
        --ais data/synthetic/sample_ais.json \
        --form16 data/synthetic/sample_form16.json

Programmatic:
    from agents.orchestrator import Orchestrator
    orch = Orchestrator()
    report = orch.run(bank_csv="path.csv", ais_json="path.json")
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .base import AgentContext, AgentResult
from .auditor_agent import AuditorAgent
from .optimizer_agent import OptimizerAgent
from .compliance_agent import ComplianceAgent
from .critic_agent import CriticAgent

LOG = "[ORCHESTRATOR]"


class Orchestrator:
    """
    ReAct-style orchestrator. Runs agents in sequence, then lets the
    CriticAgent review. If the critic flags issues, re-runs the
    offending agent with critic constraints appended to context.

    Loop:
        1. Auditor    → reconciliation + anomalies
        2. Optimizer  → regime comparison + CTC strategy
        3. Compliance → ITR form + schedule mapping
        4. Critic     → verify all claims
        5. IF critic says "needs_review" AND iteration < max:
              → re-run the flagged agent with critic feedback
              → re-run critic
        6. ELSE → finalize report
    """

    def __init__(
        self,
        ollama_model: str = None,
        max_iterations: int = 3,
        verbose: bool = True,
    ):
        if ollama_model is None:
            from tools.ollama_client import get_model_name
            ollama_model = get_model_name()
        self.ollama_model = ollama_model
        self.max_iterations = max_iterations
        self.verbose = verbose

        # Initialize tools (shared across agents)
        self._init_tools()

        # Initialize agents
        self.auditor = AuditorAgent(tools=self.tools)
        self.optimizer = OptimizerAgent(tools=self.tools)
        self.compliance = ComplianceAgent(tools=self.tools)
        self.critic = CriticAgent(tools=self.tools)

    def _init_tools(self):
        """Initialize shared tools: Calculator, Retriever, VectorStore, Verifier."""
        from tools.calculator import CalculatorTool
        from tools.retriever import PageIndexRetriever
        from tools.vector_store import VectorStore
        from tools.verifier import FaithfulnessVerifier

        self.tools = {
            "calculator": CalculatorTool(),
            "retriever": PageIndexRetriever(),
            "vector_store": VectorStore(),
            "verifier": FaithfulnessVerifier(),
        }
        self._say("Tools initialized")

    def run(
        self,
        bank_csv: str | None = None,
        ais_json: str | None = None,
        form16_json: str | None = None,
        form26as_json: str | None = None,
        gross_income: float = 0.0,
        basic_salary: float = 0.0,
        interview_answers: dict | None = None,
    ) -> dict[str, Any]:
        """
        Run the full multi-agent pipeline.

        Returns a structured report dict with all agent outputs,
        verification results, and the CA Brief data.
        """
        start_time = time.time()
        self._say("Starting FinITR-AI v3 pipeline")

        # ── Build initial context ──
        ctx = AgentContext(
            gross_income=gross_income,
            basic_salary=basic_salary or (gross_income * 0.40),
            interview_answers=interview_answers or {},
            max_iterations=self.max_iterations,
        )

        # ── Parse all documents into context ──
        self._parse_documents(ctx, bank_csv, ais_json, form16_json, form26as_json)

        # ── Agent Loop ──
        iteration = 0
        while iteration < self.max_iterations:
            ctx.iteration = iteration
            self._say(f"Iteration {iteration + 1}/{self.max_iterations}")

            # Stage 1: Auditor — reconciliation + anomaly detection
            if iteration == 0 or self._should_rerun("auditor", ctx):
                self._say("Running AuditorAgent")
                auditor_result = self.auditor._timed_run(ctx)
                ctx.agent_trace.append(self._trace(auditor_result))
                self._apply_result(ctx, auditor_result, "auditor")

            # Stage 2: Optimizer — regime comparison + CTC strategy
            if iteration == 0 or self._should_rerun("optimizer", ctx):
                self._say("Running OptimizerAgent")
                optimizer_result = self.optimizer._timed_run(ctx)
                ctx.agent_trace.append(self._trace(optimizer_result))
                self._apply_result(ctx, optimizer_result, "optimizer")

            # Stage 3: Compliance — ITR form + schedule mapping
            if iteration == 0 or self._should_rerun("compliance", ctx):
                self._say("Running ComplianceAgent")
                compliance_result = self.compliance._timed_run(ctx)
                ctx.agent_trace.append(self._trace(compliance_result))
                self._apply_result(ctx, compliance_result, "compliance")

            # Stage 4: Critic — verify everything
            self._say("Running CriticAgent")
            critic_result = self.critic._timed_run(ctx)
            ctx.agent_trace.append(self._trace(critic_result))

            # Check if critic is satisfied
            if critic_result.status == "success":
                self._say("CriticAgent satisfied — finalizing report")
                break

            # Critic found issues — record feedback for next iteration
            self._say(f"CriticAgent raised {len(critic_result.warnings)} issues — "
                      f"re-running flagged agents")
            ctx.critic_feedback.append({
                "iteration": iteration,
                "issues": critic_result.warnings,
                "blocked_claims": critic_result.output.get("blocked_claims", []),
            })

            iteration += 1

        # ── Build final report ──
        total_time = time.time() - start_time
        report = self._build_report(ctx, total_time)
        self._say(f"Pipeline complete in {total_time:.1f}s")
        return report

    # ────────────────────── Document Parsing ──────────────────────

    def _parse_documents(self, ctx: AgentContext, bank_csv, ais_json,
                         form16_json, form26as_json):
        """Parse all uploaded documents into the shared context."""
        if bank_csv:
            from parsers.csv_parser import CSVParser
            ctx.bank_transactions = CSVParser().parse(bank_csv)
            self._say(f"Parsed {len(ctx.bank_transactions)} bank transactions")

        if ais_json:
            from parsers.ais_parser import AISParser
            ctx.ais_data = AISParser().parse(ais_json)
            self._say(f"Parsed AIS: {len(ctx.ais_data.get('sft_entries', []))} SFT entries")

        if form16_json:
            form16_path = Path(form16_json)
            if form16_path.suffix.lower() == ".pdf":
                from parsers.form16_pdf_parser import Form16PDFParser
                ctx.form16_data = Form16PDFParser().parse(form16_path)
                self._say(f"Parsed Form 16 PDF: {ctx.form16_data.get('employer_name', 'Unknown')}")
                if ctx.form16_data.get("_warnings"):
                    for w in ctx.form16_data["_warnings"]:
                        self._say(f"  ! {w}")
            else:
                from parsers.form16_parser import Form16Parser
                ctx.form16_data = Form16Parser().parse(form16_json)
                self._say(f"Parsed Form 16 JSON: {ctx.form16_data.get('employer_name', 'N/A')}")

        if form26as_json:
            try:
                from parsers.form26as_parser import Form26ASParser
                ctx.form26as_data = Form26ASParser().parse(form26as_json)
                self._say("Parsed Form 26AS")
            except (ImportError, NotImplementedError):
                self._say("Form 26AS parser not yet implemented, skipping")

        # Auto-derive gross income from Form 16 if not provided
        if ctx.gross_income == 0 and ctx.form16_data:
            f16_gross = ctx.form16_data.get("gross_salary", 0.0)
            
            # Find salary in AIS to reconcile and handle input noise (like OCR rounding)
            ais_salary = 0.0
            if ctx.ais_data:
                for entry in ctx.ais_data.get("sft_entries", []):
                    if entry.get("type") == "salary":
                        ais_salary += entry.get("amount", 0.0)
                        
            # If Form 16 has a minor discrepancy (<= 3%) from AIS salary,
            # it's likely OCR noise or rounding. We trust the AIS value as the ground truth.
            if ais_salary > 0 and abs(f16_gross - ais_salary) <= 0.03 * ais_salary:
                self._say(f"Reconciled Form 16 gross salary ({f16_gross:,.0f}) with AIS salary ({ais_salary:,.0f}) due to minor difference (noise/OCR rounding).")
                ctx.gross_income = ais_salary
                f16_basic = ctx.form16_data.get("basic_salary", 0.0)
                if f16_basic > 0 and f16_gross > 0:
                    ctx.basic_salary = round(f16_basic * (ais_salary / f16_gross))
                else:
                    ctx.basic_salary = ais_salary * 0.40
            else:
                ctx.gross_income = f16_gross
                ctx.basic_salary = ctx.form16_data.get("basic_salary", ctx.gross_income * 0.4)
            self._say(f"Derived gross income: {ctx.gross_income:,.0f}")

    # ────────────────────── Helper Methods ──────────────────────

    def _should_rerun(self, agent_name: str, ctx: AgentContext) -> bool:
        """Check if critic feedback requires re-running a specific agent."""
        if not ctx.critic_feedback:
            return False
        latest = ctx.critic_feedback[-1]
        # Check warnings / issues list
        if any(agent_name in issue.get("source", "") for issue in latest.get("issues", [])):
            return True
        # Check blocked claims list
        if any(agent_name in claim.get("source", "") for claim in latest.get("blocked_claims", [])):
            return True
        return False

    def _apply_result(self, ctx: AgentContext, result: AgentResult, agent_name: str):
        """Apply an agent's output to the shared context."""
        if result.status == "error":
            self._say(f"  WARNING: {agent_name} failed -- {result.errors}")
            return

        output = result.output

        if agent_name == "auditor":
            # AuditorAgent writes directly to ctx in its run() method,
            # but also populate from result output as backup
            if "reconciliation" in output and not ctx.reconciliation:
                ctx.reconciliation = output["reconciliation"]
            if "anomalies" in output and not ctx.anomalies:
                ctx.anomalies = output["anomalies"]
            if "risk_score" in output and not ctx.risk_score:
                ctx.risk_score = output["risk_score"]
            if "interview_questions" in output and not ctx.interview_questions:
                ctx.interview_questions = output["interview_questions"]

        elif agent_name == "optimizer":
            if "regime_comparison" in output:
                ctx.regime_comparison = output["regime_comparison"]
            if "ctc_strategy" in output:
                ctx.ctc_strategy = output["ctc_strategy"]

        elif agent_name == "compliance":
            if "itr_form" in output:
                ctx.itr_form_recommendation = output["itr_form"]
            if "schedule_mapping" in output:
                ctx.schedule_mapping = output["schedule_mapping"]

    def _trace(self, result: AgentResult) -> dict:
        """Create an audit trace entry."""
        return {
            "agent": result.agent_name,
            "status": result.status,
            "duration_sec": result.duration_sec,
            "tools_called": result.tools_called,
            "warnings": result.warnings,
            "errors": result.errors,
        }

    def _build_report(self, ctx: AgentContext, total_time: float) -> dict:
        """Assemble the final structured report from context."""
        report = {
            "version": "3.0",
            "assessment_year": ctx.assessment_year,
            "gross_income": ctx.gross_income,
            "basic_salary": ctx.basic_salary,

            # Document inputs summary
            "documents": {
                "bank_transactions": len(ctx.bank_transactions),
                "form16_present": bool(ctx.form16_data),
                "ais_present": bool(ctx.ais_data),
                "form26as_present": bool(ctx.form26as_data),
            },

            # Agent outputs
            "reconciliation": ctx.reconciliation,
            "anomalies": ctx.anomalies,
            "regime_comparison": ctx.regime_comparison,
            "ctc_strategy": ctx.ctc_strategy,
            "itr_form": ctx.itr_form_recommendation,
            "schedule_mapping": ctx.schedule_mapping,
            "risk_score": ctx.risk_score,
            "deduction_gaps": ctx.deduction_gaps,

            # Interview questions (from AuditorAgent)
            "interview_questions": ctx.interview_questions,

            # Verification
            "verification": ctx.verification_results,
            "critic_feedback": ctx.critic_feedback,

            # Raw parsed document data for notice predictor feature extraction
            "form16_data": ctx.form16_data,
            "ais_data": ctx.ais_data,

            # Metadata
            "agent_trace": ctx.agent_trace,
            "iterations": ctx.iteration + 1,
            "total_time_sec": total_time,
        }

        # Notice prediction via trained ML classifier
        try:
            from models.notice_predictor import predict as predict_notice, MODEL_PATH
            if MODEL_PATH.exists():
                notice_pred = predict_notice(report)
                report["notice_prediction"] = notice_pred
                self._say(
                    f"Notice probability: {notice_pred['notice_probability']:.1%} "
                    f"({notice_pred['risk_tier']})"
                )
            else:
                report["notice_prediction"] = None
                self._say("Notice predictor model not trained yet")
        except Exception as e:
            self._say(f"Notice predictor error: {e}")
            report["notice_prediction"] = None

        return report

    def _say(self, msg: str):
        if self.verbose:
            print(f"{LOG} {msg}")


# ──────────────────────────── CLI ────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="FinITR-AI v3 — Multi-Agent Pipeline")
    ap.add_argument("--bank", help="Path to bank statement CSV")
    ap.add_argument("--ais", help="Path to AIS JSON")
    ap.add_argument("--form16", help="Path to Form 16 PDF or JSON")
    ap.add_argument("--form26as", help="Path to Form 26AS JSON")
    ap.add_argument("--income", type=float, default=0, help="Gross income (auto-derived from Form 16 if not given)")
    ap.add_argument("--basic", type=float, default=0, help="Basic salary")
    ap.add_argument("--output", default=None, help="Output JSON path")
    ap.add_argument("--model", default=None, help="Ollama model")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    orch = Orchestrator(ollama_model=args.model, verbose=not args.quiet)
    report = orch.run(
        bank_csv=args.bank,
        ais_json=args.ais,
        form16_json=args.form16,
        form26as_json=args.form26as,
        gross_income=args.income,
        basic_salary=args.basic,
    )

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2, default=str))
        print(f"{LOG} Report saved -> {args.output}")
    else:
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
