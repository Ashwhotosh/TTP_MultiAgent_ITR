"""
Enrich benchmark cases with realistic data.
- Unique PAN per case
- Realistic employer name per salary bracket
- 12 monthly salary credits (replacing single credit)
- ~400-500 background bank transactions per case
- Fix generic descriptions

Run: python benchmarks/indian_tax_bench/enrich_cases.py
"""
import json
import random
import string
from pathlib import Path
from datetime import date, timedelta

CASES_DIR = Path(__file__).parent / "cases"

# ── Employer pools by salary bracket ────────────────────────────────────────
EMPLOYERS = {
    "junior":  ["COGNIZANT", "HCL TECHNOLOGIES", "MPHASIS", "HEXAWARE", "MASTEK",
                 "KPIT TECHNOLOGIES", "SONATA SOFTWARE", "ZENSAR TECHNOLOGIES"],
    "mid":     ["TATA CONSULTANCY SERVICES", "INFOSYS", "WIPRO", "ACCENTURE", "CAPGEMINI",
                 "L&T TECHNOLOGY SERVICES", "MINDTREE", "BIRLASOFT", "PERSISTENT SYSTEMS"],
    "senior":  ["AMAZON INDIA", "MICROSOFT INDIA", "FLIPKART", "RAZORPAY", "PHONEPE",
                 "SWIGGY", "ZOMATO", "PAYTM", "MEESHO", "OLA CABS"],
    "exec":    ["GOLDMAN SACHS INDIA", "JP MORGAN SERVICES INDIA", "HDFC BANK",
                 "ICICI BANK", "MORGAN STANLEY", "DEUTSCHE BANK", "BARCLAYS", "BLACKROCK"],
}

def employer_pool(gross_salary: float) -> list[str]:
    if gross_salary < 600_000:
        return EMPLOYERS["junior"]
    elif gross_salary < 1_800_000:
        return EMPLOYERS["mid"]
    elif gross_salary < 4_000_000:
        return EMPLOYERS["senior"]
    else:
        return EMPLOYERS["exec"]

def pick_employer(gross_salary: float, rng: random.Random) -> str:
    return rng.choice(employer_pool(gross_salary))

# ── PAN generation ───────────────────────────────────────────────────────────
def gen_pan(rng: random.Random) -> str:
    letters = string.ascii_uppercase
    part1 = "".join(rng.choice(letters) for _ in range(5))
    part2 = "".join(str(rng.randint(0, 9)) for _ in range(4))
    part3 = rng.choice(letters)
    return part1 + part2 + part3

# ── Background transaction generator ─────────────────────────────────────────
FY_START = date(2024, 4, 1)
FY_END   = date(2025, 3, 31)

def rand_date(rng: random.Random, start: date = FY_START, end: date = FY_END) -> str:
    delta = (end - start).days
    return (start + timedelta(days=rng.randint(0, delta))).strftime("%Y-%m-%d")

def monthly_date(month_offset: int) -> str:
    """Returns 1st–5th of each FY month (salary credit day)."""
    month = 4 + month_offset
    year  = 2024 + (month > 12)
    month = month if month <= 12 else month - 12
    day   = 1 if month_offset % 3 == 0 else 3
    return date(year, month, day).strftime("%Y-%m-%d")

