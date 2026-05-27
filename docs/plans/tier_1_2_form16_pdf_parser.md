# Tier 1.2: Form 16 PDF Parser — Real-World Usability

## Goal
Build a `pdfplumber`-based Form 16 parser that extracts salary breakup, deductions, and TDS from actual employer-issued PDF Form 16. Without this, your project cannot be used on real data — only on JSON test files. Adding this converts the project from prototype to usable tool.

**Time estimate**: 3 hours
**Files modified**: 2
**Files created**: 2 (parser + test)
**Acceptance**: Parse a real Form 16 PDF and produce identical structure to the existing JSON-based Form16Parser output.

---

## Background: Form 16 Structure

Every employer-issued Form 16 follows CBDT-prescribed format with two parts:

**Part A** (1-2 pages, contains):
- Employer name, TAN, address
- Employee name, PAN
- Period of employment
- Quarterly TDS deduction summary (4 quarters)
- Total tax deducted

**Part B** (2-4 pages, contains):
- Detailed salary breakup (basic, HRA, special allowance, LTA, perquisites)
- Exemptions claimed (HRA 10(13A), LTA 10(5), etc.)
- Standard deduction (75k new / 50k old)
- Chapter VI-A deductions (80C, 80D, 80CCD, etc.)
- Income tax computation with slabs
- Surcharge, cess, total tax payable
- TDS adjusted, balance payable/refundable

The challenge: each employer has slightly different formatting, but the **field labels** are CBDT-standardized. So you extract by **label matching** rather than position.

---

## Task 1.2.1: Install Dependencies

```bash
pip install pdfplumber pdfminer.six
python -c "import pdfplumber; print(pdfplumber.__version__)"
# Expected: 0.10.x or higher
```

Add to `requirements.txt`:
```
pdfplumber>=0.10.0
pdfminer.six>=20221105
```

---

## Task 1.2.2: Create the PDF Parser

**File**: `parsers/form16_pdf_parser.py` (NEW)

