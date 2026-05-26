"""Tests for the real-world transaction classifier."""
import pytest
from pathlib import Path

CLASSIFIER_AVAILABLE = Path("models/transaction_classifier_v2.pkl").exists()


def test_normalizer_strips_noise():
    from parsers.description_normalizer import DescriptionNormalizer
    norm = DescriptionNormalizer()

    noisy = "WDL TFR UPI/DR/48188486544/ZOMATO/UTIB/ETERNAL/paym009769258663 AT 11669 SHIVAJI NAGAR NASIK"
    result = norm.normalize(noisy)

    assert "ZOMATO" in result.cleaned
    assert "48188486544" not in result.cleaned
    assert "paym009769258663" not in result.cleaned.lower()
    assert result.transaction_method == "UPI"
    assert result.direction == "debit"


def test_normalizer_handles_hinglish():
    from parsers.description_normalizer import DescriptionNormalizer
    norm = DescriptionNormalizer()

    cases = [
        ("UPI/DR/AMAN JUICEWALA/SHOP NO 4", "AMAN JUICEWALA"),
        ("UPI/DR/SHARMA SWEET MART/PUNE", "SHARMA SWEET MART"),
        ("WDL TFR UPI/DR/KAKA HALWAI/PUNE", "KAKA HALWAI"),
    ]
    for raw, expected_in_cleaned in cases:
        r = norm.normalize(raw)
        assert expected_in_cleaned in r.cleaned, f"Failed: {raw} -> {r.cleaned}"


@pytest.mark.skipif(not CLASSIFIER_AVAILABLE, reason="Classifier not trained")
def test_classifier_handles_noisy_zomato():
    from models.transaction_classifier_v2 import RealWorldTransactionClassifier
    clf = RealWorldTransactionClassifier()
    clf.load()

    result = clf.classify(
        "WDL TFR UPI/DR/48188486544/ZOMATO/UTIB/ETERNAL/paym009769258663 AT 11669 SHIVAJI NAGAR NASIK"
    )
    assert result["label"] == "REGULAR_EXPENSE"
    assert result["tax_relevance"] == "none"


@pytest.mark.skipif(not CLASSIFIER_AVAILABLE, reason="Classifier not trained")
def test_classifier_handles_hinglish_vendors():
    from models.transaction_classifier_v2 import RealWorldTransactionClassifier
    clf = RealWorldTransactionClassifier()
    clf.load()

    hinglish_cases = [
        "UPI/DR/AMAN JUICEWALA/SHOP NO 4",
        "UPI/DR/SHARMA SWEET MART/PUNE",
        "UPI/DR/GUPTA KIRANA STORE",
        "UPI/DR/KAKA HALWAI/PUNE CAMP",
        "UPI/DR/MAA TARA CYCLE STORES",
    ]
    for desc in hinglish_cases:
        result = clf.classify(desc)
        assert result["label"] not in ("CRYPTO_TRANSACTION", "FREELANCE_INCOME", "CAPITAL_MARKET"), (
            f"{desc} misclassified as {result['label']}"
        )
        assert result["tax_relevance"] in ("none", "deduction_opportunity"), (
            f"{desc} got tax_relevance={result['tax_relevance']}"
        )


@pytest.mark.skipif(not CLASSIFIER_AVAILABLE, reason="Classifier not trained")
def test_classifier_catches_unseen_crypto():
    from models.transaction_classifier_v2 import RealWorldTransactionClassifier
    clf = RealWorldTransactionClassifier()
    clf.load()

    result = clf.classify("UPI/DR/MUDREX/CRYPTO INVESTMENT")
    assert result["label"] == "CRYPTO_TRANSACTION"


@pytest.mark.skipif(not CLASSIFIER_AVAILABLE, reason="Classifier not trained")
def test_classifier_handles_noisy_salary():
    from models.transaction_classifier_v2 import RealWorldTransactionClassifier
    clf = RealWorldTransactionClassifier()
    clf.load()

    result = clf.classify("WDL TFR NEFT-SALARY-INFOSYS BPM LTD-MAR25-UTR123456")
    assert result["label"] == "SALARY_INCOME"


@pytest.mark.skipif(not CLASSIFIER_AVAILABLE, reason="Classifier not trained")
def test_stage_distribution():
    """Most transactions should be handled by Stage 2 (pattern) -- fast path."""
    from models.transaction_classifier_v2 import RealWorldTransactionClassifier
    clf = RealWorldTransactionClassifier()
    clf.load()

    test_cases = [
        "UPI/DR/WAZIRX/CRYPTO",
        "UPI/DR/ZERODHA EQUITY",
        "NEFT/SALARY/INFOSYS",
        "ACH/HDFC HOUSING LOAN EMI",
        "INT CR SBI SAVINGS Q1",
        "UPI/DR/AMAN JUICEWALA",
    ]
    stages = [clf.classify(t)["stage"] for t in test_cases]
    pattern_count = sum(1 for s in stages if s == "pattern")
    assert pattern_count >= 4, f"Expected >=4 pattern hits, got {pattern_count}: {stages}"
