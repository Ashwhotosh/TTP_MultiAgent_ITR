"""
generate_training_data.py -- Build the 400+ row training CSV.

This script generates a comprehensive labeled dataset including:
    - Major brands (Zomato, Swiggy, Amazon, etc.)
    - Hinglish vendors (Aman Juicewala, Sharma Sweets, etc.)
    - Noisy bank statement formats (WDL TFR, UTR numbers, etc.)
    - Multiple income sources, deductions, expenses
"""
from __future__ import annotations
import csv
import random
from pathlib import Path

random.seed(42)


SALARY_EMPLOYERS = [
    "INFOSYS BPM LTD", "TCS LIMITED", "WIPRO LTD", "ACCENTURE",
    "COGNIZANT", "HCL TECHNOLOGIES", "TECH MAHINDRA", "CAPGEMINI",
    "MICROSOFT INDIA", "GOOGLE INDIA", "AMAZON DEVELOPMENT",
    "FLIPKART", "PHONEPE", "PAYTM", "RAZORPAY", "SWIGGY",
    "ZOMATO TECH", "OLA CABS", "OYO ROOMS", "MAKEMYTRIP",
    "ADITYA BIRLA", "RELIANCE INDUSTRIES", "TATA STEEL", "L&T",
    "BAJAJ FINSERV", "HDFC LIFE", "ICICI BANK", "SBI",
    "DELOITTE INDIA", "PWC INDIA", "EY GLOBAL", "KPMG", "IBM INDIA",
]

CRYPTO_EXCHANGES = [
    "WAZIRX", "COINDCX", "COINSWITCH", "ZEBPAY", "BITBNS",
    "MUDREX", "PI42", "GIOTTUS", "UNOCOIN", "KUCOIN",
    "BINANCE", "BUYUCOIN", "VAULD", "CRYPTOPRO",
]

BROKERS = [
    "ZERODHA BROKING", "GROWW", "UPSTOX", "ANGEL BROKING",
    "ICICI DIRECT", "HDFC SECURITIES", "KOTAK SECURITIES",
    "MOTILAL OSWAL", "5PAISA", "KITE ZERODHA", "PAYTM MONEY",
    "DHAN BROKING", "INDMONEY",
]

MUTUAL_FUNDS = [
    "MIRAE ASSET MF", "HDFC AMC", "ICICI PRUDENTIAL MF",
    "AXIS MUTUAL FUND", "SBI MUTUAL FUND", "NIPPON INDIA MF",
    "KOTAK MAHINDRA MF", "DSP MUTUAL FUND", "PARAG PARIKH",
    "QUANT MF",
]

FREELANCE_REMITTERS = [
    "UPWORK GLOBAL INC", "FIVERR INTERNATIONAL", "TOPTAL",
    "FREELANCER COM", "WISE PAYMENTS", "PAYPAL", "PAYONEER",
    "REMITLY", "STRIPE PAYMENTS", "GUSTO PAYROLL",
    "DEUTSCHE BANK CLIENT USD", "JPMORGAN CHASE USD",
    "BANK OF AMERICA REMITTANCE", "WESTERN UNION",
]

INSURANCE_COMPANIES = [
    "LIC OF INDIA", "HDFC LIFE INSURANCE", "ICICI PRUDENTIAL LIFE",
    "STAR HEALTH INSURANCE", "MAX BUPA HEALTH", "RELIANCE GENERAL",
    "BAJAJ ALLIANZ", "TATA AIG", "NIVA BUPA", "MANIPAL CIGNA",
    "POLICYBAZAAR LIC", "ADITYA BIRLA HEALTH",
]

LOAN_BANKS = [
    "HDFC BANK", "SBI", "ICICI BANK", "AXIS BANK", "KOTAK",
    "BAJAJ FINSERV", "TATA CAPITAL", "INDIABULLS",
    "PNB HOUSING", "LIC HOUSING FINANCE", "HOME CREDIT",
]
LOAN_TYPES = [
    "HOUSING LOAN", "HOME LOAN", "CAR LOAN", "AUTO LOAN",
    "PERSONAL LOAN", "EDUCATION LOAN", "TWO WHEELER LOAN",
]

INVESTMENT_INSTRUMENTS = [
    "PPF DEPOSIT", "NPS TRUST CONTRIBUTION", "VOLUNTARY NPS",
    "ELSS SIP HDFC", "ELSS SIP MIRAE", "ELSS SIP AXIS",
    "SUKANYA SAMRIDHI", "NSC PURCHASE", "TAX SAVER FD",
    "ULIP PREMIUM",
]