```python
"""
form16_pdf_parser.py — Real Form 16 PDF parser using pdfplumber.

Extracts structured data from employer-issued Form 16 PDFs.
Output matches the existing Form16Parser JSON contract so the rest
of the pipeline (AuditorAgent, OptimizerAgent, ComplianceAgent) needs
no modification.

Architecture:
    1. Open PDF with pdfplumber
    2. Concatenate text from all pages
    3. Apply label-based regex extraction (more robust than positional)
    4. Detect regime from text cues ("New Tax Regime", "Section 115BAC")
    5. Validate extracted values via simple arithmetic checks
    6. Return dict in the same shape as Form16Parser
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber


# ── Field extraction patterns ──
# Each pattern: (regex, field_name, value_type)
PATTERNS = [
    # Part A
    (r"Name and address of the Employer.*?\n([^\n]+)", "employer_name", str),
    (r"PAN of the Deductor\s*[:\s]+([A-Z]{5}\d{4}[A-Z])", "employer_pan", str),
    (r"TAN of the Deductor\s*[:\s]+([A-Z]{4}\d{5}[A-Z])", "employer_tan", str),
    (r"PAN of the Employee\s*[:\s]+([A-Z]{5}\d{4}[A-Z])", "employee_pan", str),
    (r"(?:Name of the Employee|Employee Name)\s*[:\s]+([A-Z][A-Z\s.]+?)(?=\n|PAN|Assessment)", "employee_name", str),
    (r"Assessment Year\s*[:\s]+(\d{4}-\d{2})", "assessment_year", str),

    # Part B — Salary breakup
    (r"(?:1[\s.]+)?(?:Gross [Ss]alary|Salary as per provisions)[^\d]*?([\d,]+\.?\d*)", "gross_salary", float),
    (r"(?:a\)?\s*)?Salary as per section 17\(1\)[^\d]*?([\d,]+\.?\d*)", "salary_17_1", float),
    (r"(?:b\)?\s*)?(?:Value of perquisites|perquisites under section 17\(2\))[^\d]*?([\d,]+\.?\d*)", "perquisites_17_2", float),
    (r"(?:c\)?\s*)?Profits in lieu of salary[^\d]*?([\d,]+\.?\d*)", "profits_in_lieu_17_3", float),

    # Salary components
    (r"Basic [Ss]alary[^\d]*?([\d,]+\.?\d*)", "basic_salary", float),
    (r"House Rent Allowance[^\d]*?([\d,]+\.?\d*)", "hra_received", float),
    (r"Leave Travel (?:Allowance|Concession)[^\d]*?([\d,]+\.?\d*)", "lta", float),
    (r"Special Allowance[^\d]*?([\d,]+\.?\d*)", "special_allowance", float),

    # Exemptions
    (r"(?:HRA|House Rent Allowance) (?:under section|exemption)[^\d]*?([\d,]+\.?\d*)", "hra_exemption_claimed", float),
    (r"(?:LTA|Leave Travel) (?:under section|exemption)[^\d]*?([\d,]+\.?\d*)", "lta_exemption_claimed", float),

    # Deductions
    (r"Standard [Dd]eduction[^\d]*?([\d,]+\.?\d*)", "standard_deduction", float),
    (r"Professional [Tt]ax[^\d]*?([\d,]+\.?\d*)", "professional_tax", float),

    # Chapter VI-A
    (r"(?:Section\s*)?80C[^\d]*?([\d,]+\.?\d*)", "80C_amount", float),
    (r"(?:Section\s*)?80CCD\s*\(1B\)[^\d]*?([\d,]+\.?\d*)", "80CCD_1B_amount", float),
    (r"(?:Section\s*)?80CCD\s*\(2\)[^\d]*?([\d,]+\.?\d*)", "80CCD_2_amount", float),
    (r"(?:Section\s*)?80D[^\d]*?([\d,]+\.?\d*)", "80D_amount", float),
    (r"(?:Section\s*)?80G[^\d]*?([\d,]+\.?\d*)", "80G_amount", float),
    (r"(?:Section\s*)?80TTA[^\d]*?([\d,]+\.?\d*)", "80TTA_amount", float),

    # Tax computation
    (r"Total [Tt]axable [Ii]ncome[^\d]*?([\d,]+\.?\d*)", "total_taxable_income", float),
    (r"Tax on [Tt]otal [Ii]ncome[^\d]*?([\d,]+\.?\d*)", "tax_on_total_income", float),
    (r"Health and Education Cess[^\d]*?([\d,]+\.?\d*)", "cess_4_percent", float),
    (r"Total [Tt]ax [Pp]ayable[^\d]*?([\d,]+\.?\d*)", "total_tax_payable", float),
    (r"(?:Total )?Tax [Dd]educted (?:at Source)?[^\d]*?([\d,]+\.?\d*)", "tds_deducted", float),
]


REGIME_INDICATORS = {
    "new": [
        r"New Tax Regime",
        r"Section 115BAC",
        r"u/s 115BAC",
        r"opted for new",
    ],
    "old": [
        r"Old Tax Regime",
        r"Old Regime",
    ],
}


class Form16PDFParser:
    """Parses real-world Form 16 PDF files."""

    def parse(self, pdf_path: str | Path) -> dict[str, Any]:
        """
        Parse a Form 16 PDF.

        Returns dict matching Form16Parser JSON output format.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Step 1: Extract all text
        text = self._extract_text(pdf_path)

        if len(text.strip()) < 500:
            raise ValueError(
                f"Form 16 PDF appears empty or scanned (only {len(text)} chars). "
                "OCR may be needed for scanned PDFs."
            )

        # Step 2: Apply patterns
        extracted = self._apply_patterns(text)

        # Step 3: Detect regime
        regime = self._detect_regime(text)
        extracted["regime"] = regime

        # Step 4: Build standardized output
        result = self._standardize_output(extracted)

        # Step 5: Validate
        warnings = self._validate(result)
        if warnings:
            result["_warnings"] = warnings

        return result

    def _extract_text(self, pdf_path: Path) -> str:
        """Concatenate text from all pages."""
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)

                # Also extract from tables (Form 16 has many)
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            text_parts.append(" | ".join(str(c) for c in row if c))

        return "\n".join(text_parts)

    def _apply_patterns(self, text: str) -> dict:
        """Apply regex patterns and parse values."""
        result = {}
        for pattern, field, value_type in PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if not match:
                continue
            raw = match.group(1).strip()

            if value_type is float:
                # Clean number: remove commas, handle ".00"
                cleaned = raw.replace(",", "").strip()
                try:
                    result[field] = float(cleaned)
                except ValueError:
                    continue
            else:
                result[field] = raw.strip()

        return result

    def _detect_regime(self, text: str) -> str:
        """Detect which tax regime was applied."""
        for regime, patterns in REGIME_INDICATORS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return regime
        # Default heuristic: if no 80C/80D/HRA exemption claimed, likely New
        if not (re.search(r"80C[^\d]*?[\d,]+", text) or re.search(r"HRA.*exempt", text)):
            return "new"
        return "old"

    def _standardize_output(self, extracted: dict) -> dict:
        """Convert extracted fields to standard Form16Parser format."""
        # Build deductions_claimed dict
        deductions = {}
        for sec in ["80C", "80CCD_1B", "80CCD_2", "80D", "80G", "80TTA"]:
            key = f"{sec}_amount"
            if key in extracted:
                deductions[sec] = extracted[key]

        return {
            "employer_name": extracted.get("employer_name", "Unknown"),
            "employer_tan": extracted.get("employer_tan", ""),
            "employee_pan": extracted.get("employee_pan", ""),
            "employee_name": extracted.get("employee_name", "Unknown"),
            "assessment_year": extracted.get("assessment_year", "2026-27"),

            # Salary fields
            "gross_salary": extracted.get("gross_salary", 0.0),
            "basic_salary": extracted.get("basic_salary", 0.0),
            "hra_received": extracted.get("hra_received", 0.0),
            "lta": extracted.get("lta", 0.0),
            "special_allowance": extracted.get("special_allowance", 0.0),
            "perquisites_17_2": extracted.get("perquisites_17_2", 0.0),
            "profits_in_lieu_17_3": extracted.get("profits_in_lieu_17_3", 0.0),

            # Exemptions
            "hra_exemption_claimed": extracted.get("hra_exemption_claimed", 0.0),
            "lta_exemption_claimed": extracted.get("lta_exemption_claimed", 0.0),

            # Deductions
            "standard_deduction": extracted.get("standard_deduction", 75000.0),
            "professional_tax": extracted.get("professional_tax", 0.0),
            "deductions_claimed": deductions,

            # Tax computation
            "total_taxable_income": extracted.get("total_taxable_income", 0.0),
            "tax_on_total_income": extracted.get("tax_on_total_income", 0.0),
            "cess_4_percent": extracted.get("cess_4_percent", 0.0),
            "total_tax_payable": extracted.get("total_tax_payable", 0.0),
            "tds_deducted": extracted.get("tds_deducted", 0.0),

            # Regime
            "regime": extracted.get("regime", "new"),

            # Provenance
            "_source": "pdf_parsed",
            "_extracted_fields_count": len([v for v in extracted.values() if v]),
        }

    def _validate(self, result: dict) -> list[str]:
        """Sanity checks on extracted data."""
        warnings = []

        # Check 1: Gross salary should be a reasonable number
        gross = result.get("gross_salary", 0)
        if gross == 0:
            warnings.append("Gross salary not extracted — PDF format may be non-standard")
        elif gross < 100000:
            warnings.append(f"Gross salary suspiciously low: ₹{gross}")
        elif gross > 100000000:
            warnings.append(f"Gross salary suspiciously high: ₹{gross} — possible parsing error")

        # Check 2: TDS should be < 50% of gross
        tds = result.get("tds_deducted", 0)
        if tds > gross * 0.5:
            warnings.append(f"TDS ({tds}) exceeds 50% of gross — possible parsing error")

        # Check 3: New Regime should have no 80C
        if result["regime"] == "new":
            deductions = result.get("deductions_claimed", {})
            blocked = [k for k in deductions if k in ("80C", "80D", "80G", "80TTA")]
            if blocked:
                warnings.append(
                    f"New Regime detected but Old Regime deductions present: {blocked}. "
                    "Verify regime detection or check if employer made an error."
                )

        # Check 4: PAN format validation
        pan = result.get("employee_pan", "")
        if pan and not re.match(r"^[A-Z]{5}\d{4}[A-Z]$", pan):
            warnings.append(f"Employee PAN format invalid: {pan}")

        return warnings


# ──────────────────────────── CLI ────────────────────────────

def main():
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path", help="Path to Form 16 PDF")
    ap.add_argument("--output", help="Save extracted JSON to this path")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    parser = Form16PDFParser()
    result = parser.parse(args.pdf_path)

    if args.verbose:
        print(json.dumps(result, indent=2))
    else:
        print(f"Employer: {result['employer_name']}")
        print(f"Employee: {result['employee_name']} (PAN: {result['employee_pan']})")
        print(f"Gross Salary: ₹{result['gross_salary']:,.0f}")
        print(f"TDS: ₹{result['tds_deducted']:,.0f}")
        print(f"Regime: {result['regime']}")
        print(f"Deductions: {result.get('deductions_claimed', {})}")
        if result.get("_warnings"):
            print(f"\nWarnings:")
            for w in result["_warnings"]:
                print(f"  ⚠ {w}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
```

