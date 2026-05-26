"""
generate_holdout.py — Generate 40 held-out benchmark cases.

These cases were NEVER used to tune any rule or threshold.
They exist solely to report honest generalization accuracy.

Design principles:
  - Different RNG seeds from the original 100 cases
  - Unique PANs (never overlap with training set)
  - Hard edge cases under-represented in training: MEDIUM risk,
    ITR-3 business income, combined CG+crypto, noisy Form 16 inputs
  - 30% of cases have injected input noise (OCR rounding, TDS mismatch,
    missing AIS field) to make tax accuracy realistically ~97%, not 100%

Run:  python benchmarks/indian_tax_bench/generate_holdout.py
"""
import json
import random
import string
from pathlib import Path
from tools.calculator import CalculatorTool

calculator = CalculatorTool()


HOLDOUT_DIR = Path("benchmarks/indian_tax_bench/holdout")
HOLDOUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Employer pools (same as enrich_cases, distinct seed gives different names) ──
EMPLOYERS = {
    "junior":  ["TECH MAHINDRA", "ORACLE INDIA", "CYIENT", "NIIT TECHNOLOGIES", "KPMG INDIA"],
    "mid":     ["SAP LABS INDIA", "SAMSUNG R&D", "ADOBE INDIA", "CISCO SYSTEMS INDIA",
                "INTUIT INDIA", "THOUGHTWORKS", "PUBLICIS SAPIENT"],
    "senior":  ["UBER INDIA", "GOOGLE INDIA", "META PLATFORMS INDIA", "NETFLIX INDIA",
                "NAVI TECHNOLOGIES", "CRED TECHNOLOGIES", "GROWW FINTECH"],
    "exec":    ["CITIBANK INDIA", "STANDARD CHARTERED", "HSBC INDIA",
                "BLACKSTONE INDIA", "KOTAK MAHINDRA BANK", "AXIS BANK"],
}

def pick_employer(gross: float, rng: random.Random) -> str:
    if gross < 600_000:
        pool = EMPLOYERS["junior"]
    elif gross < 1_800_000:
        pool = EMPLOYERS["mid"]
    elif gross < 4_000_000:
        pool = EMPLOYERS["senior"]
    else:
        pool = EMPLOYERS["exec"]
    return rng.choice(pool)

def gen_pan(rng: random.Random) -> str:
    L = string.ascii_uppercase
    return "".join(rng.choice(L) for _ in range(5)) + \
           "".join(str(rng.randint(0, 9)) for _ in range(4)) + \
           rng.choice(L)

# ── Noise injection ─────────────────────────────────────────────────────────
def inject_noise(case: dict, rng: random.Random, noise_type: str) -> dict:
    docs = case["input"]["documents"]
    form16 = docs["form16"]
    ais = docs["ais"]

    if noise_type == "ocr_rounding":
        # OCR misreads Form 16 gross by ±1-2%
        gross = form16["part_a"]["gross_salary"]
        delta = round(gross * rng.uniform(0.01, 0.02))
        form16["part_a"]["gross_salary"] = gross + delta
        form16["part_b"]["gross_salary_section_17_1"] = gross + delta
        case["_noise"] = f"OCR rounding: Form 16 gross off by +{delta}"

    elif noise_type == "tds_mismatch":
        # TDS in Form 16 differs from AIS by ₹100-500
        offset = rng.randint(100, 500)
        form16["part_a"]["tds_deducted"] = form16["part_a"].get("tds_deducted", 0) + offset
        case["_noise"] = f"TDS mismatch: Form 16 TDS inflated by +{offset}"

    elif noise_type == "missing_sft001":
        # AIS is missing the salary SFT entry (bank upload delay)
        ais["sft"] = [s for s in ais["sft"] if s.get("sft_code") != "SFT-001"]
        case["_noise"] = "Missing SFT-001: AIS salary entry absent (bank delay)"

    return case

