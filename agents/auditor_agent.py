"""
auditor_agent.py -- AuditorAgent: Multi-Document Reconciliation.

The most critical agent. It:
1. Cross-references Form 16 (employer-declared) vs AIS (govt-known) vs
   Bank Statement (transaction-level) to build a unified income picture.
2. Flags discrepancies as notice risks.
3. Runs anomaly detection on bank transactions (crypto, freelance, capital gains).
4. Computes a data-driven risk score based on actual mismatches.

Output written to ctx:
    ctx.reconciliation   -- unified income object with source annotations
    ctx.anomalies        -- flagged transactions with evidence + risk weight
    ctx.risk_score       -- notice risk score with per-item breakdown
    ctx.interview_questions -- generated from anomalies needing user input
"""
from __future__ import annotations

import re
from typing import Any

from .base import BaseAgent, AgentContext, AgentResult


# ── Risk weight constants (evidence-based, not arbitrary) ──
RISK_WEIGHTS = {
    "ais_mismatch_income":       25,   # AIS shows income not in Form 16
    "ais_mismatch_tds":          20,   # TDS in AIS doesn't match 26AS/Form16
    "crypto_undeclared":         60,   # Crypto proceeds in AIS — 194S TDS makes non-disclosure near-certain notice
    "capital_gains_undeclared":  55,   # MF/equity via STT/SEBI data — govt has full visibility, HIGH risk
    "freelance_undeclared":      25,   # Foreign credits not declared
    "high_value_cash":           15,   # Cash deposits > 50k (SFT trigger)
    "savings_interest_missing":  10,   # Interest income in AIS not declared
    "property_unreported":       20,   # Property SFT in AIS
}

# ── Vendor registries for bank transaction classification ──
CRYPTO_VENDORS = re.compile(
    r'WAZIRX|COINSWITCH|COINDCX|ZEBPAY|BINANCE|CRYPTO|KUCOIN|GIOTTUS',
    re.IGNORECASE,
)
CAPITAL_GAINS_VENDORS = re.compile(
    r'ZERODHA|GROWW|UPSTOX|ANGEL\s*BROKING|KITE|MOTILAL|HDFC\s*SEC|ICICI\s*SEC|KOTAK\s*SEC'
    r'|ELSS|REDEMPTION|EQUITY\s*SALE|MF\s*REDEMPTION',
    re.IGNORECASE,
)
FREELANCE_VENDORS = re.compile(
    r'UPWORK|FIVERR|TOPTAL|FREELANCER|WISE|PAYPAL|REMITTANCE|USD\s*WIRE'
    r'|FREELANCE|CONSULTING',
    re.IGNORECASE,
)
SALARY_KEYWORDS = re.compile(
    r'SALARY|SAL\s*CREDIT|NEFT/SALARY',
    re.IGNORECASE,
)
RENT_KEYWORDS = re.compile(
    r'RENT|LANDLORD',
    re.IGNORECASE,
)

# ── ITR Schedule mapping for income types ──
SCHEDULE_MAP = {
    "salary":           "Schedule Salary",
    "interest_savings": "Schedule OS",
    "interest_fd":      "Schedule OS",
    "interest_other":   "Schedule OS",
    "dividend":         "Schedule OS",
    "mf_redemption":    "Schedule CG",
    "equity_sale":      "Schedule CG",
    "crypto_vda":       "Schedule VDA",
    "foreign_remittance": "Schedule PGBP / OS",
    "rent_received":    "Schedule HP",
    "property_sale":    "Schedule CG",
    "property_purchase": "N/A (not income)",
    "cash_deposit":     "N/A (verify source)",
    "cash_withdrawal":  "N/A",
    "bond_interest":    "Schedule OS",
}