HINGLISH_VENDORS = [
    "AMAN JUICEWALA", "SHARMA SWEET MART", "GUPTA KIRANA STORE",
    "PATEL GENERAL STORE", "SINGH DHABA", "KUMAR CLOTH HOUSE",
    "MISHRA CHAI WALA", "BANSAL TEA CORNER", "RAVI BHAJI WALA",
    "MAHALAXMI PROVISION", "SAI BABA STORES", "SHRI GANESH SUPER MARKET",
    "JAI MAHARASHTRA SWEET HOUSE", "BALAJI VEG", "KAKA HALWAI",
    "CHACHA JI DHABA", "BHAIYA JI PAN SHOP", "RAMESH MEDICAL STORE",
    "MAA TARA CYCLE STORES", "SHIVA SWEETS AND NAMKEEN",
    "ANJALI BEAUTY PARLOUR", "RAJESH SAREE EMPORIUM",
    "MAMA JI KE PAKODE", "SARDAR JI DHABA", "HEERA LAL JEWELLERS",
    "PARAS JEWELS", "MAA AMBE PROVISION", "RAM DARSHAN VEG RESTAURANT",
    "AGRAWAL SARI CENTER", "BANSAL DRY FRUITS", "VERMA HARDWARE",
    "DEEPAK PAN SHOP", "POOJA CYBER CAFE", "TRIVEDI ELECTRONICS",
    "KRISHNA MILK DAIRY", "RADHE RADHE GROCERY", "OM SAI MEDICAL",
    "JAI HIND CLOTH STORE", "BABA RAMDEV ATTA CHAKKI", "SHREE NATH SAREES",
    "RUKMINI MART", "AGGARWAL SWEETS", "PRINCE DRY CLEANERS",
    "MOHAN LAL TAILORS", "BIKANER MISTHAN BHANDAR", "RAJWADI THALI",
    "VAISHNO DEVI BHOJANALAYA", "ANNAPURNA RESTAURANT", "GARDEN VIEW DHABA",
    "AAPKA APNA STORE", "GANGA BAKERY", "YAMUNA SWEETS",
    "JAGGI JEWELLERS", "BABLU AUTO REPAIR", "PRINCE GIFT GALLERY",
    "GUDDI BEAUTY PARLOUR", "RANI CLOTH HOUSE", "DOLLY FASHION POINT",
    "SABZI MANDI BHAIYA", "DOODHWALA MILK DELIVERY",
    "AAJ KA SPECIAL DHABA", "GHAR KA SWAAD CATERERS",
    "MEERA BAI CLOTH MART", "TULSI VEG SHOP", "RAJU AUTO STAND",
    "MUNNI BEN SWEET CORNER", "SETHIA FOOTWEAR", "CHANDU TEA STALL",
    "GOLU DRY FRUITS", "PINKY SAREE HOUSE", "MITTAL TIFFIN SERVICE",
    "MONU TYRES AND PUNCTURE", "SHRI HARI MEDICAL HALL",
    "JINDAL CONFECTIONERY", "DURGA PUJA CATERERS", "GANPATI SWEET HOUSE",
    "PURI PROVISION STORE", "BANARAS PAAN BHANDAR",
    "GUJRATI THALI HOUSE", "ANDHRA MESS SOUTH INDIAN",
    "BENGALI MISHTI DOI", "MARWARI BHOJANALAYA",
]

FOOD_BRANDS = [
    "ZOMATO", "SWIGGY", "DUNZO", "MCDONALDS", "DOMINOS",
    "KFC", "PIZZA HUT", "STARBUCKS", "CCD", "BARISTA",
    "SUBWAY", "BURGER KING", "FAASOS", "BOX8",
]
SHOPPING_BRANDS = [
    "AMAZON", "AMZN MKTP IN", "FLIPKART", "MYNTRA",
    "NYKAA", "AJIO", "MEESHO", "FIRSTCRY", "TATACLIQ",
    "CROMA", "RELIANCE DIGITAL", "VIJAY SALES",
]
GROCERY_BRANDS = [
    "BIGBASKET", "BLINKIT", "ZEPTO", "INSTAMART",
    "DUNZO DAILY", "JIOMART", "MORE SUPERMARKET",
    "DMART READY", "SPENCERS", "RELIANCE FRESH",
]
TRAVEL_BRANDS = [
    "UBER", "OLA CABS", "IRCTC", "INDIGO", "AIR INDIA",
    "MAKEMYTRIP", "GOIBIBO", "EASEMYTRIP", "YATRA",
    "RAPIDO", "BLUE DART",
]
ENTERTAINMENT = [
    "NETFLIX", "DISNEY PLUS HOTSTAR", "AMAZON PRIME",
    "BOOKMYSHOW", "SPOTIFY", "YOUTUBE PREMIUM",
    "JIO CINEMA", "SONY LIV",
]
UTILITIES = [
    "PAYTM ELECTRICITY", "BESCOM", "MSEB", "AIRTEL BROADBAND",
    "JIO FIBER", "ACT FIBERNET", "BSNL", "TATA POWER",
    "MAHANAGAR GAS", "INDANE GAS",
]

