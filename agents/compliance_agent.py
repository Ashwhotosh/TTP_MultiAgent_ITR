"""
compliance_agent.py — ComplianceAgent: ITR Form Selection & Schedule Mapping.

Determines:
1. Which ITR form (ITR-1 / ITR-2 / ITR-3 / ITR-4) the user must file
2. Which schedules are required (CG, VDA, FA, OS, etc.)
3. Maps each income item to its exact schedule + line number
4. Generates the CA Brief — schedule-wise filing map

ITR Form Rules (simplified):
    ITR-1 (Sahaj): Salary + 1 house property + other sources. Income ≤ 50L.
                    NO capital gains. NO foreign assets. NO business income.
    ITR-2:          Salary + capital gains + foreign assets + multiple houses.
                    NO business income.
    ITR-3:          Business/profession income + all other.
    ITR-4 (Sugam):  Presumptive business (44AD/44ADA) + salary + other sources.
"""
from __future__ import annotations

from typing import Any

from .base import BaseAgent, AgentContext, AgentResult


# ITR form eligibility rules
ITR_FORM_RULES = {
    "ITR-1": {
        "allowed": ["salary", "one_house_property", "other_sources", "agricultural_up_to_5000"],
        "blocked_by": ["capital_gains", "crypto_vda", "foreign_assets", "business_income",
                       "multiple_house_property", "income_above_50L", "foreign_income",
                       "director_of_company", "unlisted_shares"],
    },
    "ITR-2": {
        "allowed": ["salary", "house_property", "capital_gains", "other_sources",
                     "crypto_vda", "foreign_assets", "foreign_income"],
        "blocked_by": ["business_income"],
    },
    "ITR-3": {
        "allowed": ["all"],
        "blocked_by": [],
    },
    "ITR-4": {
        "allowed": ["salary", "one_house_property", "other_sources",
                     "presumptive_business_44AD", "presumptive_profession_44ADA"],
        "blocked_by": ["capital_gains", "crypto_vda", "foreign_assets",
                       "brought_forward_losses", "income_above_50L"],
    },
}

# Schedule mapping: income type → ITR schedule
SCHEDULE_MAP = {
    "salary":               {"schedule": "Schedule Salary",    "section": "17(1)"},
    "house_property":       {"schedule": "Schedule HP",        "section": "22-27"},
    "stcg_111a":            {"schedule": "Schedule CG",        "section": "111A"},
    "ltcg_112a":            {"schedule": "Schedule CG",        "section": "112A"},
    "ltcg_112":             {"schedule": "Schedule CG",        "section": "112"},
    "stcg_other":           {"schedule": "Schedule CG",        "section": "CG"},
    "crypto_vda":           {"schedule": "Schedule VDA",       "section": "115BBH"},
    "savings_interest":     {"schedule": "Schedule OS",        "section": "56"},
    "dividend":             {"schedule": "Schedule OS",        "section": "56(2)(i)"},
    "fd_interest":          {"schedule": "Schedule OS",        "section": "56"},
    "freelance_44ada":      {"schedule": "Schedule BP",        "section": "44ADA"},
    "foreign_assets":       {"schedule": "Schedule FA",        "section": ""},
    "foreign_income":       {"schedule": "Schedule FSI",       "section": "90/91"},
    "rsu_perquisite":       {"schedule": "Schedule Salary 17(2)", "section": "17(2)"},
    "employer_nps":         {"schedule": "Schedule VIA",       "section": "80CCD(2)"},
}