def make_background_transactions(rng: random.Random, net_monthly: float, txn_id_start: int) -> list[dict]:
    txns = []
    tid  = txn_id_start

    def add(desc, amount, ttype, d=None):
        nonlocal tid
        txns.append({
            "id":               f"txn_{tid:04d}",
            "date":             d or rand_date(rng),
            "description":      desc,
            "amount":           round(amount, 2),
            "transaction_type": ttype,
        })
        tid += 1

    # Rent: monthly
    rent = rng.choice([12000, 15000, 18000, 20000, 22000, 25000, 30000])
    for mo in range(12):
        add(rng.choice(["NEFT/LANDLORD RENT", "UPI/DR/OWNER RENT PAYMENT",
                         "IMPS/HOUSE RENT", "UPI/HOUSING SOCIETY RENT"]),
            rent, "debit",
            monthly_date(mo))

    # EMI (home or car loan)
    if net_monthly > 60_000:
        emi = rng.choice([18500, 22300, 27800, 35000, 48000])
        emi_desc = rng.choice(["HDFC HOME LOAN EMI", "SBI HOME LOAN EMI",
                                "ICICI HOME LOAN EMI", "AXIS BANK LOAN EMI"])
        for mo in range(12):
            add(emi_desc, emi, "debit", monthly_date(mo))

    # SIP — mutual fund
    sip_amt = rng.choice([2000, 3000, 5000, 7500, 10000, 15000])
    sip_fund = rng.choice(["AXIS BLUECHIP FUND SIP", "MIRAE ASSET LARGE CAP SIP",
                            "PARAG PARIKH FLEXI CAP SIP", "HDFC MIDCAP OPPORTUNITIES SIP",
                            "NIPPON INDIA SMALL CAP SIP", "SBI EQUITY HYBRID SIP"])
    for mo in range(12):
        add(sip_fund, sip_amt, "debit", monthly_date(mo))

    # Utility: electricity
    for mo in range(12):
        add(rng.choice(["BESCOM ELECTRICITY BILL", "MSEDCL ELECTRICITY BILL",
                         "TATA POWER ELECTRICITY", "BSES RAJDHANI BILL"]),
            rng.randint(800, 4500), "debit", rand_date(rng))

    # Internet
    for mo in range(12):
        add(rng.choice(["JIOFIBER BROADBAND", "ACT FIBERNET BILL",
                         "AIRTEL BROADBAND BILL", "HATHWAY BROADBAND"]),
            rng.randint(599, 1499), "debit", rand_date(rng))

    # Mobile recharge
    for mo in range(12):
        add(rng.choice(["JIO RECHARGE", "AIRTEL RECHARGE", "BSNL RECHARGE",
                         "VI MOBILE RECHARGE"]),
            rng.randint(239, 899), "debit", rand_date(rng))

    # OTT subscriptions
    for ott, price in [("NETFLIX SUBSCRIPTION", 649), ("HOTSTAR DISNEY+", 299),
                        ("SPOTIFY PREMIUM", 119), ("AMAZON PRIME VIDEO", 179),
                        ("YOUTUBE PREMIUM", 189)]:
        if rng.random() > 0.4:
            for mo in range(12):
                add(ott, price, "debit", rand_date(rng))

    # Grocery / supermarket (weekly)
    grocery_stores = ["DMART RETAIL", "BIGBASKET ORDER", "RELIANCE SMART BAZAAR",
                       "MORE MEGASTORE", "SPENCERS RETAIL", "NATURE BASKET"]
    for _ in range(52):
        add(rng.choice(grocery_stores), rng.randint(400, 4500), "debit", rand_date(rng))

    # Food delivery (2–3x per week)
    food_apps = ["SWIGGY ORDER", "ZOMATO DELIVERY", "DUNZO DELIVERY"]
    for _ in range(120):
        add(rng.choice(food_apps), rng.randint(150, 900), "debit", rand_date(rng))

    # UPI generic (petrol, medicines, misc)
    upi_descs = [
        "UPI/DR/INDIANOIL PETROL",
        "UPI/DR/HP PETROL PUMP",
        "UPI/DR/MEDPLUS PHARMACY",
        "UPI/DR/APOLLO PHARMACY",
        "UPI/GPAY/MISC PAYMENT",
        "UPI/PHONEPE/MISC",
        "UPI/DR/HALDIRAM SNACKS",
        "UPI/DR/STARBUCKS COFFEE",
        "UPI/DR/CCD COFFEE",
        "UPI/DR/DECATHLON SPORTS",
        "UPI/DR/LIFESTYLE FASHION",
        "UPI/DR/LENSKART ORDER",
        "PAYTM/FASTAG RECHARGE",
        "UPI/DR/IXIGO TRAVEL",
        "UPI/DR/MAKEMYTRIP",
    ]
    for _ in range(80):
        add(rng.choice(upi_descs), rng.randint(100, 8000), "debit", rand_date(rng))

    # ATM withdrawals
    for _ in range(18):
        add("ATM CASH WITHDRAWAL", rng.choice([2000, 3000, 5000, 10000]), "debit", rand_date(rng))

    # Credit card bill
    for mo in range(12):
        add(rng.choice(["HDFC CREDIT CARD BILL", "SBI CREDIT CARD PAYMENT",
                         "ICICI CREDIT CARD BILL", "AXIS BANK CREDIT CARD"]),
            rng.randint(8000, 80000), "debit", rand_date(rng))

    # Insurance premiums (quarterly)
    for _ in range(4):
        add(rng.choice(["LIC PREMIUM PAYMENT", "HDFC LIFE INSURANCE PREMIUM",
                         "MAX BUPA HEALTH PREMIUM", "STAR HEALTH PREMIUM"]),
            rng.randint(3500, 18000), "debit", rand_date(rng))

    # Small cashbacks / rewards (non-income, no Schedule OS trigger)
    for _ in range(6):
        add(rng.choice(["CASHBACK CREDIT CARD REWARDS", "GPAY SCRATCH CARD CASHBACK",
                         "PAYTM CASHBACK CREDIT", "LOYALTY POINTS REDEEMED"]),
            rng.randint(10, 250), "credit", rand_date(rng))

    return txns