class AuditorAgent(BaseAgent):
    """Reconciles multiple documents and flags discrepancies."""

    def __init__(self, tools: dict[str, Any] | None = None):
        super().__init__(
            name="AuditorAgent",
            role="Cross-reference Form 16, AIS, and bank statement to find "
                 "undeclared income and notice risks.",
            tools=tools or {},
        )

    def run(self, ctx: AgentContext) -> AgentResult:
        """Execute reconciliation pipeline.

        Steps:
            1. Extract income items from each document source
            2. Build unified income ledger with source tags
            3. Cross-reference: find items in AIS not in Form 16
            4. Cross-reference: find bank anomalies not in AIS
            5. Compute risk score from mismatches
            6. Generate interview questions for ambiguous items
        """
        self._log("Starting multi-document reconciliation")
        warnings = []
        tools_called = []

        # Step 1: Extract income items from each source
        form16_income = self._extract_form16_income(ctx.form16_data)
        ais_income = self._extract_ais_income(ctx.ais_data)
        bank_income = self._extract_bank_income(ctx.bank_transactions)

        # Step 2: Build unified ledger
        ledger = self._build_unified_ledger(form16_income, ais_income, bank_income)

        # Step 3: Cross-reference AIS vs Form 16
        ais_mismatches = self._cross_ref_ais_form16(ais_income, form16_income)

        # Step 4: Detect bank anomalies
        anomalies = self._detect_anomalies(ctx.bank_transactions, ais_income)

        # Step 5: Compute risk score
        risk = self._compute_risk_score(ais_mismatches, anomalies)

        # Step 6: Generate interview questions
        questions = self._generate_questions(anomalies, ais_mismatches)

        # Write to context
        ctx.reconciliation = ledger
        ctx.anomalies = anomalies
        ctx.risk_score = risk
        ctx.interview_questions = questions

        self._log(f"Reconciliation complete: {len(ledger.get('ledger', []))} items, "
                  f"{len(anomalies)} anomalies, risk={risk.get('risk_level', 'N/A')}")

        return AgentResult(
            agent_name=self.name,
            status="success",
            output={
                "reconciliation": ledger,
                "anomalies": anomalies,
                "risk_score": risk,
                "interview_questions": questions,
            },
            reasoning="Multi-document reconciliation complete.",
            tools_called=tools_called,
            warnings=warnings,
        )

    # ────────────────────── Reconciliation Steps ──────────────────────

    def _extract_form16_income(self, form16: dict) -> dict:
        """Extract structured income from Form 16 data.

        Returns:
            {
                "salary": {"gross": X, "tds": Y, "employer": str, "source": "form16"},
                "perquisites": {"amount": X, "source": "form16"},
                "deductions_claimed": dict,
                "regime": str,
            }
        """
        if not form16:
            return {}

        return {
            "salary": {
                "gross": form16.get("gross_salary", 0),
                "basic": form16.get("basic_salary", 0),
                "hra_received": form16.get("hra_received", 0),
                "tds": form16.get("tds_deducted", 0),
                "employer": form16.get("employer_name", "Unknown"),
                "source": "form16",
            },
            "perquisites": {
                "amount": form16.get("perquisites_17_2", 0),
                "source": "form16",
            },
            "standard_deduction": form16.get("standard_deduction", 0),
            "professional_tax": form16.get("professional_tax", 0),
            "deductions_claimed": form16.get("deductions_claimed", {}),
            "regime": form16.get("regime", "new"),
        }

    def _extract_ais_income(self, ais: dict) -> list[dict]:
        """Extract all SFT entries from AIS as standardized income items."""
        if not ais:
            return []

        items = []
        for entry in ais.get("sft_entries", []):
            items.append({
                "type": entry.get("type", "other"),
                "amount": entry.get("amount", 0),
                "reporter": entry.get("reporter", "Unknown"),
                "tds_deducted": entry.get("tds_deducted", 0),
                "section": entry.get("section", ""),
                "source": "ais",
                "ais_category": entry.get("sft_code", ""),
                "quarter": entry.get("quarter", "ALL"),
                "additional_info": entry.get("additional_info", {}),
            })
        return items

    def _extract_bank_income(self, transactions: list[dict]) -> list[dict]:
        """Scan bank transactions for income-like items.

        Uses regex patterns for classification. Focuses on credits.
        """
        if not transactions:
            return []

        income_items = []
        for txn in transactions:
            if txn.get("transaction_type") != "credit":
                continue

            desc = txn.get("description", "")
            amount = txn.get("amount", 0)

            # Classify the credit
            flag_type = None
            income_type = "other"

            if SALARY_KEYWORDS.search(desc):
                income_type = "salary"
                flag_type = "SALARY"
            elif CRYPTO_VENDORS.search(desc):
                income_type = "crypto_vda"
                flag_type = "CRYPTO_TRIGGER"
            elif CAPITAL_GAINS_VENDORS.search(desc):
                if 'REDEMPTION' in desc.upper() or 'SALE' in desc.upper():
                    income_type = "mf_redemption" if 'ELSS' in desc.upper() or 'MF' in desc.upper() else "equity_sale"
                else:
                    income_type = "equity_sale"
                flag_type = "CAPITAL_GAINS_TRIGGER"
            elif FREELANCE_VENDORS.search(desc):
                income_type = "foreign_remittance"
                flag_type = "FREELANCE_INCOME"
            elif ('INTEREST' in desc.upper() or 'INT/' in desc.upper()
                  or re.search(r'\bINT\b', desc, re.IGNORECASE)):
                if 'FD' in desc.upper() or 'FIXED' in desc.upper():
                    income_type = "interest_fd"
                else:
                    income_type = "interest_savings"
                flag_type = "INTEREST"
            elif 'CASH' in desc.upper() and 'DEPOSIT' in desc.upper():
                income_type = "cash_deposit"
                flag_type = "HIGH_VALUE_CASH" if amount >= 50000 else None

            if flag_type or income_type != "other":
                income_items.append({
                    "type": income_type,
                    "amount": amount,
                    "date": txn.get("date", ""),
                    "description": desc,
                    "txn_id": txn.get("id", ""),
                    "source": "bank",
                    "flag_type": flag_type,
                    "vendor": txn.get("vendor"),
                })

        return income_items

    def _build_unified_ledger(self, form16_income: dict,
                               ais_income: list[dict],
                               bank_income: list[dict]) -> dict:
        """Merge all income sources into a unified ledger."""
        ledger = []

        # 1. Salary — match across all three sources
        f16_salary = form16_income.get("salary", {})
        ais_salary = [i for i in ais_income if i["type"] == "salary"]
        bank_salary = [i for i in bank_income if i["type"] == "salary"]

        salary_amount_f16 = f16_salary.get("gross", 0)
        salary_amount_ais = sum(i["amount"] for i in ais_salary)
        salary_amount_bank = sum(i["amount"] for i in bank_salary)

        if salary_amount_f16 > 0 or salary_amount_ais > 0:
            delta = abs(salary_amount_f16 - salary_amount_ais)
            match_status = "confirmed" if delta < 100 else "mismatch"
            employer = f16_salary.get("employer", "")
            if not employer and ais_salary:
                employer = ais_salary[0].get("reporter", "")

            ledger.append({
                "item": f"Salary - {employer}",
                "amount_form16": salary_amount_f16,
                "amount_ais": salary_amount_ais,
                "amount_bank": salary_amount_bank,
                "match_status": match_status,
                "delta": delta,
                "itr_schedule": "Schedule Salary",
                "risk_weight": 0 if match_status == "confirmed" else RISK_WEIGHTS["ais_mismatch_income"],
            })

        # 2. Non-salary AIS items
        ais_non_salary = [i for i in ais_income if i["type"] != "salary"]
        for ais_item in ais_non_salary:
            item_type = ais_item["type"]
            amount_ais = ais_item["amount"]

            # Try to match with bank
            matching_bank = [
                b for b in bank_income
                if b["type"] == item_type and abs(b["amount"] - amount_ais) < 100
            ]

            amount_bank = matching_bank[0]["amount"] if matching_bank else 0
            itr_schedule = SCHEDULE_MAP.get(item_type, "Schedule OS")

            # These items are AIS-reported but NOT in Form 16 -> notice risk
            ledger.append({
                "item": f"{item_type.replace('_', ' ').title()} - {ais_item['reporter']}",
                "amount_form16": 0,
                "amount_ais": amount_ais,
                "amount_bank": amount_bank,
                "match_status": "ais_only",
                "delta": amount_ais,
                "itr_schedule": itr_schedule,
                "risk_weight": RISK_WEIGHTS.get(
                    f"{item_type}_undeclared",
                    RISK_WEIGHTS.get("savings_interest_missing", 10)
                ),
            })

        # 3. Bank-only items (not in AIS)
        ais_types_amounts = {
            (i["type"], i["amount"]) for i in ais_income
        }
        for bank_item in bank_income:
            if bank_item["type"] in ("salary", "other"):
                continue
            # Check if already covered by AIS matching
            matched = any(
                bank_item["type"] == a["type"] and abs(bank_item["amount"] - a["amount"]) < 100
                for a in ais_income
            )
            if not matched:
                itr_schedule = SCHEDULE_MAP.get(bank_item["type"], "Schedule OS")
                ledger.append({
                    "item": f"{bank_item['type'].replace('_', ' ').title()} - {bank_item.get('vendor', 'Bank')}",
                    "amount_form16": 0,
                    "amount_ais": 0,
                    "amount_bank": bank_item["amount"],
                    "match_status": "bank_only",
                    "delta": bank_item["amount"],
                    "itr_schedule": itr_schedule,
                    "risk_weight": 5,  # Lower risk - govt doesn't know yet
                })

        return {
            "ledger": ledger,
            "total_form16": salary_amount_f16,
            "total_ais": sum(i["amount"] for i in ais_income),
            "total_bank_credits": sum(
                i["amount"] for i in bank_income
            ),
        }

    def _cross_ref_ais_form16(self, ais_income: list[dict],
                               form16_income: dict) -> list[dict]:
        """Find items in AIS that are NOT in Form 16."""
        mismatches = []

        f16_salary_gross = form16_income.get("salary", {}).get("gross", 0)

        for item in ais_income:
            if item["type"] == "salary":
                # Check salary match
                if abs(item["amount"] - f16_salary_gross) > 100:
                    mismatches.append({
                        "type": "ais_mismatch_income",
                        "item": f"Salary mismatch: AIS={item['amount']:,.0f} vs Form16={f16_salary_gross:,.0f}",
                        "amount": item["amount"],
                        "reporter": item["reporter"],
                        "risk_weight": RISK_WEIGHTS["ais_mismatch_income"],
                    })
            else:
                # Non-salary items in AIS but not in Form 16.
                # Any income the government knows about (AIS) but the filer hasn't
                # declared is a reconciliation mismatch — regardless of income type.
                # interest_savings/fd/other previously used "savings_interest_missing"
                # (weight 10 → LOW), which under-flagged genuine MEDIUM-risk cases.
                # Now they use "ais_mismatch_income" (weight 25 → MEDIUM) so AIS-only
                # interest income is correctly classified as a reconciliation mismatch.
                risk_type = {
                    "crypto_vda":         "crypto_undeclared",
                    "equity_sale":        "capital_gains_undeclared",
                    "mf_redemption":      "capital_gains_undeclared",
                    "foreign_remittance": "freelance_undeclared",
                    "interest_savings":   "ais_mismatch_income",
                    "interest_fd":        "ais_mismatch_income",
                    "interest_other":     "ais_mismatch_income",
                    "cash_deposit":       "high_value_cash",
                    "property_purchase":  "property_unreported",
                    "property_sale":      "property_unreported",
                }.get(item["type"], "ais_mismatch_income")

                mismatches.append({
                    "type": risk_type,
                    "item": f"{item['type']} ({item['reporter']}): Rs {item['amount']:,.0f}",
                    "amount": item["amount"],
                    "reporter": item["reporter"],
                    "risk_weight": RISK_WEIGHTS.get(risk_type, 10),
                    "section": item.get("section", ""),
                    "ais_category": item.get("ais_category", ""),
                })

        return mismatches

    def _detect_anomalies(self, transactions: list[dict],
                           ais_income: list[dict]) -> list[dict]:
        """Detect anomalies using v2 real-world classifier with fallback to pattern matching."""
        if not transactions:
            return []

        anomalies = []
        ais_types = {i["type"] for i in ais_income}

        # Try v2 ML classifier first
        clf = None
        try:
            from models.transaction_classifier_v2 import RealWorldTransactionClassifier, CLASSIFIER_PATH
            if CLASSIFIER_PATH.exists():
                clf = RealWorldTransactionClassifier()
                clf.load()
        except Exception as e:
            self._log(f"Transaction classifier unavailable: {e}")

        if clf:
            descriptions = [t.get("description", "") for t in transactions]
            directions = [t.get("transaction_type") for t in transactions]
            ml_results = clf.classify_batch(descriptions, directions)

            for i, txn in enumerate(transactions):
                result = ml_results[i]
                if result["tax_relevance"] == "none":
                    continue  # Skip regular expenses and transfers

                label = result["label"]
                amount = float(txn.get("amount", 0))

                # Map classifier label to AIS cross-reference key
                ais_map = {
                    "CRYPTO_TRANSACTION": ["crypto_vda"],
                    "CAPITAL_MARKET": ["equity_sale", "mf_redemption"],
                    "FREELANCE_INCOME": ["foreign_remittance"],
                }
                ais_keys = ais_map.get(label, [])
                in_ais = bool(ais_keys and any(k in ais_types for k in ais_keys))

                anomalies.append({
                    "id": txn.get("id", f"txn_{i}"),
                    "date": txn.get("date"),
                    "description": txn.get("description"),
                    "cleaned": result["cleaned"],
                    "amount": amount,
                    "flag_type": label,
                    "tax_relevance": result["tax_relevance"],
                    "itr_schedule": result["schedule"],
                    "risk_weight": result["risk_weight"],
                    "confidence": result["confidence"],
                    "classification_stage": result["stage"],
                    "transaction_method": result["transaction_method"],
                    "in_ais": in_ais,
                    "requires_user_input": result["confidence"] < 0.85,
                    "reasoning": (
                        f"{label} detected (conf={result['confidence']:.2f}, stage={result['stage']}). "
                        f"{'Found in AIS.' if in_ais else 'Not found in AIS — verify declaration.'}"
                    ),
                })
            return anomalies

        # Fallback: original pattern-based detection
        for txn in transactions:
            desc = txn.get("description", "")
            amount = txn.get("amount", 0)
            txn_type = txn.get("transaction_type", "")
            anomaly = None

            if CRYPTO_VENDORS.search(desc):
                in_ais = "crypto_vda" in ais_types
                anomaly = {
                    "id": txn.get("id", ""), "date": txn.get("date", ""),
                    "description": desc, "amount": amount,
                    "flag_type": "CRYPTO_TRIGGER",
                    "reasoning": f"Crypto transaction detected. {'In AIS.' if in_ais else 'Not in AIS.'}",
                    "in_ais": in_ais,
                    "risk_weight": RISK_WEIGHTS["crypto_undeclared"] if in_ais else 10,
                    "requires_user_input": True, "itr_schedule": "Schedule VDA",
                }
            elif CAPITAL_GAINS_VENDORS.search(desc) and txn_type == "credit":
                in_ais = any(t in ais_types for t in ("equity_sale", "mf_redemption"))
                anomaly = {
                    "id": txn.get("id", ""), "date": txn.get("date", ""),
                    "description": desc, "amount": amount,
                    "flag_type": "CAPITAL_GAINS_TRIGGER",
                    "reasoning": f"Capital gains transaction: {desc}. {'In AIS.' if in_ais else 'Not in AIS.'}",
                    "in_ais": in_ais,
                    "risk_weight": RISK_WEIGHTS["capital_gains_undeclared"],
                    "requires_user_input": True, "itr_schedule": "Schedule CG",
                }
            elif FREELANCE_VENDORS.search(desc) and txn_type == "credit":
                in_ais = "foreign_remittance" in ais_types
                anomaly = {
                    "id": txn.get("id", ""), "date": txn.get("date", ""),
                    "description": desc, "amount": amount,
                    "flag_type": "FREELANCE_INCOME",
                    "reasoning": f"Foreign/freelance credit detected. {'In AIS.' if in_ais else 'Not in AIS.'}",
                    "in_ais": in_ais,
                    "risk_weight": RISK_WEIGHTS["freelance_undeclared"],
                    "requires_user_input": True, "itr_schedule": "Schedule PGBP / OS",
                }
            elif 'CASH' in desc.upper() and 'DEPOSIT' in desc.upper() and amount >= 50000:
                in_ais = "cash_deposit" in ais_types
                anomaly = {
                    "id": txn.get("id", ""), "date": txn.get("date", ""),
                    "description": desc, "amount": amount,
                    "flag_type": "HIGH_VALUE_CASH",
                    "reasoning": f"Cash deposit Rs {amount:,.0f} > Rs 50,000 threshold.",
                    "in_ais": in_ais,
                    "risk_weight": RISK_WEIGHTS["high_value_cash"],
                    "requires_user_input": True, "itr_schedule": "N/A (verify source)",
                }
            if anomaly:
                anomalies.append(anomaly)

        return anomalies

    def _compute_risk_score(self, mismatches: list[dict],
                             anomalies: list[dict]) -> dict:
        """Compute notice risk score from evidence."""
        total = 0
        breakdown = []
        undeclared_amount = 0.0

        # Score from AIS mismatches
        for mismatch in mismatches:
            weight = mismatch.get("risk_weight", 5)
            total += weight
            undeclared_amount += mismatch.get("amount", 0)
            breakdown.append({
                "item": mismatch["item"],
                "weight": weight,
                "reason": f"AIS mismatch: {mismatch['type']}",
            })

        # Score from bank anomalies (avoid double-counting AIS items)
        seen_types = {m.get("type") for m in mismatches}
        for anomaly in anomalies:
            # Only add if the anomaly's risk type wasn't already counted via AIS
            flag = anomaly.get("flag_type", "")
            if anomaly.get("in_ais", False):
                # Already counted via AIS mismatch
                continue
            weight = anomaly.get("risk_weight", 5)
            total += weight
            breakdown.append({
                "item": f"{flag}: {anomaly.get('description', '')[:50]}",
                "weight": weight,
                "reason": anomaly.get("reasoning", "Bank anomaly"),
            })

        # Normalize to 0-100
        score = min(100, total)
        if score < 20:
            level = "LOW"
        elif score < 50:
            level = "MEDIUM"
        elif score < 75:
            level = "HIGH"
        else:
            level = "CRITICAL"

        return {
            "total_score": score,
            "risk_level": level,
            "breakdown": breakdown,
            "undeclared_amount": undeclared_amount,
        }

    def _generate_questions(self, anomalies: list[dict],
                             mismatches: list[dict]) -> list[dict]:
        """Generate targeted interview questions for ambiguous items."""
        questions = []

        # Questions from anomalies
        for anomaly in anomalies:
            if not anomaly.get("requires_user_input", False):
                continue

            flag = anomaly.get("flag_type", "")

            if flag == "CRYPTO_TRIGGER":
                questions.append({
                    "id": f"q_{anomaly.get('id', 'crypto')}",
                    "category": "crypto",
                    "question": (
                        f"AIS reports crypto/VDA transfers via {anomaly.get('description', 'exchange')[:40]}. "
                        f"What was your total cost of acquisition for these assets?"
                    ),
                    "input_type": "number",
                    "context": f"Sale proceeds reported: Rs {anomaly['amount']:,.0f}",
                    "itr_schedule": "Schedule VDA",
                    "required": True,
                })
            elif flag == "CAPITAL_GAINS_TRIGGER":
                questions.append({
                    "id": f"q_{anomaly.get('id', 'cg')}",
                    "category": "capital_gains",
                    "question": (
                        "We detected equity/MF sale proceeds in your bank statement. "
                        "Please upload your Zerodha/Groww P&L statement or enter "
                        "the capital gains amount manually."
                    ),
                    "input_type": "file_or_number",
                    "context": f"Proceeds: Rs {anomaly['amount']:,.0f}",
                    "itr_schedule": "Schedule CG",
                    "required": True,
                })
            elif flag == "FREELANCE_INCOME":
                questions.append({
                    "id": f"q_{anomaly.get('id', 'freelance')}",
                    "category": "freelance",
                    "question": (
                        f"Foreign credit of Rs {anomaly['amount']:,.0f} detected. "
                        "Is this professional/freelance income under Section 44ADA? "
                        "If yes, it will be taxed at presumptive rates (50% deemed profit)."
                    ),
                    "input_type": "boolean",
                    "context": anomaly.get("description", ""),
                    "itr_schedule": "Schedule PGBP",
                    "required": True,
                })
            elif flag == "HIGH_VALUE_CASH":
                questions.append({
                    "id": f"q_{anomaly.get('id', 'cash')}",
                    "category": "cash_deposit",
                    "question": (
                        f"Cash deposit of Rs {anomaly['amount']:,.0f} detected. "
                        "What is the source of this cash? "
                        "(e.g., savings, gift, sale proceeds, agricultural income)"
                    ),
                    "input_type": "text",
                    "context": f"Date: {anomaly.get('date', 'N/A')}",
                    "itr_schedule": "N/A",
                    "required": True,
                })

        # Questions from AIS mismatches (interest not in Form 16)
        for mismatch in mismatches:
            if mismatch["type"] == "savings_interest_missing":
                questions.append({
                    "id": f"q_interest_{mismatch.get('reporter', 'bank')[:10]}",
                    "category": "interest",
                    "question": (
                        f"AIS reports interest income of Rs {mismatch['amount']:,.0f} "
                        f"from {mismatch.get('reporter', 'bank')}. "
                        "This was not reported by your employer in Form 16. "
                        "Please confirm this amount."
                    ),
                    "input_type": "confirm_or_edit",
                    "context": f"Section {mismatch.get('section', '194A')}",
                    "itr_schedule": "Schedule OS",
                    "required": False,
                })

        return questions
