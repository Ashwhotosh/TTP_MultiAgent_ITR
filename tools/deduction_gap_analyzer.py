"""
tools/deduction_gap_analyzer.py — Find unclaimed tax deductions.

Cross-references classified bank transactions against Form 16
to identify "money left on the table" and calculate potential
savings under Old vs New Regime.
"""
from __future__ import annotations
from typing import Any

DEDUCTION_LIMITS = {
    "80C":         150000,
    "80D_self":     25000,
    "80CCD_1B":     50000,
    "24b":         200000,
    "80GG":         60000,
}


class DeductionGapAnalyzer:

    def analyze(
        self,
        anomalies: list[dict],
        form16_data: dict,
        gross_income: float,
        basic_salary: float,
        regime: str = "new",
        city_type: str = "metro",
    ) -> dict[str, Any]:
        groups  = self._group(anomalies)
        claimed = self._extract_claimed(form16_data)
        gaps    = []

        for fn in (self._hra_gap, self._insurance_gap,
                   self._home_loan_gap, self._investment_gap):
            gap = fn(groups, claimed, gross_income, basic_salary, city_type)
            if gap:
                gaps.append(gap)

        rate = self._rate(gross_income, regime)
        old_saving = sum(g["gap_amount"] * rate for g in gaps if g["eligible_old_regime"])
        new_saving = sum(g["gap_amount"] * rate for g in gaps if g["eligible_new_regime"])

        for g in gaps:
            g["saving_old_regime"] = round(g["gap_amount"] * rate) if g["eligible_old_regime"] else 0
            g["saving_new_regime"] = round(g["gap_amount"] * rate) if g["eligible_new_regime"] else 0
            g["blocked_under_new_regime"] = not g["eligible_new_regime"]

        switch_saving = old_saving - new_saving
        return {
            "gaps":                        gaps,
            "total_unclaimed_old_regime":  round(sum(g["gap_amount"] for g in gaps if g["eligible_old_regime"])),
            "estimated_old_regime_saving": round(old_saving),
            "estimated_new_regime_saving": round(new_saving),
            "regime_switch_recommended":   switch_saving > 10000,
            "switch_saving":               round(switch_saving),
            "current_regime":              regime,
            "summary":                     self._summary(gaps, old_saving, new_saving, regime),
        }

    # ── gap detectors ───────────────────────────────────────────────────

    def _hra_gap(self, groups, claimed, gross, basic, city_type):
        txns = groups.get("RENT_PAID", []) or groups.get("rent_paid", [])
        if not txns:
            return None
        annual_rent = self._annualize(txns)
        hra_recv    = float(claimed.get("hra_received", 0))
        hra_claimed = float(claimed.get("hra_exemption_claimed", 0))

        if hra_recv > 0:
            exempt = self._hra_exempt(basic, hra_recv, annual_rent, city_type == "metro")
            gap    = max(0, exempt - hra_claimed)
            if gap < 1000:
                return None
            return dict(
                type="HRA", section="Section 10(13A)",
                description=f"Rent ₹{annual_rent:,.0f}/yr detected. HRA received but not claimed.",
                detected_amount=round(annual_rent), claimed_amount=round(hra_claimed),
                gap_amount=round(gap), max_allowed=round(exempt),
                eligible_old_regime=True, eligible_new_regime=False,
                note="HRA exemption not available under New Regime. Switching unlocks this deduction.",
                caveat=None,
            )
        else:
            limit = min(annual_rent - 0.10 * gross, 0.25 * gross, DEDUCTION_LIMITS["80GG"])
            gap   = max(0, limit - float(claimed.get("80GG", 0)))
            if gap < 1000:
                return None
            return dict(
                type="80GG", section="Section 80GG",
                description=f"Rent ₹{annual_rent:,.0f}/yr paid, no HRA in salary. Section 80GG deduction possible.",
                detected_amount=round(annual_rent), claimed_amount=float(claimed.get("80GG", 0)),
                gap_amount=round(gap), max_allowed=DEDUCTION_LIMITS["80GG"],
                eligible_old_regime=True, eligible_new_regime=False,
                note="Section 80GG not available under New Regime.",
                caveat="Requires no house ownership and no HRA component in salary.",
            )

    def _insurance_gap(self, groups, claimed, *_):
        txns = groups.get("INSURANCE_PREMIUM", []) or groups.get("insurance_premium", [])
        if not txns:
            return None
        lic    = sum(abs(float(t.get("amount",0))) for t in txns
                     if any(k in str(t.get("description","")).upper() for k in ("LIC","LIFE")))
        health = sum(abs(float(t.get("amount",0))) for t in txns
                     if any(k in str(t.get("description","")).upper() for k in ("HEALTH","MEDICLAIM","BUPA","STAR")))
        other  = sum(abs(float(t.get("amount",0))) for t in txns) - lic - health

        c80c = float(claimed.get("80C",0))
        c80d = float(claimed.get("80D",0))

        breakdown = {}
        if lic + other > 0:
            gap = max(0, min(lic + other, DEDUCTION_LIMITS["80C"]) - c80c)
            if gap > 1000: breakdown["80C"] = round(gap)
        if health > 0:
            gap = max(0, min(health, DEDUCTION_LIMITS["80D_self"]) - c80d)
            if gap > 1000: breakdown["80D"] = round(gap)

        if not breakdown:
            return None
        return dict(
            type="INSURANCE", section=" / ".join(breakdown.keys()),
            description=f"Insurance: LIC ₹{lic:,.0f}, Health ₹{health:,.0f} — not claimed in Form 16.",
            detected_amount=round(lic + health + other), claimed_amount=round(c80c + c80d),
            gap_amount=sum(breakdown.values()), max_allowed=DEDUCTION_LIMITS["80C"],
            gap_breakdown=breakdown,
            eligible_old_regime=True, eligible_new_regime=False,
            note="80C and 80D not available under New Regime.",
            caveat=None,
        )

    def _home_loan_gap(self, groups, claimed, *_):
        txns = groups.get("LOAN_EMI", []) or groups.get("loan_emi", [])
        home = [t for t in txns
                if any(k in str(t.get("description","")).upper() for k in ("HOME","HOUSING","HOUSE"))]
        if not home:
            return None
        emi = self._annualize(home)
        est_int = emi * 0.65
        est_pri = emi * 0.35
        c24b  = float(claimed.get("24b",0))
        c80c  = float(claimed.get("80C",0))
        gap_i = max(0, min(est_int, DEDUCTION_LIMITS["24b"]) - c24b)
        gap_p = max(0, min(est_pri, max(0, DEDUCTION_LIMITS["80C"] - c80c)))
        if gap_i < 1000 and gap_p < 1000:
            return None
        return dict(
            type="HOME_LOAN", section="Section 24(b) + 80C",
            description=f"Home loan EMI ₹{emi:,.0f}/yr. Interest (~₹{est_int:,.0f}) not claimed under 24(b).",
            detected_amount=round(emi), claimed_amount=round(c24b),
            gap_amount=round(gap_i + gap_p), max_allowed=DEDUCTION_LIMITS["24b"],
            gap_breakdown={"24b_interest": round(gap_i), "80C_principal": round(gap_p)},
            eligible_old_regime=True, eligible_new_regime=False,
            note="Section 24(b) home loan interest not available under New Regime.",
            caveat="Interest estimate (~65% of EMI) is approximate. Get exact figure from bank interest certificate.",
        )

    def _investment_gap(self, groups, claimed, *_):
        txns = groups.get("INVESTMENT_TAX_SAVING", []) or groups.get("investment_tax_saving", [])
        if not txns:
            return None
        elss  = sum(abs(float(t.get("amount",0))) for t in txns if "ELSS" in str(t.get("description","")).upper())
        nps   = sum(abs(float(t.get("amount",0))) for t in txns if "NPS"  in str(t.get("description","")).upper())
        ppf   = sum(abs(float(t.get("amount",0))) for t in txns if "PPF"  in str(t.get("description","")).upper())
        other = sum(abs(float(t.get("amount",0))) for t in txns) - elss - nps - ppf

        c80c = float(claimed.get("80C",0))
        cccd = float(claimed.get("80CCD_1B",0))

        breakdown = {}
        gap_80c = max(0, min(elss + ppf + other, DEDUCTION_LIMITS["80C"]) - c80c)
        gap_nps = max(0, min(nps, DEDUCTION_LIMITS["80CCD_1B"]) - cccd)
        if gap_80c > 1000: breakdown["80C_ELSS_PPF"] = round(gap_80c)
        if gap_nps  > 1000: breakdown["80CCD_1B_NPS"] = round(gap_nps)

        if not breakdown:
            return None
        return dict(
            type="INVESTMENT", section="80C / 80CCD(1B)",
            description=f"Investments: ELSS ₹{elss:,.0f}, NPS ₹{nps:,.0f}, PPF ₹{ppf:,.0f} — not claimed.",
            detected_amount=round(elss + nps + ppf + other), claimed_amount=round(c80c + cccd),
            gap_amount=sum(breakdown.values()), max_allowed=DEDUCTION_LIMITS["80C"] + DEDUCTION_LIMITS["80CCD_1B"],
            gap_breakdown=breakdown,
            eligible_old_regime=True, eligible_new_regime=False,
            note="80C and voluntary NPS (80CCD-1B) not available under New Regime.",
            caveat=None,
        )

    # ── helpers ─────────────────────────────────────────────────────────

    def _group(self, anomalies):
        g = {}
        for t in anomalies:
            lbl = t.get("flag_type") or t.get("label") or ""
            if lbl:
                g.setdefault(lbl.upper(), []).append(t)
        return g

    def _extract_claimed(self, form16):
        d = form16.get("deductions_claimed", {}) or {}
        return {
            "80C":                  float(d.get("80C",0) or 0),
            "80D":                  float(d.get("80D",0) or 0),
            "80CCD_1B":             float(d.get("80CCD_1B",0) or d.get("80CCD_1b",0) or 0),
            "24b":                  float(d.get("24b",0) or 0),
            "80GG":                 float(d.get("80GG",0) or 0),
            "hra_received":         float(form16.get("hra_received",0) or 0),
            "hra_exemption_claimed":float(form16.get("hra_exemption_claimed",0) or 0),
        }

    def _annualize(self, txns):
        total = sum(abs(float(t.get("amount",0))) for t in txns)
        if len(txns) >= 10:
            return (total / len(txns)) * 12
        return total

    def _hra_exempt(self, basic, hra_recv, rent, metro):
        return min(hra_recv, (0.5 if metro else 0.4) * basic, max(0, rent - 0.1 * basic))

    def _rate(self, income, regime):
        if regime == "new":
            if income <= 700000:  return 0.05
            if income <= 1000000: return 0.10
            if income <= 1200000: return 0.15
            if income <= 1500000: return 0.20
            return 0.30
        else:
            if income <= 250000:  return 0.0
            if income <= 500000:  return 0.05
            if income <= 1000000: return 0.20
            return 0.30

    def _summary(self, gaps, old_saving, new_saving, regime):
        if not gaps:
            return "No significant unclaimed deductions detected."
        blocked = sum(1 for g in gaps if g.get("blocked_under_new_regime"))
        if blocked > 0 and regime == "new":
            return (f"Found {len(gaps)} unclaimed deduction opportunities totalling "
                    f"Rs{old_saving:,.0f} in potential savings. "
                    f"{blocked} are Old Regime only — consider switching.")
        return f"Found {len(gaps)} unclaimed deductions — potential saving Rs{old_saving:,.0f}."
