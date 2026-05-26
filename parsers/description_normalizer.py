"""
description_normalizer.py - Strip noise from bank transaction descriptions.

Real Indian bank statements have descriptions like:
    "WDL TFR UPI/DR/48188486544/ZOMATO/UTIB/ETERNAL/paym009769258663 AT 11669 SHIVAJI NAGAR NASIK"

This normalizer extracts the meaningful part:
    "ZOMATO ETERNAL"

Handles:
    - SBI, HDFC, ICICI, Axis, Kotak, PNB statement formats
    - WDL TFR, DEP TFR, POS, NEFT, RTGS, IMPS, UPI prefixes
    - Transaction reference numbers (8+ digit sequences)
    - Terminal/branch codes and locations
    - Bank acronyms (CR, DR, TFR TO, TFR FR, etc.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# Bank acronyms to strip (case-insensitive, sorted longest-first)
NOISE_PREFIXES = [
    "WDL TFR", "DEP TFR", "POS PRCH", "ATM WDL", "CASH WDL",
    "CASH DEP", "NEFT DR", "NEFT CR", "RTGS DR", "RTGS CR",
    "IMPS DR", "IMPS CR", "UPI/DR", "UPI/CR", "ACH/DR", "ACH/CR",
    "ECS/DR", "ECS/CR", "SWEEP TFR DR", "SWEEP TFR CR", "CHQ DEP",
    "CHQ ISSUE", "BR TO BR", "TRF TO", "TRF FR", "TO TRANSFER",
    "BY TRANSFER", "DR TRANSFER", "CR TRANSFER", "WDL", "DEP",
    "POS", "ATM", "NEFT", "RTGS", "IMPS", "UPI", "ACH", "ECS",
    "SWEEP", "INFT", "TPT",
]
NOISE_PREFIXES.sort(key=len, reverse=True)

NOISE_SUFFIXES = ["/CR", "/DR", "-CR", "-DR", " CR", " DR"]

# Patterns applied via regex substitution
_NOISE_REGEX = [
    re.compile(r"\b\d{8,}\b"),                                   # Long digit sequences = txn IDs
    re.compile(r"\bpaym\w+", re.IGNORECASE),                     # "PAYM" payment IDs
    re.compile(r"\bUTR[:/\s]*\w+", re.IGNORECASE),              # UTR reference numbers
    re.compile(r"\bREF[:/\s]*\w+", re.IGNORECASE),              # REF reference numbers
    re.compile(                                                    # Bank routing codes (word-boundary safe)
        r"\b(?:UTIB|UTIBR|HDFCR|ICICR|KKBKR|SBIN|PUNB|YESB|BARB|MAHB|UCBA|IBKL|SCBL|CITI|DEUT|HSBC)\b"
    ),
    re.compile(r"\bTID[:/\s]*\w+", re.IGNORECASE),              # Terminal IDs
    re.compile(r"\bMID[:/\s]*\w+", re.IGNORECASE),              # Merchant IDs
    re.compile(                                                    # "AT <digits> <LOCATION>"
        r"\bAT\s+\d+\s+[A-Z\s]+"
        r"(?:NAGAR|MARG|ROAD|STREET|LANE|COLONY|SECTOR|CHOWK|MARKET|MALL"
        r"|MUMBAI|DELHI|BANGALORE|CHENNAI|PUNE|NASIK|HYDERABAD|KOLKATA)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),          # Embedded dates
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"),                # Time patterns
]


@dataclass
class NormalizedTransaction:
    raw: str
    cleaned: str
    extracted_merchant: str
    transaction_method: str     # UPI | NEFT | IMPS | POS | ATM | CASH | UNKNOWN
    direction: str              # credit | debit | unknown
    stripped_tokens: list[str] = field(default_factory=list)


class DescriptionNormalizer:
    """Strips noise from real Indian bank transaction descriptions."""

    def normalize(self, description: str,
                  amount_sign: str | None = None) -> NormalizedTransaction:
        if not description or not isinstance(description, str):
            return NormalizedTransaction(
                raw=description or "", cleaned="",
                extracted_merchant="", transaction_method="UNKNOWN",
                direction=amount_sign or "unknown",
            )

        original = description.strip().upper()
        cleaned = original
        stripped: list[str] = []

        # Step 1: Detect method + direction before stripping
        method = self._detect_method(cleaned)
        direction = self._detect_direction(cleaned, amount_sign)

        # Step 2: Strip known prefix tokens (longest first)
        for prefix in NOISE_PREFIXES:
            pat = re.compile(rf"^{re.escape(prefix)}\b", re.IGNORECASE)
            if pat.match(cleaned):
                cleaned = pat.sub(" ", cleaned).strip()
                stripped.append(prefix)

        # Step 3: Strip suffixes
        for suffix in NOISE_SUFFIXES:
            if cleaned.upper().endswith(suffix.upper()):
                cleaned = cleaned[: -len(suffix)]
                stripped.append(suffix)

        # Step 4: Regex noise removal
        for pattern in _NOISE_REGEX:
            new = pattern.sub(" ", cleaned)
            if new != cleaned:
                stripped.extend(pattern.findall(cleaned))
                cleaned = new

        # Step 5: Collapse separators
        cleaned = re.sub(r"[/\s\-_]+", " ", cleaned).strip()

        # Step 5b: Strip residual noise tokens that become visible after collapse
        cleaned = re.sub(r"^(?:CR|DR|AT)\s+", "", cleaned, flags=re.IGNORECASE).strip()

        # Step 6: Extract merchant
        merchant = self._extract_merchant(cleaned)

        return NormalizedTransaction(
            raw=description,
            cleaned=cleaned,
            extracted_merchant=merchant,
            transaction_method=method,
            direction=direction,
            stripped_tokens=stripped,
        )

    def _detect_method(self, text: str) -> str:
        t = text.upper()
        for method in ("UPI", "NEFT", "RTGS", "IMPS", "POS", "ATM", "CASH", "ACH", "ECS"):
            if method in t:
                return method
        if "CHQ" in t or "CHEQUE" in t:
            return "CHEQUE"
        return "UNKNOWN"

    def _detect_direction(self, text: str, hint: str | None) -> str:
        if hint and hint.lower() in ("credit", "debit"):
            return hint.lower()
        t = text.upper()
        if "/CR" in t or " CR " in t or t.endswith(" CR"):
            return "credit"
        if "/DR" in t or " DR " in t or t.endswith(" DR"):
            return "debit"
        if any(w in t for w in ("CREDIT", "RECEIVED", "DEPOSIT", "REFUND")):
            return "credit"
        if any(w in t for w in ("DEBIT", "WITHDRAWAL", "PAYMENT", "PURCHASE")):
            return "debit"
        return "unknown"

    def _extract_merchant(self, cleaned: str) -> str:
        """Keep up to 5 alphabetic tokens — Hinglish names preserved naturally."""
        tokens = cleaned.split()
        merchant_tokens = []
        for tok in tokens:
            if not re.search(r"[A-Z]", tok):
                continue
            if len(tok) <= 2 and tok.upper() not in ("JI", "DR", "MR"):
                continue
            if re.match(r"^[A-Z]\d+$", tok) or re.match(r"^\d+[A-Z]$", tok):
                continue
            merchant_tokens.append(tok)
            if len(merchant_tokens) >= 5:
                break
        return " ".join(merchant_tokens).strip()


def normalize_description(desc: str, direction_hint: str | None = None) -> str:
    """Quick API: normalize one description, return cleaned text."""
    return DescriptionNormalizer().normalize(desc, direction_hint).cleaned


if __name__ == "__main__":
    norm = DescriptionNormalizer()
    test_cases = [
        "WDL TFR UPI/DR/48188486544/ZOMATO/UTIB/ETERNAL/paym009769258663 AT 11669 SHIVAJI NAGAR NASIK",
        "UPI/DR/AMAN JUICEWALA/SHOP NO 4/MIRA ROAD",
        "NEFT/SALARY/TECHCORP INDIA PVT LTD/APR25",
        "POS PRCH AT FLIPKART 12345 MUMBAI",
        "ATM WDL HDFC BANK BANGALORE 04042025",
        "DEP TFR NEFT/CR/UPWORK GLOBAL INC/USD WIRE/REF12345678",
        "WDL TFR NEFT-RENT-PRIYA SHARMA LANDLORD-APR2025-UTR123456",
    ]
    for tc in test_cases:
        r = norm.normalize(tc)
        print(f"RAW:      {tc}")
        print(f"CLEANED:  {r.cleaned}")
        print(f"MERCHANT: {r.extracted_merchant}")
        print(f"METHOD:   {r.transaction_method} | DIRECTION: {r.direction}")
        print()