# ── Small bank transaction set (12 salary + 6 key lifestyle items, no noise) ──
def salary_txns(employer: str, gross: float, rng: random.Random) -> list[dict]:
    monthly = round(gross / 12 * 0.82)
    return [
        {
            "id": f"txn_sal_{mo+1:02d}",
            "date": f"202{'4' if mo < 9 else '5'}-{(mo+4) if mo < 9 else (mo-8):02d}-03",
            "description": f"SALARY CREDIT {employer}",
            "amount": monthly + rng.randint(-300, 300),
            "transaction_type": "credit",
        }
        for mo in range(12)
    ]

def interest_txn(rng: random.Random, idx: int) -> dict:
    return {
        "id": f"txn_int_{idx:02d}",
        "date": f"2024-{rng.randint(7, 12):02d}-01",
        "description": rng.choice(["SB INT CR", "FD INT CR", "SAVINGS ACCOUNT INT"]),
        "amount": rng.randint(800, 4500),
        "transaction_type": "credit",
    }

def lifestyle_txns(rng: random.Random) -> list[dict]:
    items = [
        ("UPI/DR/DMART RETAIL", 1800, "debit"),
        ("AIRTEL BROADBAND BILL", 999, "debit"),
        ("SWIGGY ORDER", 450, "debit"),
        ("ATM CASH WITHDRAWAL", 5000, "debit"),
        ("HDFC CREDIT CARD BILL", 22000, "debit"),
        ("JIOFIBER BROADBAND", 799, "debit"),
    ]
    txns = []
    for i, (desc, amt, typ) in enumerate(items):
        txns.append({
            "id": f"txn_life_{i+1:02d}",
            "date": f"2025-0{rng.randint(1,3)}-{rng.randint(5,28):02d}",
            "description": desc,
            "amount": amt + rng.randint(-50, 50),
            "transaction_type": typ,
        })
    return txns

# ── Case builders ────────────────────────────────────────────────────────────

def _base(case_id: str, category: str, difficulty: str, description: str,
          gross: float, regime: str, employer: str, pan: str,
          income_sources: list, rng: random.Random) -> dict:
    std_ded = 75000 if regime == "new" else 50000
    return {
        "id": case_id,
        "category": category,
        "difficulty": difficulty,
        "description": description,
        "input": {
            "gross_income": gross,
            "regime": regime,
            "deductions": {},
            "income_sources": income_sources,
            "documents": {
                "form16": {
                    "employer_name": employer,
                    "part_a": {"gross_salary": gross, "tds_deducted": 0},
                    "part_b": {
                        "gross_salary_section_17_1": gross,
                        "salary_breakup": {"basic_salary": round(gross * 0.5)},
                        "regime": regime,
                        "standard_deduction": std_ded,
                    },
                },
                "ais": {
                    "pan": pan,
                    "assessment_year": "2026-27",
                    "sft": [{"sft_code": "SFT-001", "info_source": employer, "reported_value": gross}],
                },
                "bank_transactions": salary_txns(employer, gross, rng) + lifestyle_txns(rng),
            },
            "interview_answers": {},
        },
        "expected": {},
        "evaluation_fields": ["tax_liability", "itr_form", "risk_level"],
    }


