"""
form16_pdf_parser.py — Real Form 16 PDF parser using pdfplumber.

Extracts structured data from employer-issued Form 16 PDFs.
Output matches the existing Form16Parser JSON contract so the rest
of the pipeline (AuditorAgent, OptimizerAgent, ComplianceAgent) needs
no modification.

Architecture:
    1. Open PDF with pdfplumber
    2. Concatenate text from all pages + pipe-separated table rows
    3. Apply label-based regex extraction for metadata (PAN, TAN, etc.)
    4. Apply table-KV extraction for all numeric salary/tax fields
       (more robust than positional regex — handles "|" table separators)
    5. Detect regime from text cues ("New Tax Regime", "Section 115BAC")
    6. Validate extracted values via simple arithmetic checks
    7. Return dict in the same shape as Form16Parser
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber


# ── Metadata patterns (string fields from page text) ──
METADATA_PATTERNS = [
    # Try same-line format first: "Label VALUE" on one line
    (r"Name and address of the Employer\s+(.+?)(?=\n|PAN of the Deductor)", "employer_name", str),
    (r"PAN of the Deductor\s*[:\|]?\s*([A-Z]{5}\d{4}[A-Z])", "employer_pan", str),
    (r"TAN of the Deductor\s*[:\|]?\s*([A-Z]{4}\d{5}[A-Z])", "employer_tan", str),
    (r"PAN of the Employee\s*[:\|]?\s*([A-Z]{5}\d{4}[A-Z])", "employee_pan", str),
    (r"Name of the Employee\s*[:\|]?\s*([A-Z][A-Z\s.]+?)(?=\n|Designation|PAN)", "employee_name", str),
    (r"Assessment Year\s*[:\|]?\s*(\d{4}-\d{2})", "assessment_year", str),
]

# ── Table-row KV label → field mapping ──
# Each tuple: (substring to look for in label, field_name, take_last_col)
TABLE_LABEL_MAP = [
    # Salary components
    ("gross salary", "gross_salary"),
    ("salary as per section 17(1)", "salary_17_1"),
    ("basic salary", "basic_salary"),
    ("house rent allowance", "hra_received"),
    ("leave travel", "lta"),
    ("special allowance", "special_allowance"),
    ("value of perquisites", "perquisites_17_2"),
    ("profits in lieu of salary", "profits_in_lieu_17_3"),

    # Exemptions (these labels often contain "exemption" or "u/s 10")
    ("hra", "hra_exemption_claimed"),
    ("lta exemption", "lta_exemption_claimed"),

    # Deductions
    ("standard deduction", "standard_deduction"),
    ("professional tax", "professional_tax"),

    # Chapter VI-A  (checked before generic "80" to avoid mismatch)
    ("80ccd(1b)", "80CCD_1B_amount"),
    ("80ccd(2)", "80CCD_2_amount"),
    ("80ccd (1b)", "80CCD_1B_amount"),
    ("80ccd (2)", "80CCD_2_amount"),
    ("80c ", "80C_amount"),
    ("section 80c", "80C_amount"),
    ("80d", "80D_amount"),
    ("80g", "80G_amount"),
    ("80tta", "80TTA_amount"),

    # Tax computation
    ("total taxable income", "total_taxable_income"),
    ("tax on total income", "tax_on_total_income"),
    ("health and education cess", "cess_4_percent"),
    ("total tax payable", "total_tax_payable"),
    ("tax deducted at source", "tds_deducted"),
]

REGIME_INDICATORS = {
    "new": [
        r"New Tax Regime",
        r"Section 115BAC",
        r"u/s 115BAC",
        r"opted for new",
        r"115BAC",
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

        page_text, table_rows = self._extract_text(pdf_path)
        full_text = page_text + "\n" + "\n".join(table_rows)

        if len(full_text.strip()) < 500:
            raise ValueError(
                f"Form 16 PDF appears empty or scanned (only {len(full_text)} chars). "
                "OCR may be needed for scanned PDFs."
            )

        # Extract string metadata via regex
        extracted = self._apply_metadata_patterns(page_text)

        # Extract numeric fields from pipe-separated table rows (more reliable)
        numeric = self._extract_from_table_rows(table_rows)
        extracted.update(numeric)

        # Fall back to regex for any numeric fields still missing
        self._regex_fallback(page_text, extracted)

        # Detect regime
        extracted["regime"] = self._detect_regime(full_text)

        result = self._standardize_output(extracted)
        warnings = self._validate(result)
        if warnings:
            result["_warnings"] = warnings

        return result

    # ──────────────────── Text Extraction ────────────────────

    def _extract_text(self, pdf_path: Path) -> tuple[str, list[str]]:
        """
        Returns:
            page_text: concatenated plain text from all pages
            table_rows: pipe-separated table rows (LABEL | VALUE format)
        """
        page_parts: list[str] = []
        table_rows: list[str] = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_parts.append(page.extract_text() or "")
                for table in page.extract_tables():
                    for row in table:
                        if row:
                            table_rows.append(" | ".join(str(c) for c in row if c))

        return "\n".join(page_parts), table_rows

    # ──────────────────── Metadata Extraction ────────────────────

    def _apply_metadata_patterns(self, text: str) -> dict:
        """Extract string metadata fields (PAN, TAN, employer name, etc.)."""
        result = {}
        for pattern, field, value_type in METADATA_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                result[field] = match.group(1).strip()
        return result

    # ──────────────────── Table-KV Extraction ────────────────────

    def _extract_from_table_rows(self, table_rows: list[str]) -> dict:
        """
        Parse pipe-separated table rows to extract numeric fields.

        Row format: "LABEL | VALUE" or "LABEL | COL1 | COL2 | VALUE"
        We always take the LAST column as the value (rightmost = total/amount).
        """
        result = {}

        for row in table_rows:
            if " | " not in row:
                continue
            parts = [p.strip() for p in row.split(" | ")]
            label = parts[0].lower()
            # For multi-column rows (like TDS summary), take the last column
            raw_value = parts[-1].strip()

            # Parse the numeric value
            cleaned = raw_value.replace("Rs.", "").replace("Rs", "").replace("INR", "").replace(",", "").strip()
            try:
                value = float(cleaned)
            except ValueError:
                continue

            # Skip header rows and subtotals we don't care about
            if label in ("component", "deduction", "particulars", "quarter", ""):
                continue

            # Match against label map (first match wins — order matters in TABLE_LABEL_MAP)
            for label_fragment, field in TABLE_LABEL_MAP:
                if label_fragment in label:
                    # Don't overwrite with a zero if we already have a non-zero value
                    # (e.g., "Gross Salary" row in income table should match the salary table)
                    if field not in result or (value != 0 and result[field] == 0):
                        result[field] = value
                    break

        return result

    # ──────────────────── Regex Fallback ────────────────────

    def _regex_fallback(self, text: str, result: dict) -> None:
        """
        Try regex patterns for fields still missing after table extraction.
        Uses same-line patterns (no newline crossing) for reliability.
        """
        # TDS from quarterly summary ("Total | 250,000.00 | 250,000.00")
        if "tds_deducted" not in result or result.get("tds_deducted", 0) == 0:
            m = re.search(r"^Total\s+([\d,]+\.?\d*)", text, re.IGNORECASE | re.MULTILINE)
            if m:
                try:
                    result["tds_deducted"] = float(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        # Standard deduction fallback
        if "standard_deduction" not in result or result.get("standard_deduction", 0) == 0:
            m = re.search(r"Standard\s+Deduction.*?([\d,]+\.?\d*)\s*$",
                          text, re.IGNORECASE | re.MULTILINE)
            if m:
                try:
                    result["standard_deduction"] = float(m.group(1).replace(",", ""))
                except ValueError:
                    pass

    # ──────────────────── Regime Detection ────────────────────

    def _detect_regime(self, text: str) -> str:
        for regime, patterns in REGIME_INDICATORS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    return regime
        # Default heuristic: no 80C/HRA exemption → likely New Regime
        if not (re.search(r"\b80C\b.*?[\d,]+", text) or re.search(r"HRA.*?exempt", text)):
            return "new"
        return "old"

    # ──────────────────── Standardize Output ────────────────────

    def _standardize_output(self, extracted: dict) -> dict:
        deductions = {}
        for sec in ["80C", "80CCD_1B", "80CCD_2", "80D", "80G", "80TTA"]:
            key = f"{sec}_amount"
            if key in extracted and extracted[key]:
                deductions[sec] = extracted[key]

        return {
            "employer_name": extracted.get("employer_name", "Unknown"),
            "employer_tan": extracted.get("employer_tan", ""),
            "employee_pan": extracted.get("employee_pan", ""),
            "employee_name": extracted.get("employee_name", "Unknown"),
            "assessment_year": extracted.get("assessment_year", "2026-27"),

            "gross_salary": extracted.get("gross_salary", 0.0),
            "basic_salary": extracted.get("basic_salary", 0.0),
            "hra_received": extracted.get("hra_received", 0.0),
            "lta": extracted.get("lta", 0.0),
            "special_allowance": extracted.get("special_allowance", 0.0),
            "perquisites_17_2": extracted.get("perquisites_17_2", 0.0),
            "profits_in_lieu_17_3": extracted.get("profits_in_lieu_17_3", 0.0),

            "hra_exemption_claimed": extracted.get("hra_exemption_claimed", 0.0),
            "lta_exemption_claimed": extracted.get("lta_exemption_claimed", 0.0),

            "standard_deduction": extracted.get("standard_deduction", 75000.0),
            "professional_tax": extracted.get("professional_tax", 0.0),
            "deductions_claimed": deductions,

            "total_taxable_income": extracted.get("total_taxable_income", 0.0),
            "tax_on_total_income": extracted.get("tax_on_total_income", 0.0),
            "cess_4_percent": extracted.get("cess_4_percent", 0.0),
            "total_tax_payable": extracted.get("total_tax_payable", 0.0),
            "tds_deducted": extracted.get("tds_deducted", 0.0),

            "regime": extracted.get("regime", "new"),
            "_source": "pdf_parsed",
            "_extracted_fields_count": len([v for v in extracted.values() if v]),
        }

    # ──────────────────── Validation ────────────────────

    def _validate(self, result: dict) -> list[str]:
        warnings = []

        gross = result.get("gross_salary", 0)
        if gross == 0:
            warnings.append("Gross salary not extracted — PDF format may be non-standard")
        elif gross < 100000:
            warnings.append(f"Gross salary suspiciously low: {gross}")
        elif gross > 100000000:
            warnings.append(f"Gross salary suspiciously high: {gross} — possible parsing error")

        tds = result.get("tds_deducted", 0)
        if tds > gross * 0.5:
            warnings.append(f"TDS ({tds}) exceeds 50% of gross — possible parsing error")

        if result["regime"] == "new":
            deductions = result.get("deductions_claimed", {})
            blocked = [k for k in deductions if k in ("80C", "80D", "80G", "80TTA")]
            if blocked:
                warnings.append(
                    f"New Regime detected but Old Regime deductions present: {blocked}. "
                    "Verify regime detection or check if employer made an error."
                )

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
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Employer: {result['employer_name']}")
        print(f"Employee: {result['employee_name']} (PAN: {result['employee_pan']})")
        print(f"Gross Salary: {result['gross_salary']:,.0f}")
        print(f"TDS: {result['tds_deducted']:,.0f}")
        print(f"Regime: {result['regime']}")
        print(f"Deductions: {result.get('deductions_claimed', {})}")
        if result.get("_warnings"):
            print("\nWarnings:")
            for w in result["_warnings"]:
                print(f"  ! {w}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
