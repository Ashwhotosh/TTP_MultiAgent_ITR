"""
csv_parser.py -- Bank statement CSV parser.

Handles multiple Indian bank statement formats. Auto-detects column layout
and normalises to a standard transaction format.

Supported formats:
    - Standard: Date, Details, Note, Debit/Credit, Amount, Balance
    - SBI: Txn Date, Description, Ref No, Debit, Credit, Balance
    - HDFC: Date, Narration, Chq./Ref.No., Value Dt, Withdrawal Amt, Deposit Amt, Closing Balance
    - ICICI: S No., Value Date, Transaction Date, Cheque Number, Transaction Remarks, Withdrawal Amount (INR), Deposit Amount (INR), Balance (INR)
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any


# ── Vendor / mode detection patterns ──
TXN_MODE_PATTERNS = [
    (r'\bUPI\b', 'UPI'),
    (r'\bNEFT\b', 'NEFT'),
    (r'\bIMPS\b', 'IMPS'),
    (r'\bRTGS\b', 'RTGS'),
    (r'\bCASH\b', 'CASH'),
    (r'\bINT/', 'INT'),
    (r'\bATM\b', 'ATM'),
    (r'\bACH\b', 'ACH'),
    (r'\bECS\b', 'ECS'),
]

VENDOR_PATTERNS = [
    # Extract vendor from UPI: UPI/DR/VENDOR_NAME/...
    (r'UPI/(?:DR|CR)/([^/]+)/', None),
    # NEFT: NEFT/keyword/VENDOR_NAME/...
    (r'NEFT/(?:SALARY|RENT|CR|DR)?/?([^/]+)/', None),
    # Wise/Wire: NEFT/CR/WISE/VENDOR_NAME
    (r'WISE/([^/]+)', None),
    # Interest
    (r'INT/([^/]+)', None),
]


class CSVParser:
    """Multi-format Indian bank statement CSV parser."""

    def parse(self, filepath: str) -> list[dict[str, Any]]:
        """Parse bank statement CSV. Auto-detects format.

        Returns list of:
            {
                "id": "txn_001",
                "date": "2025-04-10",
                "description": str,
                "amount": float,
                "transaction_type": "credit" | "debit",
                "balance": float,
                "vendor": str | None,
                "txn_mode": "UPI" | "NEFT" | "IMPS" | "CASH" | "OTHER",
                "note": str | None,
                "itr_schedule_hint": None,
            }
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Bank statement not found: {filepath}")

        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)

        # Auto-detect format
        format_type = self._detect_format(headers)

        transactions = []
        for idx, row in enumerate(rows, start=1):
            txn = self._parse_row(row, format_type, idx)
            if txn:
                transactions.append(txn)

        return transactions

    def _detect_format(self, headers: list[str]) -> str:
        """Detect bank statement format from headers."""
        header_lower = [h.strip().lower() for h in headers]

        if 'debit/credit' in header_lower or 'details' in header_lower:
            return 'standard'
        elif 'withdrawal amt' in header_lower or 'narration' in header_lower:
            return 'hdfc'
        elif 'transaction remarks' in header_lower:
            return 'icici'
        elif 'debit' in header_lower and 'credit' in header_lower:
            return 'sbi'
        else:
            return 'standard'  # best-effort fallback

    def _parse_row(self, row: dict, format_type: str, idx: int
                   ) -> dict[str, Any] | None:
        """Parse a single row based on format type."""
        try:
            if format_type == 'standard':
                return self._parse_standard(row, idx)
            elif format_type == 'hdfc':
                return self._parse_hdfc(row, idx)
            elif format_type == 'icici':
                return self._parse_icici(row, idx)
            elif format_type == 'sbi':
                return self._parse_sbi(row, idx)
            else:
                return self._parse_standard(row, idx)
        except Exception:
            return None

    def _parse_standard(self, row: dict, idx: int) -> dict[str, Any] | None:
        """Parse standard format: Date, Details, Note, Debit/Credit, Amount, Balance"""
        date = (row.get('Date') or '').strip()
        description = (row.get('Details') or '').strip()
        note = (row.get('Note') or '').strip() or None
        dc_flag = (row.get('Debit/Credit') or '').strip().lower()
        amount_str = (row.get('Amount') or '0').strip()
        balance_str = (row.get('Balance') or '0').strip()

        if not date or not description:
            return None

        amount = self._parse_amount(amount_str)
        balance = self._parse_amount(balance_str)
        txn_type = 'credit' if dc_flag == 'credit' else 'debit'

        vendor = self._extract_vendor(description)
        txn_mode = self._extract_mode(description)

        return {
            "id": f"txn_{idx:03d}",
            "date": date,
            "description": description,
            "amount": amount,
            "transaction_type": txn_type,
            "balance": balance,
            "vendor": vendor,
            "txn_mode": txn_mode,
            "note": note,
            "itr_schedule_hint": None,
        }

    def _parse_hdfc(self, row: dict, idx: int) -> dict[str, Any] | None:
        """Parse HDFC format."""
        date = (row.get('Date') or '').strip()
        description = (row.get('Narration') or '').strip()
        withdrawal = self._parse_amount(row.get('Withdrawal Amt', '0'))
        deposit = self._parse_amount(row.get('Deposit Amt', '0'))
        balance = self._parse_amount(row.get('Closing Balance', '0'))

        if not date:
            return None

        if deposit > 0:
            amount, txn_type = deposit, 'credit'
        else:
            amount, txn_type = withdrawal, 'debit'

        return {
            "id": f"txn_{idx:03d}",
            "date": date,
            "description": description,
            "amount": amount,
            "transaction_type": txn_type,
            "balance": balance,
            "vendor": self._extract_vendor(description),
            "txn_mode": self._extract_mode(description),
            "note": None,
            "itr_schedule_hint": None,
        }

    def _parse_icici(self, row: dict, idx: int) -> dict[str, Any] | None:
        """Parse ICICI format."""
        date = (row.get('Transaction Date') or row.get('Value Date') or '').strip()
        description = (row.get('Transaction Remarks') or '').strip()
        withdrawal = self._parse_amount(row.get('Withdrawal Amount (INR)', '0'))
        deposit = self._parse_amount(row.get('Deposit Amount (INR)', '0'))
        balance = self._parse_amount(row.get('Balance (INR)', '0'))

        if not date:
            return None

        if deposit > 0:
            amount, txn_type = deposit, 'credit'
        else:
            amount, txn_type = withdrawal, 'debit'

        return {
            "id": f"txn_{idx:03d}",
            "date": date,
            "description": description,
            "amount": amount,
            "transaction_type": txn_type,
            "balance": balance,
            "vendor": self._extract_vendor(description),
            "txn_mode": self._extract_mode(description),
            "note": None,
            "itr_schedule_hint": None,
        }

    def _parse_sbi(self, row: dict, idx: int) -> dict[str, Any] | None:
        """Parse SBI format."""
        date = (row.get('Txn Date') or '').strip()
        description = (row.get('Description') or '').strip()
        debit = self._parse_amount(row.get('Debit', '0'))
        credit = self._parse_amount(row.get('Credit', '0'))
        balance = self._parse_amount(row.get('Balance', '0'))

        if not date:
            return None

        if credit > 0:
            amount, txn_type = credit, 'credit'
        else:
            amount, txn_type = debit, 'debit'

        return {
            "id": f"txn_{idx:03d}",
            "date": date,
            "description": description,
            "amount": amount,
            "transaction_type": txn_type,
            "balance": balance,
            "vendor": self._extract_vendor(description),
            "txn_mode": self._extract_mode(description),
            "note": None,
            "itr_schedule_hint": None,
        }

    # ────────────────────── Helpers ──────────────────────

    @staticmethod
    def _parse_amount(val: str | None) -> float:
        """Parse amount string to float, handling commas and empty strings."""
        if not val:
            return 0.0
        val = str(val).strip().replace(',', '').replace('"', '')
        try:
            return abs(float(val))
        except ValueError:
            return 0.0

    @staticmethod
    def _extract_vendor(description: str) -> str | None:
        """Extract vendor name from transaction description."""
        desc = description.strip()

        for pattern, _ in VENDOR_PATTERNS:
            m = re.search(pattern, desc, re.IGNORECASE)
            if m:
                vendor = m.group(1).strip()
                # Clean up common suffixes
                vendor = re.sub(r'\s*/.*$', '', vendor)
                return vendor

        # Fallback: try to extract from CASH/DEPOSIT
        if 'CASH' in desc.upper():
            return 'CASH'

        return None

    @staticmethod
    def _extract_mode(description: str) -> str:
        """Extract transaction mode (UPI, NEFT, etc.) from description."""
        desc_upper = description.upper()
        for pattern, mode in TXN_MODE_PATTERNS:
            if re.search(pattern, desc_upper):
                return mode
        return 'OTHER'