---

## Task 1.2.3: Update Parsers __init__

**File**: `parsers/__init__.py`

Add the PDF parser to the exports:

```python
from .ais_parser import AISParser
from .csv_parser import CSVParser
from .form16_parser import Form16Parser
from .form16_pdf_parser import Form16PDFParser
from .form26as_parser import Form26ASParser
```

---

## Task 1.2.4: Update Orchestrator to Accept PDF

**File**: `agents/orchestrator.py`

Find `_parse_documents()`. Modify the Form 16 handling to auto-detect PDF vs JSON:

```python
if form16_json:
    form16_path = Path(form16_json)
    if form16_path.suffix.lower() == ".pdf":
        from parsers.form16_pdf_parser import Form16PDFParser
        ctx.form16_data = Form16PDFParser().parse(form16_path)
        self._say(f"Parsed Form 16 PDF: {ctx.form16_data.get('employer_name', 'Unknown')}")
        if ctx.form16_data.get("_warnings"):
            for w in ctx.form16_data["_warnings"]:
                self._say(f"  ⚠ {w}")
    else:
        from parsers.form16_parser import Form16Parser
        ctx.form16_data = Form16Parser().parse(form16_path)
        self._say(f"Parsed Form 16 JSON: {ctx.form16_data.get('employer_name', 'Unknown')}")
```