NOISE_PREFIXES = [
    "WDL TFR ", "WDL TFR NEFT-", "DEP TFR ",
    "ACH/DR/", "POS PRCH AT ", "UPI/DR/",
    "UPI/CR/", "NEFT/CR/", "NEFT/DR/", "IMPS/CR/",
    "RTGS/DR/", "", "", "",
]
NOISE_SUFFIXES = [
    "", "", " 04042025", " UTR123456789", " REF-CR-2025-12345",
    " /MUMBAI", " AT NASIK", " /BANGALORE TERMINAL 12",
    " /paym00987654321", " /TXN-REF-7654321",
]


def make_noisy(clean_desc: str) -> str:
    prefix = random.choice(NOISE_PREFIXES)
    suffix = random.choice(NOISE_SUFFIXES)
    if random.random() < 0.3:
        prefix = "WDL TFR UPI/DR/" + str(random.randint(10000000, 99999999)) + "/"
        suffix = f"/paym{random.randint(1000000000, 9999999999)} AT LOC {random.randint(100, 9999)}"
    return f"{prefix}{clean_desc}{suffix}"


def generate():
    rows = []

    # SALARY_INCOME (30)
    for emp in SALARY_EMPLOYERS[:30]:
        rows.append([make_noisy(f"SALARY {emp}"), "SALARY_INCOME", "salary"])

    # FREELANCE_INCOME (25)
    for remitter in random.sample(FREELANCE_REMITTERS * 3, 25):
        rows.append([make_noisy(f"{remitter} USD REMITTANCE"), "FREELANCE_INCOME", "foreign_remittance"])

    # CRYPTO_TRANSACTION (30)
    for exch in random.sample(CRYPTO_EXCHANGES * 3, 30):
        direction = random.choice([
            "CRYPTO BUY", "CRYPTO SELL", "BTC PURCHASE", "ETH SALE", "USDT TRANSFER",
        ])
        rows.append([make_noisy(f"{exch} {direction}"), "CRYPTO_TRANSACTION", "VDA"])

    # CAPITAL_MARKET (30)
    for _ in range(20):
        broker = random.choice(BROKERS)
        action = random.choice(["EQUITY BUY", "EQUITY SELL", "STOCK PURCHASE", "SHARE SALE"])
        rows.append([make_noisy(f"{broker} {action}"), "CAPITAL_MARKET", "Schedule_CG"])
    for _ in range(10):
        mf = random.choice(MUTUAL_FUNDS)
        action = random.choice(["MF REDEMPTION", "SIP PURCHASE", "MUTUAL FUND REDEEM"])
        rows.append([make_noisy(f"{mf} {action}"), "CAPITAL_MARKET", "Schedule_CG"])

    # INTEREST_INCOME (25)
    interest_descs = [
        "SBI SAVINGS INTEREST Q1", "HDFC FD INTEREST Q2", "AXIS BANK FD INT",
        "ICICI SAVINGS INT MAR", "KOTAK FD MATURITY INT", "PNB RD INTEREST",
        "FEDERAL BANK FD INT", "YES BANK SAVINGS INT", "INDUSIND FD INT",
        "INT CR HDFC SAVINGS Q3", "INTEREST ON FIXED DEPOSIT",
        "RECURRING DEPOSIT INTEREST", "FD INT AXIS Q4",
        "QUARTERLY SAVINGS INTEREST", "SBI RD INTEREST MATURITY",
    ] * 2
    for desc in interest_descs[:25]:
        rows.append([make_noisy(desc), "INTEREST_INCOME", "Schedule_OS"])

    # DIVIDEND_INCOME (15)
    dividend_companies = [
        "INFOSYS", "TCS", "RELIANCE", "HDFC BANK",
        "ITC LIMITED", "HUL", "ASIAN PAINTS",
        "BAJAJ FINANCE", "MARUTI SUZUKI", "BHARTI AIRTEL",
    ]
    for co in (dividend_companies + dividend_companies[:5]):
        rows.append([make_noisy(f"DIVIDEND {co} LTD"), "DIVIDEND_INCOME", "Schedule_OS"])

    # RENT_PAID (20)
    landlords = [
        "PRIYA SHARMA LANDLORD", "RAMESH KUMAR PROPERTIES",
        "RAJESH GUPTA RENTAL", "AGARWAL HOUSING",
        "MEHTA RESIDENCY OWNER", "RAJ KAPOOR LANDLORD",
        "SUNITA AUNTY RENT", "MR SHARMA HOUSE OWNER",
        "PATEL APARTMENT RENTAL", "JOSHI NIWAS RENT",
        "PROPERTY RENTAL MUMBAI", "FLAT RENT HSR LAYOUT",
        "HOUSE RENT PAYMENT JUNE", "MONTHLY RENT SHARMA JI",
        "RENT FLAT DOMBIVALI", "RENT KORAMANGALA APARTMENT",
        "LANDLORD MR VERMA", "MS SINGH RENTAL INCOME",
        "GULSHAN RAI RENT", "MISHRA PG RENT",
    ]
    for ll in landlords:
        rows.append([make_noisy(f"RENT {ll}"), "RENT_PAID", "deduction_HRA_80GG"])

    # INSURANCE_PREMIUM (20)
    insurance_descs = []
    for ins in (INSURANCE_COMPANIES + INSURANCE_COMPANIES[:8]):
        action = random.choice(["PREMIUM", "POLICY PAYMENT", "ANNUAL PREMIUM", "RENEWAL"])
        insurance_descs.append(f"{ins} {action}")
    for desc in insurance_descs[:20]:
        rows.append([make_noisy(desc), "INSURANCE_PREMIUM", "deduction_80D_80C"])

    # LOAN_EMI (25)
    for _ in range(25):
        bank = random.choice(LOAN_BANKS)
        loan = random.choice(LOAN_TYPES)
        rows.append([make_noisy(f"{bank} {loan} EMI"), "LOAN_EMI", "deduction_24b_80C"])

    # INVESTMENT_TAX_SAVING (20)
    for _ in range(20):
        instr = random.choice(INVESTMENT_INSTRUMENTS)
        rows.append([make_noisy(instr), "INVESTMENT_TAX_SAVING", "deduction_80C_80CCD"])

    # REGULAR_EXPENSE -- Hinglish (80)
    for vendor in HINGLISH_VENDORS[:80]:
        rows.append([make_noisy(vendor), "REGULAR_EXPENSE", "none"])

    # REGULAR_EXPENSE -- Big brands (40)
    all_brands = (
        FOOD_BRANDS + SHOPPING_BRANDS + GROCERY_BRANDS
        + TRAVEL_BRANDS + ENTERTAINMENT + UTILITIES
    )
    for brand in random.sample(all_brands * 3, 40):
        rows.append([make_noisy(brand), "REGULAR_EXPENSE", "none"])

    # TRANSFER (40)
    transfer_descs = [
        "UPI TRANSFER TO RAHUL VERMA", "P2P PAYMENT TO FRIEND",
        "SELF TRANSFER TO SAVINGS", "ATM WITHDRAWAL HDFC",
        "CASH WITHDRAWAL SBI", "TRANSFER TO BROTHER ACCOUNT",
        "GIFT TO PARENTS", "REFUND CR FROM AMAZON",
        "REVERSAL UPI TRANSACTION", "INTERNAL ACCOUNT TRANSFER",
        "TRANSFER TO PPF ACCOUNT", "MOM TRANSFER",
        "DAD ACCOUNT TRANSFER", "WIFE ACCOUNT TRANSFER",
        "HUSBAND TRANSFER", "SISTER ACCOUNT",
        "FRIEND LOAN REPAYMENT", "BORROWED MONEY RETURN",
        "PERSONAL P2P", "EMERGENCY TRANSFER",
    ] * 2
    for desc in transfer_descs[:40]:
        rows.append([make_noisy(desc), "TRANSFER", "none"])

    random.shuffle(rows)

    out_path = Path("data/training/transaction_labels_v2.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["description", "label", "tax_relevance"])
        writer.writerows(rows)

    print(f"Generated {len(rows)} labeled transactions -> {out_path}")

    from collections import Counter
    dist = Counter(r[1] for r in rows)
    print("\nLabel distribution:")
    for label, count in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")


if __name__ == "__main__":
    generate()