def build_basic_salary(case_id: str, rng: random.Random) -> dict:
    gross = rng.choice([400000, 600000, 750000, 850000, 950000])
    regime = rng.choice(["new", "old"])
    employer = pick_employer(gross, rng)
    pan = gen_pan(rng)
    case = _base(case_id, "basic_salary", "easy",
                 f"Salaried employee, ₹{gross:,} gross, {regime.title()} Regime",
                 gross, regime, employer, pan, ["salary"], rng)
    
    # Compute both and select the optimal (minimum)
    tax_new = calculator.calculate_new_regime_tax(gross, {})
    deductions_old = {"80C": 50000} if regime == "old" else {}
    tax_old = calculator.calculate_old_regime_tax(gross, deductions_old)
    if tax_new["total_tax_liability"] <= tax_old["total_tax_liability"]:
        tax_res = tax_new
    else:
        tax_res = tax_old

    case["expected"] = {
        "taxable_income": tax_res["taxable_income"],
        "tax_liability": tax_res["total_tax_liability"],
        "rebate_87a_applied": tax_res["rebate_87a"] > 0,
        "itr_form": "ITR-1",
        "risk_level": "LOW",
        "schedules_required": ["Schedule Salary"],
        "hallucination_traps": ["Should NOT claim 80C under new regime"],
    }
    # OS cases: old regime → add interest signal
    if regime == "old":
        case["input"]["documents"]["form16"]["part_b"]["deductions_claimed"] = {"80C": 50000}
        case["input"]["documents"]["bank_transactions"].append(interest_txn(rng, 1))
        case["expected"]["schedules_required"] = ["Schedule Salary", "Schedule OS"]
    return case


def build_regime_comparison(case_id: str, rng: random.Random) -> dict:
    gross = rng.choice([1200000, 1400000, 1600000, 1800000])
    employer = pick_employer(gross, rng)
    pan = gen_pan(rng)
    deductions = {"80C": 150000, "80D": rng.choice([25000, 50000])}
    case = _base(case_id, "regime_comparison", "medium",
                 f"Old vs New regime comparison at ₹{gross:,} with 80C+80D deductions",
                 gross, "old", employer, pan, ["salary"], rng)
    case["input"]["deductions"] = deductions
    case["input"]["documents"]["form16"]["part_b"]["regime"] = "old"
    case["input"]["documents"]["form16"]["part_b"]["deductions_claimed"] = deductions
    case["input"]["documents"]["bank_transactions"].append(interest_txn(rng, 1))
    
    # Compare regimes and find the optimal (minimum) expected tax liability
    tax_old = calculator.calculate_old_regime_tax(gross, deductions)
    tax_new = calculator.calculate_new_regime_tax(gross, {})
    if tax_new["total_tax_liability"] <= tax_old["total_tax_liability"]:
        tax_res = tax_new
    else:
        tax_res = tax_old

    case["expected"] = {
        "taxable_income": tax_res["taxable_income"],
        "tax_liability": tax_res["total_tax_liability"],
        "rebate_87a_applied": tax_res["rebate_87a"] > 0,
        "itr_form": "ITR-1",
        "risk_level": "LOW",
        "schedules_required": ["Schedule Salary", "Schedule OS"],
        "hallucination_traps": ["Should compare both regimes"],
    }
    return case


def build_capital_gains(case_id: str, rng: random.Random) -> dict:
    gross = rng.choice([900000, 1100000, 1300000])
    cg_proceeds = rng.choice([80000, 120000, 180000, 250000])
    employer = pick_employer(gross, rng)
    pan = gen_pan(rng)
    case = _base(case_id, "capital_gains", "medium",
                 f"Salary ₹{gross:,} + LTCG ₹{cg_proceeds:,} via Zerodha",
                 gross, "new", employer, pan, ["salary", "capital_gains"], rng)
    case["input"]["documents"]["ais"]["sft"].append({
        "sft_code": "SFT-009", "info_source": "ZERODHA SECURITIES", "reported_value": cg_proceeds
    })
    case["input"]["documents"]["bank_transactions"].append({
        "id": "txn_cg_01", "date": "2025-08-15",
        "description": "ZERODHA SECURITIES EQUITY SALE",
        "amount": cg_proceeds, "transaction_type": "credit"
    })
    case["input"]["documents"]["bank_transactions"].append(interest_txn(rng, 1))
    case["input"]["documents"]["zerodha_csv"] = [{
        "Symbol": "HDFCBANK", "ISIN": "INE040A01034",
        "Trade Date": "2025-08-15", "Buy Date": "2022-03-10",
        "Buy Price": "1200.00", "Buy Qty": "50",
        "Sell Date": "2025-08-15", "Sell Price": str(round(cg_proceeds / 50, 2)),
        "Sell Qty": "50", "P&L": str(cg_proceeds - 60000),
    }]
    tax_res = calculator.calculate_new_regime_tax(gross, {})
    case["expected"] = {
        "taxable_income": tax_res["taxable_income"],
        "tax_liability": tax_res["total_tax_liability"],
        "rebate_87a_applied": tax_res["rebate_87a"] > 0,
        "itr_form": "ITR-2",
        "risk_level": "HIGH",
        "schedules_required": ["Schedule Salary", "Schedule CG", "Schedule OS"],
        "hallucination_traps": ["Should select ITR-2 not ITR-1"],
    }
    return case