Update the CLI argument help text:
```python
ap.add_argument("--form16", help="Path to Form 16 PDF or JSON")
```

---

## Task 1.2.5: Update Streamlit Uploader

**File**: `frontend/app.py`

In the sidebar, update the file_uploader to accept PDF:

```python
form16_file = st.sidebar.file_uploader(
    "Form 16 (PDF or JSON)",
    type=["pdf", "json"],
    help="Upload your employer-issued Form 16. PDF or pre-parsed JSON."
)
```

In the `_save_uploaded` and pipeline trigger logic, preserve the file extension when saving:

```python
def _save_uploaded(file, prefix: str = "form16") -> str:
    os.makedirs("outputs", exist_ok=True)
    ext = Path(file.name).suffix.lower()
    path = Path("outputs") / f"{prefix}_uploaded{ext}"
    with open(path, "wb") as f:
        f.write(file.getbuffer())
    return str(path)
```

---

## Task 1.2.6: Write Tests

**File**: `tests/test_form16_pdf.py` (NEW)

```python
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
    """Regex patterns extract numbers correctly."""
    from parsers.form16_pdf_parser import Form16PDFParser
    parser = Form16PDFParser()

    sample_text = """
    Gross Salary: 22,00,000.00
    Standard Deduction: 75,000
    TAN of the Deductor: DELT12345A
    PAN of the Employee: ABCDE1234F
    """

    extracted = parser._apply_patterns(sample_text)
    assert extracted.get("gross_salary") == 2200000.0
    assert extracted.get("standard_deduction") == 75000.0
    assert extracted.get("employer_tan") == "DELT12345A"
    assert extracted.get("employee_pan") == "ABCDE1234F"
```