def make_salary_credits(employer: str, gross_salary: float, rng: random.Random, txn_id_start: int) -> list[dict]:
    monthly_gross = round(gross_salary / 12)
    # Simulate TDS: rough estimate
    tds_per_month = max(0, round(monthly_gross * rng.uniform(0.05, 0.18)))
    net = monthly_gross - tds_per_month
    txns = []
    for mo in range(12):
        txns.append({
            "id":               f"txn_sal_{txn_id_start + mo:04d}",
            "date":             monthly_date(mo),
            "description":      f"SALARY CREDIT {employer}",
            "amount":           round(net + rng.randint(-500, 500), 2),
            "transaction_type": "credit",
        })
    return txns

# ── Description fixer ────────────────────────────────────────────────────────
GENERIC_RE = "Generic AIS mismatch case"

AIS_DESCRIPTIONS = [
    "AIS shows TDS-004 FD interest {v:,} not reflected in Form 16 — reconciliation needed",
    "AIS SFT-004 reports bank interest ₹{v:,}; not declared in ITR — Schedule OS gap",
    "Employer TDS matches Form 16 but AIS carries additional SFT entry of ₹{v:,}",
    "Bank FD interest ₹{v:,} appears in AIS; employee missed Schedule OS declaration",
    "AIS mismatch: reported interest income ₹{v:,} by bank, absent from Form 16 Part B",
    "SFT-004 savings/FD interest ₹{v:,} in AIS — potential notice trigger if undeclared",
    "AIS TDS credit ₹{v:,} from bank FD; filer must reconcile before filing ITR",
    "Undeclared bank interest ₹{v:,} per AIS SFT data — high reconciliation risk",
]

def fix_description(case: dict, rng: random.Random) -> str:
    desc = case.get("description", "")
    if not desc.startswith(GENERIC_RE):
        return desc
    # Pull the SFT value for a richer description
    sfts = case["input"]["documents"]["ais"]["sft"]
    non_salary = [s for s in sfts if s["sft_code"] != "SFT-001"]
    if non_salary:
        val = non_salary[0]["reported_value"]
        tmpl = rng.choice(AIS_DESCRIPTIONS)
        return tmpl.format(v=int(val))
    return desc

