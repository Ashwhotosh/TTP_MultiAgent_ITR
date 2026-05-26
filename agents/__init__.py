"""
FinITR-AI v3 — Multi-Agent System for Indian ITR Filing.

Agents:
    - Orchestrator:     ReAct-style planner that routes between agents
    - AuditorAgent:     Reconciles Form 16 + Bank Stmt + AIS
    - OptimizerAgent:   Old vs New regime comparison, CTC restructuring
    - ComplianceAgent:  ITR form selection, schedule mapping
    - CriticAgent:      Faithfulness verification, hallucination blocking
"""
from .orchestrator import Orchestrator
from .auditor_agent import AuditorAgent
from .optimizer_agent import OptimizerAgent
from .compliance_agent import ComplianceAgent
from .critic_agent import CriticAgent

__all__ = [
    "Orchestrator",
    "AuditorAgent",
    "OptimizerAgent",
    "ComplianceAgent",
    "CriticAgent",
]