class ComplianceAgent(BaseAgent):
    """Determines ITR form and maps income to schedules."""

    def __init__(self, tools: dict[str, Any] | None = None):
        super().__init__(
            name="ComplianceAgent",
            role="Determine ITR form, required schedules, and map every income "
                 "item to its exact schedule location.",
            tools=tools or {},
        )

    def run(self, ctx: AgentContext) -> AgentResult:
        """
        Steps:
            1. Analyze all income types from reconciliation
            2. Determine ITR form
            3. Map each income item to schedule + line
            4. Generate filing checklist
            5. Build CA Brief data structure
        """
        self._log("Determining ITR form and schedule mapping")
        warnings = []

        income_types = self._classify_income_types(ctx)
        itr_form = self._determine_itr_form(income_types)
        schedules = self._map_to_schedules(ctx.reconciliation, ctx.anomalies, ctx)

        # Auto-populate Schedule CG if broker P&L is provided
        import os
        zerodha_csv = ctx.interview_answers.get("zerodha_csv")
        if "capital_gains" in income_types and zerodha_csv and os.path.exists(zerodha_csv):
            self._log(f"Auto-populating Schedule CG from: {zerodha_csv}")
            from schedules.schedule_cg import ScheduleCGBuilder
            try:
                cg_data = ScheduleCGBuilder().build_from_zerodha(zerodha_csv)
                cg_mappings = self._cg_to_schedule_entries(cg_data)
                schedules = [m for m in schedules if m.get("schedule") != "Schedule CG"]
                schedules.extend(cg_mappings)
            except Exception as e:
                self._log(f"Failed to build Schedule CG: {e}")
                warnings.append({"type": "schedule_cg_failed", "source": "compliance", "detail": str(e)})

        # Auto-populate Schedule VDA if crypto trades are provided
        wazirx_csv = ctx.interview_answers.get("wazirx_csv")
        if "crypto_vda" in income_types and wazirx_csv and os.path.exists(wazirx_csv):
            self._log(f"Auto-populating Schedule VDA from: {wazirx_csv}")
            from schedules.schedule_vda import ScheduleVDABuilder
            try:
                vda_data = ScheduleVDABuilder().build_from_wazirx(wazirx_csv)
                vda_mappings = self._vda_to_schedule_entries(vda_data)
                schedules = [m for m in schedules if m.get("schedule") != "Schedule VDA"]
                schedules.extend(vda_mappings)
            except Exception as e:
                self._log(f"Failed to build Schedule VDA: {e}")
                warnings.append({"type": "schedule_vda_failed", "source": "compliance", "detail": str(e)})

        ca_brief = self._build_ca_brief(ctx, itr_form, schedules)

        ctx.itr_form_recommendation = itr_form
        ctx.schedule_mapping = schedules

        # Deduction gap analysis
        try:
            from tools.deduction_gap_analyzer import DeductionGapAnalyzer
            regime = (ctx.regime_comparison or {}).get("recommended", "new")
            ctx.deduction_gaps = DeductionGapAnalyzer().analyze(
                anomalies=ctx.anomalies,
                form16_data=ctx.form16_data,
                gross_income=ctx.gross_income,
                basic_salary=ctx.basic_salary,
                regime=regime,
                city_type=ctx.interview_answers.get("city_type", "metro"),
            )
            n = len(ctx.deduction_gaps.get("gaps", []))
            saving = ctx.deduction_gaps.get("estimated_old_regime_saving", 0)
            if n:
                self._log(f"Deduction gap: {n} gaps, Rs{saving:,.0f} potential saving")
        except Exception as e:
            self._log(f"Deduction gap failed: {e}")
            ctx.deduction_gaps = {}

        return AgentResult(
            agent_name=self.name,
            status="success",
            output={
                "itr_form": itr_form,
                "schedule_mapping": schedules,
                "ca_brief": ca_brief,
            },
            reasoning=f"ITR form recommended: {itr_form['recommended_form']}. Mapped {len(schedules)} schedules.",
            warnings=warnings,
        )

    def _cg_to_schedule_entries(self, cg_data: dict) -> list[dict]:
        entries = []
        for cat, details in cg_data["schedule_cg"].items():
            net = details.get("net", 0.0)
            if details.get("gains", 0.0) > 0 or details.get("losses", 0.0) > 0:
                section = "111A" if cat == "stcg_111a" else ("112A" if cat == "ltcg_112a" else ("112" if cat == "ltcg_112" else "CG"))
                entries.append({
                    "item": f"Capital Gains ({cat.upper().replace('_', ' ')})",
                    "amount": details.get("taxable", net) if cat in ("ltcg_112a", "stcg_111a") else net,
                    "schedule": "Schedule CG",
                    "section": section,
                    "line_hint": f"Schedule CG -> Part B -> {cat.upper()}",
                    "source": "broker_csv",
                    "tds_credit": 0.0,
                    "tds_section": "",
                    "meta": {
                        "gains": details.get("gains"),
                        "losses": details.get("losses"),
                        "exemption": details.get("exemption_125k", 0.0),
                        "tax": details.get("tax"),
                    }
                })
        return entries

    def _vda_to_schedule_entries(self, vda_data: dict) -> list[dict]:
        entries = []
        summary = vda_data["schedule_vda"]
        entries.append({
            "item": "Virtual Digital Assets (VDA) Summary",
            "amount": summary["total_gains"],
            "schedule": "Schedule VDA",
            "section": "115BBH",
            "line_hint": "Part A -> Virtual Digital Asset -> Sl. No. 1",
            "source": "broker_csv",
            "tds_credit": summary["tds_194s_credit"],
            "tds_section": "194S",
            "meta": {
                "total_sale_consideration": summary["total_sale_consideration"],
                "total_cost_of_acquisition": summary["total_cost_of_acquisition"],
                "tax": summary["tax_at_30_percent"],
            }
        })
        return entries

    def _classify_income_types(self, ctx: AgentContext) -> set[str]:
        """Identify all income types present in the reconciled data."""
        types = set()

        if ctx.gross_income > 5000000:
            types.add("income_above_50L")

        ledger = ctx.reconciliation.get("ledger", [])
        for item in ledger:
            name = item.get("item", "").lower()
            schedule = item.get("itr_schedule", "")
            if "salary" in name or schedule == "Schedule Salary":
                types.add("salary")
            if "interest" in name or "dividend" in name or schedule == "Schedule OS":
                types.add("other_sources")
            if schedule == "Schedule HP" or "rent" in name:
                types.add("house_property")
            if schedule == "Schedule CG" or "redemption" in name or "equity" in name:
                types.add("capital_gains")
            if schedule == "Schedule VDA" or "crypto" in name:
                types.add("crypto_vda")
            if schedule == "Schedule FA" or "foreign" in name:
                types.add("foreign_assets")
            if schedule == "Schedule FSI":
                types.add("foreign_income")
            if "freelance" in name or "remittance" in name or schedule in ("Schedule BP", "Schedule PGBP / OS"):
                # Only classify as business_income if confirmed in interview_answers
                is_confirmed = False
                for k, v in ctx.interview_answers.items():
                    if "freelance" in k or "remittance" in k or k == "q_txn_026":
                        if v is True or v == "true" or v == "yes":
                            is_confirmed = True
                if is_confirmed or schedule in ("Schedule BP", "Schedule PGBP / OS"):
                    types.add("business_income")

        # Also check anomalies
        for anomaly in ctx.anomalies:
            flag = anomaly.get("flag_type", "")
            schedule = anomaly.get("itr_schedule", "")
            if flag == "CRYPTO_TRIGGER" or schedule == "Schedule VDA":
                types.add("crypto_vda")
            if flag == "CAPITAL_GAINS_TRIGGER" or schedule == "Schedule CG":
                types.add("capital_gains")
            if flag == "FREELANCE_INCOME" or schedule in ("Schedule BP", "Schedule PGBP / OS"):
                anomaly_id = anomaly.get("id", "")
                is_confirmed = False
                for k, v in ctx.interview_answers.items():
                    if k == f"q_{anomaly_id}":
                        if v is True or v == "true" or v == "yes":
                            is_confirmed = True
                if is_confirmed:
                    types.add("business_income")

        # Infer Schedule OS from concrete evidence only (signal-based, not blanket).
        # Three valid signals — each one grounded in an actual document:
        # (1) Old-regime with declared deductions → 80C/80D investments imply FD/PPF → interest
        # (2) Ledger has an interest or OS-scheduled item (from AIS SFT-004 or bank INT CR)
        # (3) Capital gains / crypto investors: AIS evidence that they are financially active
        form16 = ctx.form16_data or {}
        form16_regime = form16.get("regime", "new")
        form16_deductions = form16.get("deductions_claimed", {})

        # Signal 1: old-regime with active deductions
        if form16_regime == "old" and form16_deductions:
            types.add("other_sources")

        # Chapter VI-A deductions in Form 16 → Schedule VIA required
        if form16_deductions:
            types.add("deductions_vi_a")

        # Signal 2: ledger already has an interest/OS item (AIS SFT-004 or bank INT CR detected)
        ledger = ctx.reconciliation.get("ledger", []) if ctx.reconciliation else []
        for item in ledger:
            item_name = item.get("item", "").lower()
            item_sched = item.get("itr_schedule", "")
            if ("interest" in item_name or "dividend" in item_name
                    or item_sched == "Schedule OS"):
                types.add("other_sources")
                break

        # Signal 3: CG or crypto activity — financially active investors overwhelmingly
        # have savings account interest (strong empirical prior, AIS almost always confirms)
        if "capital_gains" in types or "crypto_vda" in types or "foreign_income" in types:
            types.add("other_sources")

        return types

    def _determine_itr_form(self, income_types: set[str]) -> dict:
        """Apply ITR form eligibility rules.

        Returns:
            {
                "recommended_form": "ITR-2",
                "reason": "Capital gains and VDA income present",
                "blocked_forms": {
                    "ITR-1": ["capital_gains", "crypto_vda"],
                    "ITR-4": ["capital_gains"],
                },
                "required_schedules": ["Schedule CG", "Schedule VDA", "Schedule OS"],
            }
        """
        blocked_forms = {}

        # Evaluate ITR-1 blockers
        itr1_blockers = [b for b in ITR_FORM_RULES["ITR-1"]["blocked_by"] if b in income_types]
        if itr1_blockers:
            blocked_forms["ITR-1"] = itr1_blockers

        # Evaluate ITR-4 blockers
        itr4_blockers = [b for b in ITR_FORM_RULES["ITR-4"]["blocked_by"] if b in income_types]
        if itr4_blockers:
            blocked_forms["ITR-4"] = itr4_blockers

        # Evaluate ITR-2 blockers
        itr2_blockers = [b for b in ITR_FORM_RULES["ITR-2"]["blocked_by"] if b in income_types]
        if itr2_blockers:
            blocked_forms["ITR-2"] = itr2_blockers

        # Select recommended form
        if "ITR-1" not in blocked_forms and ("salary" in income_types or "other_sources" in income_types):
            recommended = "ITR-1"
            reason = "Eligible for ITR-1 (Sahaj) due to simple salary/other sources income within Rs 50L."
        elif "business_income" in income_types:
            if "ITR-4" not in blocked_forms:
                recommended = "ITR-4"
                reason = "Presumptive business/professional income (Section 44AD/44ADA) present."
            else:
                recommended = "ITR-3"
                reason = "Business or professional income present with complex assets (capital gains/VDA)."
        elif "ITR-2" not in blocked_forms:
            recommended = "ITR-2"
            reason = "Capital gains, VDA, or foreign assets/income present without business income."
        else:
            recommended = "ITR-3"
            reason = "Complex income profile requiring ITR-3."

        # Compile required schedules based on income types
        schedules_set = set()
        if "salary" in income_types:
            schedules_set.add("Schedule Salary")
        if "other_sources" in income_types:
            schedules_set.add("Schedule OS")
        if "house_property" in income_types:
            schedules_set.add("Schedule HP")
        if "capital_gains" in income_types:
            schedules_set.add("Schedule CG")
        if "crypto_vda" in income_types:
            schedules_set.add("Schedule VDA")
        if "foreign_assets" in income_types:
            schedules_set.add("Schedule FA")
        if "foreign_income" in income_types:
            schedules_set.add("Schedule FSI")
        if "business_income" in income_types or recommended in ("ITR-3", "ITR-4"):
            schedules_set.add("Schedule BP")
        if "deductions_vi_a" in income_types:
            schedules_set.add("Schedule VIA")

        return {
            "recommended_form": recommended,
            "reason": reason,
            "blocked_forms": blocked_forms,
            "required_schedules": sorted(list(schedules_set)),
        }

    def _map_to_schedules(self, reconciliation: dict,
                          anomalies: list[dict], ctx: AgentContext = None) -> list[dict]:
        """Map each income item to its ITR schedule.

        Returns list of:
            {
                "item": "Savings interest - SBI",
                "amount": 14200,
                "schedule": "Schedule OS",
                "section": "56",
                "line_hint": "Income from Other Sources → Interest",
                "source": "ais",
                "tds_credit": 1420,
                "tds_section": "194A",
            }
        """
        mappings = []
        ledger = reconciliation.get("ledger", [])
        interview_answers = ctx.interview_answers if ctx else {}

        # Fetch TDS entries — AISParser stores them under "tds_entries"
        # Use a mutable copy so each entry is consumed only once
        tds_entries = []
        if ctx and ctx.ais_data:
            raw = ctx.ais_data.get("tds_entries", ctx.ais_data.get("tds_tcs", []))
            tds_entries = list(raw)  # copy so we can pop matched entries

        for item in ledger:
            name = item.get("item", "")
            name_lower = name.lower()

            gross_f16 = item.get("amount_form16", 0.0)
            gross_ais = item.get("amount_ais", 0.0)
            gross_bank = item.get("amount_bank", 0.0)
            amount = max(gross_f16, gross_ais, gross_bank)

            schedule = item.get("itr_schedule", "Schedule OS")
            section = "56"
            line_hint = "Income from Other Sources"
            source = item.get("match_status", "ais")

            if "salary" in name_lower:
                schedule = "Schedule Salary"
                section = "17(1)"
                line_hint = "Salary Details -> Gross Salary under Section 17(1)"
            elif "savings interest" in name_lower or "interest on savings" in name_lower:
                schedule = "Schedule OS"
                section = "56"
                line_hint = "Income from Other Sources -> Savings bank interest"
            elif "fixed deposit" in name_lower or "fd interest" in name_lower:
                schedule = "Schedule OS"
                section = "56"
                line_hint = "Income from Other Sources -> FD Interest"
            elif "dividend" in name_lower:
                schedule = "Schedule OS"
                section = "56(2)(i)"
                line_hint = "Income from Other Sources -> Dividend"
            elif "crypto" in name_lower or "virtual digital" in name_lower:
                schedule = "Schedule VDA"
                section = "115BBH"
                line_hint = "Part A -> Virtual Digital Asset -> Sl. No. 1"
                
                # Subtract acquisition cost from proceeds if answered
                cost = 0.0
                for k, v in interview_answers.items():
                    if "crypto" in k.lower() or "vda" in k.lower() or k == "q_txn_017":
                        try:
                            cost = float(v)
                        except ValueError:
                            pass
                if cost > 0:
                    amount = max(0.0, amount - cost)
                    source = "ais + interview"
            elif "mutual fund" in name_lower or "redemption" in name_lower or "equity" in name_lower or "capital gains" in name_lower:
                schedule = "Schedule CG"
                section = "112A" if "elss" in name_lower or "mutual fund" in name_lower else "111A"
                line_hint = "Schedule CG -> Capital Gains details"
                
                # Check for cost of acquisition in interview
                cost = 0.0
                for k, v in interview_answers.items():
                    if "cg" in k.lower() or "equity" in k.lower() or "mf" in k.lower() or k == "q_txn_035" or k == "q_txn_019":
                        try:
                            cost = float(v)
                        except ValueError:
                            pass
                if cost > 0:
                    amount = max(0.0, amount - cost)
                    source = "ais + interview"
            elif "freelance" in name_lower or "remittance" in name_lower:
                is_business = False
                for k, v in interview_answers.items():
                    if "freelance" in k or k == "q_txn_026":
                        if v is True or v == "true" or v == "yes":
                            is_business = True
                if is_business:
                    schedule = "Schedule BP"
                    section = "44ADA"
                    line_hint = "Income from Profession -> Section 44ADA (Presumptive)"
                    amount = amount * 0.5  # 50% deemed profit
                    source = "bank + interview"
                else:
                    schedule = "Schedule OS"
                    section = "56"
                    line_hint = "Income from Other Sources -> Others"

            # Match TDS Credit
            tds_credit = 0.0
            tds_section = ""
            for entry in tds_entries:
                deductor = entry.get("deductor_name", "").lower()
                sec = entry.get("section", "")
                
                matched = False
                if "salary" in name_lower and sec == "192":
                    matched = True
                elif ("savings interest" in name_lower or "interest savings" in name_lower) and sec == "194A" and "hdfc" in deductor:
                    matched = True
                elif ("fixed deposit" in name_lower or "interest fd" in name_lower or "fd interest" in name_lower) and sec == "194A" and ("sbi" in deductor or "state bank" in deductor):
                    matched = True
                elif ("crypto" in name_lower or "vda" in name_lower) and sec == "194S":
                    matched = True
                elif ("freelance" in name_lower or "remittance" in name_lower) and sec in ("194J", "195"):
                    matched = True
                    
                if matched:
                    tds_credit = entry.get("tax_deducted", 0.0)
                    tds_section = sec
                    tds_entries.remove(entry)  # consume so it can't be re-matched
                    break

            mappings.append({
                "item": name,
                "amount": amount,
                "schedule": schedule,
                "section": section,
                "line_hint": line_hint,
                "source": source,
                "tds_credit": tds_credit,
                "tds_section": tds_section,
            })

        return mappings

    def _build_ca_brief(self, ctx, itr_form, schedules) -> dict:
        """Build the CA Brief data structure.

        This is the structured 2-page report a CA can use to
        understand the client's situation in 5 minutes.
        """
        return {
            "summary": "CA Brief is planned for Week 3.",
            "itr_form": itr_form.get("recommended_form"),
            "schedule_count": len(schedules),
        }