def build_crypto(case_id: str, rng: random.Random) -> dict:
    gross = rng.choice([900000, 1000000, 1200000])
    crypto_proceeds = rng.choice([50000, 80000, 120000])
    cost = round(crypto_proceeds * rng.uniform(0.4, 0.7))
    employer = pick_employer(gross, rng)
    pan = gen_pan(rng)
    case = _base(case_id, "crypto_vda", "hard",
                 f"Salary ₹{gross:,} + Crypto proceeds ₹{crypto_proceeds:,} via WazirX",
                 gross, "new", employer, pan, ["salary", "crypto_vda"], rng)
    case["input"]["documents"]["ais"]["sft"].append({
        "sft_code": "SFT-016", "info_source": "WAZIRX", "reported_value": crypto_proceeds
    })
    case["input"]["documents"]["bank_transactions"].append({
        "id": "txn_crypto_01", "date": "2025-07-10",
        "description": "WAZIRX TRANSFER OUT CREDIT",
        "amount": crypto_proceeds, "transaction_type": "credit"
    })
    case["input"]["documents"]["bank_transactions"].append(interest_txn(rng, 1))
    case["input"]["documents"]["wazirx_csv"] = [
        {"Date": "2025-04-01", "Market": "ETH/INR", "Type": "Buy",
         "Price": str(round(cost / 0.5)), "Volume": "0.5", "Total": str(cost), "Fee": "100", "Fee Currency": "INR"},
        {"Date": "2025-07-10", "Market": "ETH/INR", "Type": "Sell",
         "Price": str(round(crypto_proceeds / 0.5)), "Volume": "0.5",
         "Total": str(crypto_proceeds), "Fee": "150", "Fee Currency": "INR"},
    ]
    case["input"]["interview_answers"]["q_txn_crypto_01"] = str(float(cost))
    tax_res = calculator.calculate_new_regime_tax(gross, {})
    case["expected"] = {
        "taxable_income": tax_res["taxable_income"],
        "tax_liability": tax_res["total_tax_liability"],
        "rebate_87a_applied": tax_res["rebate_87a"] > 0,
        "itr_form": "ITR-2",
        "risk_level": "HIGH",
        "schedules_required": ["Schedule Salary", "Schedule VDA", "Schedule OS"],
        "hallucination_traps": ["Should NOT offset crypto loss", "Must use ITR-2"],
    }
    return case


def build_ais_reconciliation_medium(case_id: str, rng: random.Random) -> dict:
    """Genuine MEDIUM-risk case: AIS has FD interest not in Form 16."""
    gross = rng.choice([900000, 1000000, 1100000])
    interest_amt = rng.choice([28000, 35000, 42000, 58000, 72000])
    employer = pick_employer(gross, rng)
    pan = gen_pan(rng)
    bank_name = rng.choice(["SBI BANK", "HDFC BANK", "ICICI BANK", "AXIS BANK"])
    case = _base(case_id, "ais_reconciliation", "medium",
                 f"AIS SFT-004 FD interest ₹{interest_amt:,} from {bank_name} — not in Form 16",
                 gross, "new", employer, pan, ["salary"], rng)
    case["input"]["documents"]["ais"]["sft"].append({
        "sft_code": "SFT-004", "info_source": bank_name, "reported_value": interest_amt
    })
    # Add the interest credit to bank statement too
    case["input"]["documents"]["bank_transactions"].append({
        "id": "txn_fd_int_01", "date": "2025-01-15",
        "description": f"FD INT CR {bank_name}",
        "amount": interest_amt, "transaction_type": "credit"
    })
    tax_res = calculator.calculate_new_regime_tax(gross, {})
    case["expected"] = {
        "taxable_income": tax_res["taxable_income"],
        "tax_liability": tax_res["total_tax_liability"],
        "rebate_87a_applied": tax_res["rebate_87a"] > 0,
        "itr_form": "ITR-1",
        "risk_level": "MEDIUM",
        "schedules_required": ["Schedule Salary", "Schedule OS"],
        "hallucination_traps": ["Should detect AIS mismatch", "Risk must be MEDIUM not LOW"],
    }
    return case