# ── Main enrichment logic ─────────────────────────────────────────────────────
def enrich(path: Path) -> None:
    with open(path, "r", encoding="utf-8") as f:
        case = json.load(f)

    case_num = int(path.stem.split("_")[1])
    rng = random.Random(case_num * 7919)  # deterministic seed per case

    docs = case["input"]["documents"]
    form16 = docs.get("form16", {})
    ais    = docs.get("ais", {})

    gross_salary = form16.get("part_a", {}).get("gross_salary", 1_000_000)

    # 1. New employer
    employer = pick_employer(gross_salary, rng)
    form16["employer_name"] = employer
    for sft in ais.get("sft", []):
        if sft.get("sft_code") == "SFT-001":
            sft["info_source"] = employer

    # 2. New PAN
    ais["pan"] = gen_pan(rng)

    # 3. Replace salary bank credits with 12 monthly ones.
    # Keep ONLY tax-relevant non-salary credits (Zerodha, WazirX, FD interest, etc.)
    # so the script is idempotent — drop all generic lifestyle transactions.
    TAX_RELEVANT_KEYWORDS = ["ZERODHA", "WAZIRX", "FD INTEREST", "DIVIDEND", "RENTAL INCOME",
                              "FREELANCE", "PPFAS", "EQUITY SALE", "CRYPTO", "VDA", "TRANSFER OUT"]
    existing_txns = docs.get("bank_transactions", [])
    non_salary_txns = [
        t for t in existing_txns
        if ("SALARY" not in t.get("description", "").upper())
        and any(kw in t.get("description", "").upper() for kw in TAX_RELEVANT_KEYWORDS)
    ]
    # Update descriptions that reference old employer name
    for t in non_salary_txns:
        for old_emp in list(EMPLOYERS["junior"]) + list(EMPLOYERS["mid"]) + list(EMPLOYERS["senior"]) + list(EMPLOYERS["exec"]) + ["TECHCORP"]:
            t["description"] = t["description"].replace(old_emp, employer)

    salary_txns = make_salary_credits(employer, gross_salary, rng, txn_id_start=1)

    # 4. Background transactions
    net_monthly = round(gross_salary / 12 * 0.80)
    bg_txns = make_background_transactions(rng, net_monthly, txn_id_start=100)

    docs["bank_transactions"] = salary_txns + non_salary_txns + bg_txns

    # 5. Fix description
    case["description"] = fix_description(case, rng)

    # 6. Data-honesty invariant: if Schedule OS is expected, the bank statement
    #    must contain a real interest credit so the AuditorAgent can infer it
    #    from a genuine signal rather than a blanket heuristic.
    expected_schedules = case.get("expected", {}).get("schedules_required", [])
    has_interest_credit = any(
        kw in t.get("description", "").upper()
        for t in docs["bank_transactions"]
        for kw in ["INT CR", "FD INT", "INTEREST", "SB INT"]
        if t.get("transaction_type") == "credit"
    )
    if "Schedule OS" in expected_schedules and not has_interest_credit:
        interest_banks = ["SBI SAVINGS INT CR", "HDFC BANK FD INT CR",
                          "ICICI BANK SB INT CR", "AXIS BANK INT CR"]
        docs["bank_transactions"].append({
            "id":               f"txn_int_{case_num:04d}",
            "date":             rand_date(rng, date(2024, 10, 1), date(2025, 3, 31)),
            "description":      rng.choice(interest_banks),
            "amount":           rng.randint(800, 4200),
            "transaction_type": "credit",
        })

    # 7. Write back
    with open(path, "w", encoding="utf-8") as f:
        json.dump(case, f, indent=2, ensure_ascii=False)

    total = len(docs["bank_transactions"])
    os_signal = "[INT]" if "Schedule OS" in expected_schedules else ""
    print(f"  {path.name}: employer={employer!r:40s} pan={ais['pan']}  txns={total} {os_signal}")


if __name__ == "__main__":
    cases = sorted(CASES_DIR.glob("tc_*.json"))
    print(f"Enriching {len(cases)} cases...\n")
    for p in cases:
        enrich(p)
    print(f"\nDone. {len(cases)} cases updated.")
