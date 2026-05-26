"""
ais_parser.py -- Annual Information Statement (AIS) Parser.

Parses the AIS JSON downloaded from the IT Department's compliance portal.
The AIS contains all Specified Financial Transactions (SFTs) reported to
the government by third parties (banks, brokers, employers, etc.)

AIS Structure (simplified):
{
    "pan": "XXXXX0000X",
    "assessment_year": "2026-27",
    "sft": [                        # Specified Financial Transactions
        {
            "sft_code": "SFT-001",  # Salary
            "info_source": "TAN of employer",
            "reported_value": 2200000,
            "derived_value": 2200000,
            "tds_tcs": 182400,
        },
        {
            "sft_code": "SFT-005",  # Savings interest
            "info_source": "HDFC Bank",
            "reported_value": 14200,
            "tds_tcs": 1420,
        },
        ...
    ],
    "tds_tcs": [                    # TDS/TCS details
        {
            "section": "192",
            "deductor_tan": "...",
            "amount_paid": 2200000,
            "tax_deducted": 182400,
        },
        ...
    ]
}

The parser normalizes SFT codes to human-readable income types
and returns a structured dict for the AuditorAgent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# SFT code -> income type mapping
# Reference: CBDT Notification No. 166/2020
SFT_CODE_MAP = {
    "SFT-001": {"type": "salary",           "section": "192"},
    "SFT-002": {"type": "rent_received",     "section": "194I"},
    "SFT-003": {"type": "interest_savings",  "section": "194A"},
    "SFT-004": {"type": "interest_fd",       "section": "194A"},
    "SFT-005": {"type": "interest_other",    "section": "194A"},
    "SFT-006": {"type": "dividend",          "section": "194"},
    "SFT-007": {"type": "mf_purchase",       "section": ""},
    "SFT-008": {"type": "mf_redemption",     "section": "194F"},
    "SFT-009": {"type": "equity_sale",       "section": "194"},
    "SFT-010": {"type": "bond_interest",     "section": "193"},
    "SFT-011": {"type": "property_purchase", "section": "194IA"},
    "SFT-012": {"type": "property_sale",     "section": "194IA"},
    "SFT-013": {"type": "cash_deposit",      "section": ""},
    "SFT-014": {"type": "cash_withdrawal",   "section": "194N"},
    "SFT-015": {"type": "foreign_remittance","section": "206C"},
    "SFT-016": {"type": "crypto_vda",        "section": "194S"},
    # Add more as needed from CBDT notifications
}

LOG = "[AIS_PARSER]"


class AISParser:
    """Parses AIS JSON into structured income items."""

    def parse(self, filepath: str | Path) -> dict[str, Any]:
        """Parse AIS JSON file.

        Returns:
            {
                "pan": str (masked),
                "assessment_year": str,
                "sft_entries": list[dict],  # normalized SFT entries
                "tds_entries": list[dict],  # TDS/TCS entries
                "summary": {
                    "total_reported_income": float,
                    "total_tds": float,
                    "income_types_present": list[str],
                },
            }
        """
        raw = json.loads(Path(filepath).read_text(encoding="utf-8"))

        sft_entries = []
        for sft in raw.get("sft", []):
            entry = self._normalize_sft(sft)
            if entry:
                sft_entries.append(entry)

        tds_entries = self._parse_tds(raw.get("tds_tcs", []))

        return {
            "pan": self._mask_pan(raw.get("pan", "")),
            "assessment_year": raw.get("assessment_year", ""),
            "sft_entries": sft_entries,
            "tds_entries": tds_entries,
            "summary": self._build_summary(sft_entries, tds_entries),
        }

    def _normalize_sft(self, sft: dict) -> dict | None:
        """Convert raw SFT entry to standardized format.

        Returns:
            {
                "type": str,         # normalized income type
                "amount": float,
                "reporter": str,     # entity that reported this
                "tds_deducted": float,
                "section": str,      # TDS section
                "source": "ais",
                "sft_code": str,
                "quarter": str,
                "additional_info": dict,
            }
        """
        sft_code = sft.get("sft_code", "")
        mapping = SFT_CODE_MAP.get(sft_code)

        if mapping is None:
            # Unknown SFT code -- include but mark as "other"
            mapping = {"type": "other", "section": ""}

        amount = float(sft.get("reported_value", 0) or sft.get("derived_value", 0))

        return {
            "type": mapping["type"],
            "amount": amount,
            "reporter": sft.get("info_source", "Unknown"),
            "tds_deducted": float(sft.get("tds_tcs", 0)),
            "section": mapping["section"],
            "source": "ais",
            "sft_code": sft_code,
            "quarter": sft.get("quarter", "ALL"),
            "additional_info": sft.get("additional_info", {}),
        }

    def _parse_tds(self, tds_list: list) -> list[dict]:
        """Parse TDS/TCS entries.

        Returns list of:
            {
                "section": str,
                "deductor_name": str,
                "deductor_tan": str,
                "amount_paid": float,
                "tax_deducted": float,
                "tax_deposited": float,
                "date_of_deposit": str,
            }
        """
        entries = []
        for tds in tds_list:
            entries.append({
                "section": tds.get("section", ""),
                "deductor_name": tds.get("deductor_name", ""),
                "deductor_tan": tds.get("deductor_tan", ""),
                "amount_paid": float(tds.get("amount_paid_credited", 0)),
                "tax_deducted": float(tds.get("tax_deducted", 0)),
                "tax_deposited": float(tds.get("tax_deposited", 0)),
                "date_of_deposit": tds.get("date_of_deposit", ""),
            })
        return entries

    def _build_summary(self, sft_entries: list[dict],
                       tds_entries: list[dict]) -> dict:
        """Build summary statistics.

        Returns:
            {
                "total_reported_income": float,
                "total_tds": float,
                "income_types_present": list[str],
            }
        """
        total_income = sum(e["amount"] for e in sft_entries)
        total_tds_from_sft = sum(e["tds_deducted"] for e in sft_entries)
        total_tds_from_tds = sum(e["tax_deducted"] for e in tds_entries)

        # Use the higher of the two TDS totals (they should agree)
        total_tds = max(total_tds_from_sft, total_tds_from_tds)

        income_types = list(dict.fromkeys(
            e["type"] for e in sft_entries if e["type"] != "mf_purchase"
        ))

        return {
            "total_reported_income": total_income,
            "total_tds": total_tds,
            "income_types_present": income_types,
        }

    @staticmethod
    def _mask_pan(pan: str) -> str:
        """Mask PAN for privacy: ABCDE1234F -> A****234F"""
        if len(pan) >= 10:
            return pan[0] + "****" + pan[5:9] + pan[9]
        return "**MASKED**"
