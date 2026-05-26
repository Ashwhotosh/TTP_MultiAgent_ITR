from agents.base import AgentContext
from agents.critic_agent import CriticAgent
from agents.orchestrator import Orchestrator
from tools.calculator import CalculatorTool
from tools.retriever import PageIndexRetriever
from tools.verifier import FaithfulnessVerifier

def test_critic_catches_wrong_regime_deduction():
    """CriticAgent should block 80C recommendation under New Regime."""
    ctx = AgentContext(gross_income=1500000)
    ctx.regime_comparison = {
        "recommended": "new",
        "new_regime": {
            "deductions_used": ["80C", "80CCD(2)"],
            "deductions": {"80C": 150000, "80CCD_2": 50000}
        }
    }
    tools = {
        "calculator": CalculatorTool(),
        "retriever": PageIndexRetriever(),
        "verifier": FaithfulnessVerifier()
    }
    critic = CriticAgent(tools=tools)
    result = critic.run(ctx)
    assert result.status == "needs_review"
    assert any("80C" in str(claim.get("section", "")) for claim in result.output["blocked_claims"])

def test_critic_catches_arithmetic_mismatch():
    """CriticAgent should flag when LLM states wrong tax amount."""
    ctx = AgentContext(gross_income=1500000)
    ctx.regime_comparison = {
        "recommended": "new",
        "new_regime": {
            "deductions": {"80CCD_2": 0.0, "80CCH": 0.0},
            "total_tax_liability": 5000.0  # Wrong tax liability (should be 124,800)
        }
    }
    tools = {
        "calculator": CalculatorTool(),
        "retriever": PageIndexRetriever(),
        "verifier": FaithfulnessVerifier()
    }
    critic = CriticAgent(tools=tools)
    result = critic.run(ctx)
    assert result.status == "needs_review"
    assert any(w.get("type") == "arithmetic_mismatch" for w in result.warnings)

def test_orchestrator_reruns_on_critic_feedback():
    """Orchestrator should re-invoke OptimizerAgent when critic rejects."""
    ctx = AgentContext()
    ctx.critic_feedback.append({
        "iteration": 0,
        "issues": [],
        "blocked_claims": [{"claim": {"section": "80C"}, "source": "optimizer"}]
    })
    orch = Orchestrator()
    assert orch._should_rerun("optimizer", ctx) is True
    assert orch._should_rerun("compliance", ctx) is False
