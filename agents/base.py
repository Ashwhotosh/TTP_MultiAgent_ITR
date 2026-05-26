"""
base.py — Abstract base class for all FinITR agents.

Every agent:
  - Has a name and role description
  - Receives a shared AgentContext (accumulated state from prior agents)
  - Returns an AgentResult with structured output + reasoning trace
  - Can call tools (Calculator, Retriever, VectorStore)
  - Logs every decision for auditability
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    """Shared state passed between agents. Each agent reads what it needs
    and appends its own output."""

    # ── Document inputs ──
    bank_transactions: list[dict] = field(default_factory=list)
    form16_data: dict = field(default_factory=dict)
    ais_data: dict = field(default_factory=dict)
    form26as_data: dict = field(default_factory=dict)

    # ── Accumulated agent outputs ──
    reconciliation: dict = field(default_factory=dict)       # AuditorAgent output
    anomalies: list[dict] = field(default_factory=list)      # AuditorAgent flagged items
    interview_questions: list[dict] = field(default_factory=list)
    interview_answers: dict = field(default_factory=dict)
    regime_comparison: dict = field(default_factory=dict)     # OptimizerAgent output
    ctc_strategy: dict = field(default_factory=dict)          # OptimizerAgent output
    itr_form_recommendation: dict = field(default_factory=dict)  # ComplianceAgent
    schedule_mapping: list[dict] = field(default_factory=list)   # ComplianceAgent
    verification_results: list[dict] = field(default_factory=list)  # CriticAgent
    risk_score: dict = field(default_factory=dict)
    deduction_gaps: dict = field(default_factory=dict)

    # ── User profile ──
    gross_income: float = 0.0
    basic_salary: float = 0.0
    employer_nps: float = 0.0
    assessment_year: str = "2026-27"

    # ── Orchestrator state ──
    iteration: int = 0
    max_iterations: int = 3
    critic_feedback: list[dict] = field(default_factory=list)
    agent_trace: list[dict] = field(default_factory=list)


@dataclass
class AgentResult:
    """Output from a single agent invocation."""
    agent_name: str
    status: str                    # "success" | "needs_review" | "error"
    output: dict = field(default_factory=dict)
    reasoning: str = ""
    tools_called: list[str] = field(default_factory=list)
    duration_sec: float = 0.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    """Abstract base for all agents."""

    def __init__(self, name: str, role: str, tools: dict[str, Any] | None = None):
        self.name = name
        self.role = role
        self.tools = tools or {}

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult:
        """Execute the agent's task given current context."""
        ...

    def _log(self, msg: str) -> None:
        print(f"[{self.name}] {msg}")

    def _timed_run(self, ctx: AgentContext) -> AgentResult:
        """Wrapper that times execution and catches errors."""
        start = time.time()
        try:
            result = self.run(ctx)
            result.duration_sec = time.time() - start
            return result
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                status="error",
                errors=[str(e)],
                duration_sec=time.time() - start,
            )

    def _call_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """Invoke a registered tool by name."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not registered with {self.name}")
        return self.tools[tool_name](*args, **kwargs)