Run tests:
```bash
pytest tests/test_form16_pdf.py -v
```

---

## Task 1.2.7: Get a Real Form 16 for Testing

Three options:
1. **Your own Form 16** — if you've worked, you have one from a previous employer
2. **CBDT sample** — Income Tax India website has sample Form 16 templates: search "Form 16 sample CBDT"
3. **Generate one** — use a Form 16 generator tool (search "Form 16 generator", many free options for testing)

Save it as `data/real/test_form16.pdf` and run:

```bash
python -m parsers.form16_pdf_parser data/real/test_form16.pdf --verbose
```

Verify the output looks reasonable. If fields are missing, look at the raw text:

```bash
python -c "
import pdfplumber
with pdfplumber.open('data/real/test_form16.pdf') as pdf:
    for i, page in enumerate(pdf.pages):
        print(f'=== Page {i+1} ===')
        print(page.extract_text())
" | less
```

Then adjust regex patterns in `PATTERNS` list to match the actual labels in your PDF.

---

## Task 1.2.8: End-to-End Test with PDF

```bash
python -m agents.orchestrator \
    --bank data/synthetic/sample_bank_statement.csv \
    --ais data/synthetic/sample_ais.json \
    --form16 data/real/test_form16.pdf \
    --output outputs/pdf_pipeline_test.json

# Verify
python -c "
import json
r = json.load(open('outputs/pdf_pipeline_test.json'))
assert r['documents']['form16_present']
print('PDF pipeline OK')
print('Gross income from PDF:', r.get('gross_income'))
"
```

---

## Acceptance Criteria

- [ ] `parsers/form16_pdf_parser.py` created with `Form16PDFParser` class
- [ ] All 4 tests in `tests/test_form16_pdf.py` pass
- [ ] CLI works: `python -m parsers.form16_pdf_parser <pdf>` extracts data
- [ ] Orchestrator auto-detects `.pdf` vs `.json` and dispatches correctly
- [ ] Streamlit uploader accepts both PDF and JSON
- [ ] At least one real Form 16 PDF successfully parsed end-to-end
- [ ] Output structure matches existing `Form16Parser` JSON output (so downstream agents need no changes)

## Risks & Mitigations

**Risk**: Each employer's Form 16 has slightly different formatting; regex fails on some.
**Mitigation**: Validation step catches missing critical fields. Test on 2-3 different PDFs if possible. For a viva, having ONE working PDF is enough as proof of concept.

**Risk**: Scanned PDFs return empty text (image-based).
**Mitigation**: The parser explicitly checks text length and raises informative error. For OCR support, would need pytesseract — out of scope for 3-hour budget.

**Risk**: Regime detection wrong on edge cases.
**Mitigation**: Fallback to "new" with warning when neither pattern matches. ComplianceAgent's existing logic also independently determines regime from deductions.

## Demo Value

In your viva, this is a 30-second wow moment: "Let me upload my actual employer Form 16 PDF" → drag-drop → pipeline runs → reconciliation shows mismatches. Demonstrates the project works on real data, not just curated JSON test fixtures.
