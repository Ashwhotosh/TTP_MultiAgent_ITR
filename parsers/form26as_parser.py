"""
form26as_parser.py — Form 26AS (Tax Credit Statement) parser.

Contains TDS/TCS credited against the PAN from all deductors.
Cross-referenced with AIS TDS to find mismatches.

TODO: [WEEK 1] Implement. Lower priority than AIS parser — 
AIS subsumes most 26AS data now. Build if time permits.
"""
from __future__ import annotations
from typing import Any

class Form26ASParser:
    """Parse Form 26AS data."""

    def parse(self, filepath: str) -> dict[str, Any]:
        """
        Returns:
            {
                "pan": str,
                "assessment_year": str,
                "tds_entries": list[dict],
                "tcs_entries": list[dict],
                "refund_entries": list[dict],
                "total_tds": float,
            }
        """
        # TODO: [WEEK 1] Implement if time permits
        pass