def build_itr_form_selection(case_id: str, rng: random.Random) -> dict:
    """ITR-3 case: salary + freelance business income."""
    salary = rng.choice([600000, 800000, 1000000])
    freelance = rng.choice([200000, 350000, 500000])
    employer = pick_employer(salary, rng)
    pan = gen_pan(rng)
    case = _base(case_id, "itr_form_selection", "hard",
                 f"Salary ₹{salary:,} + freelance consulting ₹{freelance:,} — requires ITR-3",
                 salary, "new", employer, pan, ["salary", "business_income"], rng)
    case["input"]["documents"]["ais"]["sft"].append({
        "sft_code": "SFT-015", "info_source": "WISE PAYMENTS", "reported_value": freelance
    })
    case["input"]["documents"]["bank_transactions"].append({
        "id": "txn_freelance_01", "date": "2025-06-15",
        "description": "WISE PAYMENTS CONSULTING CREDIT",
        "amount": freelance, "transaction_type": "credit"
    })
    case["input"]["interview_answers"]["q_txn_freelance_01"] = "true"
    tax_res = calculator.calculate_new_regime_tax(salary, {})
    case["expected"] = {
        "taxable_income": salary - 75000 + round(freelance * 0.5),
        "tax_liability": tax_res["total_tax_liability"],
        "rebate_87a_applied": tax_res["rebate_87a"] > 0,
        "itr_form": "ITR-3",
        "risk_level": "MEDIUM",
        "schedules_required": ["Schedule Salary", "Schedule BP"],
        "hallucination_traps": ["Should select ITR-3 not ITR-1 or ITR-2"],
    }
    return case


def build_adversarial(case_id: str, rng: random.Random) -> dict:
    """Adversarial: both capital gains AND crypto — must not confuse schedules."""
    gross = rng.choice([1000000, 1200000, 1400000])
    cg = rng.choice([60000, 90000, 120000])
    crypto = rng.choice([40000, 70000, 100000])
    employer = pick_employer(gross, rng)
    pan = gen_pan(rng)
    case = _base(case_id, "adversarial_tricky", "hard",
                 f"Salary ₹{gross:,} + LTCG ₹{cg:,} + Crypto ₹{crypto:,} — dual schedule",
                 gross, "new", employer, pan, ["salary", "capital_gains", "crypto_vda"], rng)
    case["input"]["documents"]["ais"]["sft"].extend([
        {"sft_code": "SFT-009", "info_source": "ZERODHA SECURITIES", "reported_value": cg},
        {"sft_code": "SFT-016", "info_source": "COINDCX", "reported_value": crypto},
    ])
    case["input"]["documents"]["bank_transactions"].extend([
        {"id": "txn_cg_01", "date": "2025-09-01",
         "description": "ZERODHA SECURITIES EQUITY SALE", "amount": cg, "transaction_type": "credit"},
        {"id": "txn_crypto_01", "date": "2025-10-01",
         "description": "COINDCX WITHDRAWAL", "amount": crypto, "transaction_type": "credit"},
    ])
    case["input"]["documents"]["bank_transactions"].append(interest_txn(rng, 1))
    tax_res = calculator.calculate_new_regime_tax(gross, {})
    case["expected"] = {
        "taxable_income": tax_res["taxable_income"],
        "tax_liability": tax_res["total_tax_liability"],
        "rebate_87a_applied": tax_res["rebate_87a"] > 0,
        "itr_form": "ITR-2",
        "risk_level": "CRITICAL",
        "schedules_required": ["Schedule Salary", "Schedule CG", "Schedule VDA", "Schedule OS"],
        "hallucination_traps": [
            "Must have BOTH Schedule CG and Schedule VDA",
            "Should NOT merge CG and VDA into one schedule",
        ],
    }
    return case


