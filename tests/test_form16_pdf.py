"""Tests for the Form 16 PDF parser."""
import pytest
from pathlib import Path


def test_parser_imports():
    """Parser module can be imported."""
    from parsers.form16_pdf_parser import Form16PDFParser
    parser = Form16PDFParser()
    assert parser is not None


def test_parser_handles_missing_file():
    """Missing file raises FileNotFoundError."""
    from parsers.form16_pdf_parser import Form16PDFParser
    with pytest.raises(FileNotFoundError):
        Form16PDFParser().parse("nonexistent.pdf")


def test_parser_output_shape():
    """Parser output has all expected keys."""
    from parsers.form16_pdf_parser import Form16PDFParser
    pdf_path = Path("data/synthetic/sample_form16.pdf")
    if not pdf_path.exists():
        pytest.skip("No sample Form 16 PDF available. Add one to data/synthetic/")

    result = Form16PDFParser().parse(pdf_path)

    required_keys = [
        "employer_name", "employee_pan", "gross_salary",
        "basic_salary", "hra_received", "standard_deduction",
        "tds_deducted", "regime", "deductions_claimed"
    ]
    for key in required_keys:
        assert key in result, f"Missing key: {key}"

    assert result["regime"] in ("old", "new")
    assert result["gross_salary"] >= 0


def test_regime_detection():
    """Regime detection works on sample text."""
    from parsers.form16_pdf_parser import Form16PDFParser
    parser = Form16PDFParser()

    new_text = "Tax computed under Section 115BAC of the Income Tax Act"
    assert parser._detect_regime(new_text) == "new"

    old_text = "Tax computed under Old Tax Regime with Chapter VI-A deductions"
    assert parser._detect_regime(old_text) == "old"


def test_pattern_extraction():
    """Table-row KV extraction and metadata patterns work correctly."""
    from parsers.form16_pdf_parser import Form16PDFParser
    parser = Form16PDFParser()

    # Metadata extraction (string fields)
    page_text = (
        "TAN of the Deductor DELT12345A\n"
        "PAN of the Employee ABCDE1234F\n"
        "Assessment Year 2026-27\n"
    )
    extracted = parser._apply_metadata_patterns(page_text)
    assert extracted.get("employer_tan") == "DELT12345A"
    assert extracted.get("employee_pan") == "ABCDE1234F"

    # Table-row KV extraction (numeric fields)
    table_rows = [
        "Gross Salary | 22,00,000.00",
        "Standard Deduction under section 16(ia) | 75,000.00",
        "Tax Deducted at Source (TDS) | 2,50,000.00",
        "Basic Salary | 11,00,000.00",
    ]
    numeric = parser._extract_from_table_rows(table_rows)
    assert numeric.get("gross_salary") == 2200000.0
    assert numeric.get("standard_deduction") == 75000.0
    assert numeric.get("tds_deducted") == 250000.0
    assert numeric.get("basic_salary") == 1100000.0
