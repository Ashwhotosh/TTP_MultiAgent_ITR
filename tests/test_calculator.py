"""Tests for the Calculator tool — both regimes."""

def test_new_regime_basic():
    """10L income under New Regime should have 0 tax (87A rebate)."""
    # TODO: [WEEK 1] Implement after migrating calculator
    pass

def test_new_regime_marginal_relief():
    """12.5L income should trigger marginal relief."""
    pass

def test_old_regime_with_deductions():
    """15L with 80C=1.5L, 80D=25k, HRA=2L under Old Regime."""
    pass

def test_hra_exemption():
    """HRA exemption = min(actual, 50% basic, rent-10% basic)."""
    pass