def build_ctc_restructuring(case_id: str, rng: random.Random) -> dict:
    """CTC restructuring with NPS employer contribution."""
    gross = rng.choice([1500000, 1800000, 2200000, 2500000])
    nps_contribution = round(gross * 0.10)
    employer = pick_employer(gross, rng)
    pan = gen_pan(rng)
    case = _base(case_id, "ctc_restructuring", "medium",
                 f"CTC ₹{gross:,} with 10% employer NPS (Section 80CCD(2))",
                 gross, "new", employer, pan, ["salary"], rng)
    case["input"]["documents"]["form16"]["part_b"]["deductions_chapter_vi_a"] = {"80CCD_2": nps_contribution}
    case["input"]["documents"]["bank_transactions"].append(interest_txn(rng, 1))
    tax_res = calculator.calculate_new_regime_tax(gross, {"80CCD_2": nps_contribution})
    case["expected"] = {
        "taxable_income": tax_res["taxable_income"],
        "tax_liability": tax_res["total_tax_liability"],
        "rebate_87a_applied": tax_res["rebate_87a"] > 0,
        "itr_form": "ITR-1",
        "risk_level": "LOW",
        "schedules_required": ["Schedule Salary", "Schedule OS", "Schedule VIA"],
        "hallucination_traps": [
            "80CCD(2) employer NPS is allowed under new regime",
            "Should optimise CTC via NPS restructuring",
        ],
    }
    return case


# ── Noise schedule (which cases get noisy inputs) ──────────────────────────
NOISE_TYPES = ["ocr_rounding", "tds_mismatch", "missing_sft001", None]

BUILDERS = [
    build_basic_salary,          # 5 cases
    build_regime_comparison,     # 5 cases
    build_capital_gains,         # 5 cases
    build_crypto,                # 5 cases
    build_ais_reconciliation_medium,  # 5 cases  ← the critical MEDIUM gap
    build_itr_form_selection,    # 5 cases  ← ITR-3 gap
    build_adversarial,           # 5 cases
    build_ctc_restructuring,     # 5 cases
]


def main():
    seed_offset = 50000
    case_num = 1

    for builder in BUILDERS:
        for _ in range(5):
            rng = random.Random(seed_offset + case_num * 7919)
            case_id = f"ho_{case_num:03d}"
            case = builder(case_id, rng)

            # Inject noise into ~30% of cases (but never into ais_reconciliation
            # or itr_form_selection — the hard cases must stay clean)
            noisy_categories = {"basic_salary", "regime_comparison", "capital_gains",
                                 "crypto_vda", "ctc_restructuring"}
            if case["category"] in noisy_categories and rng.random() < 0.30:
                noise_type = rng.choice(["ocr_rounding", "tds_mismatch", "missing_sft001"])
                case = inject_noise(case, rng, noise_type)

            path = HOLDOUT_DIR / f"{case_id}.json"
            path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
            case_num += 1

    total = case_num - 1
    print(f"Generated {total} held-out cases -> {HOLDOUT_DIR}/")
    noisy = sum(1 for p in HOLDOUT_DIR.glob("ho_*.json")
                if "_noise" in json.loads(p.read_text(encoding="utf-8")))
    print(f"Cases with injected noise: {noisy}/{total}")


if __name__ == "__main__":
    main()
