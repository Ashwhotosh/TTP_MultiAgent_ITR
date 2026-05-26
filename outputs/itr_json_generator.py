"""
itr_json_generator.py — ITR-2 JSON export.
Generates ITR-2 JSON matching the IT Department schema (FY 25-26 / AY 26-27).
Only implements schedules built in the pipeline: Salary, OS, CG, VDA, Part B-TI, Part B-TTI.
"""
from __future__ import annotations


class ITRJsonGenerator:
    """Generates ITR-2 JSON from a FinITR-AI v3 pipeline report dict."""

    def generate(self, report: dict) -> dict:
        gross = report.get("gross_income", 0.0)
        ay = report.get("assessment_year", "2026-27")
        comp = report.get("regime_comparison", {}) or {}
        recommended = comp.get("recommended", "new")

        new_reg = comp.get("new_regime", {}) or {}
        old_reg = comp.get("old_regime", {}) or {}
        new_tax = new_reg.get("total_tax_liability", 0.0)
        old_tax = old_reg.get("total_tax_liability", 0.0)
        tax_payable = min(new_tax, old_tax) if (new_tax and old_tax) else (new_tax or old_tax)

        schedule_mapping = report.get("schedule_mapping", []) or []
        tds_claimed = sum(m.get("tds_credit", 0.0) for m in schedule_mapping)
        refund_due = round(max(0.0, tds_claimed - tax_payable), 2)
        net_payable = round(max(0.0, tax_payable - tds_claimed), 2)

        schedule_s = self._build_schedule_s(report)
        schedule_os = self._build_schedule_os(report)
        schedule_cg = self._build_schedule_cg(report)
        schedule_vda = self._build_schedule_vda(report)

        salary_income = (schedule_s.get("Salary") or [{}])[0].get("GrossSalary", 0.0) if schedule_s.get("Salary") else 0.0
        os_income = (schedule_os.get("IncFromOthSrc") or {}).get("OthSrcIncome", 0.0)
        cg_stcg = (schedule_cg.get("ShortTermCapGainFor15Per") or {}).get("ShortTermCapGain", 0.0)
        cg_ltcg = (schedule_cg.get("LongTermCapGain20Per") or {}).get("LTCGAfterExemption", 0.0)
        cg_income = cg_stcg + cg_ltcg
        vda_income = sum(
            max(0.0, v.get("Consideration", 0) - v.get("CostOfAcq", 0))
            for v in (schedule_vda.get("VDADetails") or [])
        )
        total_income = salary_income + os_income + cg_income + vda_income

        ais = report.get("ais_data", {}) or {}

        return {
            "ITR": {
                "ITR2": {
                    "PartA_GEN1": {
                        "PersonalInfo": {
                            "PAN": ais.get("pan", ""),
                            "Name": ais.get("name", ""),
                            "AssessmentYear": ay,
                            "FilingDate": "",
                        },
                        "FilingStatus": {
                            "ReturnFileSec": 139,
                            "NewTaxRegime": "Y" if recommended == "new" else "N",
                            "EmployerCategory": "OTH",
                        },
                    },
                    "ScheduleS": schedule_s,
                    "ScheduleOS": schedule_os,
                    "ScheduleCGPost": schedule_cg,
                    "ScheduleVDA": schedule_vda,
                    "PartBTI": {
                        "TotalIncome": round(total_income, 0),
                        "SalaryIncome": round(salary_income, 0),
                        "OtherSourcesIncome": round(os_income, 0),
                        "CapitalGainIncome": round(cg_income, 0),
                        "VDAIncome": round(vda_income, 0),
                    },
                    "PartBTTI": {
                        "TaxPayable": round(net_payable, 0),
                        "TDSClaimed": round(tds_claimed, 0),
                        "RefundDue": round(refund_due, 0),
                        "GrossTaxLiability": round(tax_payable, 0),
                    },
                }
            }
        }

    def _build_schedule_s(self, report: dict) -> dict:
        mappings = report.get("schedule_mapping", []) or []
        salary_entries = [m for m in mappings if m.get("schedule") == "Schedule Salary"]
        form16 = report.get("form16_data", {}) or {}

        salaries = []
        for entry in salary_entries:
            salaries.append({
                "NameOfEmployer": entry.get("item", "").replace("Salary - ", "") or form16.get("employer_name", "Employer"),
                "GrossSalary": round(entry.get("amount", 0), 0),
                "TaxDeductedByEmployer": round(entry.get("tds_credit", 0), 0),
                "Section": "17(1)",
            })

        if not salaries and report.get("gross_income", 0) > 0:
            salaries.append({
                "NameOfEmployer": form16.get("employer_name", "Employer"),
                "GrossSalary": round(report.get("gross_income", 0), 0),
                "TaxDeductedByEmployer": round(form16.get("tds_deducted", 0), 0),
                "Section": "17(1)",
            })

        return {"Salary": salaries} if salaries else {}

    def _build_schedule_os(self, report: dict) -> dict:
        mappings = report.get("schedule_mapping", []) or []
        os_entries = [m for m in mappings if m.get("schedule") == "Schedule OS"]
        total = sum(e.get("amount", 0) for e in os_entries)
        if total <= 0:
            return {}
        return {
            "IncFromOthSrc": {
                "OthSrcIncome": round(total, 0),
                "IncChargeable": round(total, 0),
            }
        }

    def _build_schedule_cg(self, report: dict) -> dict:
        mappings = report.get("schedule_mapping", []) or []
        cg_entries = [m for m in mappings if m.get("schedule") == "Schedule CG"]
        if not cg_entries:
            return {}

        stcg = sum(e.get("amount", 0) for e in cg_entries if e.get("section") == "111A")
        ltcg = sum(e.get("amount", 0) for e in cg_entries if e.get("section") == "112A")
        ltcg_other = sum(e.get("amount", 0) for e in cg_entries if e.get("section") not in ("111A", "112A"))

        result = {}
        if stcg > 0:
            result["ShortTermCapGainFor15Per"] = {"ShortTermCapGain": round(stcg, 0)}
        if ltcg > 0:
            exemption = min(ltcg, 125000)
            result["LongTermCapGain20Per"] = {
                "LTCGBeforeExemption": round(ltcg, 0),
                "ExemptionLimit125K": round(exemption, 0),
                "LTCGAfterExemption": round(max(0, ltcg - exemption), 0),
            }
        if ltcg_other > 0:
            result["LongTermCapGainOther"] = {"LTCGAtApplicableRate": round(ltcg_other, 0)}
        return result

    def _build_schedule_vda(self, report: dict) -> dict:
        mappings = report.get("schedule_mapping", []) or []
        vda_entries = [m for m in mappings if m.get("schedule") == "Schedule VDA"]
        if not vda_entries:
            return {}

        details = []
        for entry in vda_entries:
            meta = entry.get("meta", {}) or {}
            consideration = meta.get("total_sale_consideration", entry.get("amount", 0))
            cost = meta.get("total_cost_of_acquisition", 0)
            gain = max(0.0, consideration - cost)
            details.append({
                "NameOfVDA": entry.get("item", "Crypto/VDA"),
                "DateOfTransfer": "",
                "Consideration": round(consideration, 0),
                "CostOfAcq": round(cost, 0),
                "GainOrLoss": round(gain, 0),
                "TaxAt30Percent": round(gain * 0.30, 0),
            })

        return {"VDADetails": details} if details else {}
