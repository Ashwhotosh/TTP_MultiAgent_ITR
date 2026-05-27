# Week 1: Foundation — Parsers, Tools, and AIS Reconciliation

## Goal
By end of week 1, you can run:
```bash
python -m agents.orchestrator --bank data/synthetic/sample_bank_statement.csv --ais data/synthetic/sample_ais.json --form16 data/synthetic/sample_form16.json
```
And get a JSON report showing: reconciled income from all 3 sources, flagged discrepancies, anomaly classifications, and a data-driven risk score.

---

## Task 1.1: Migrate Calculator from v2 (Day 1 morning)

**File**: `tools/calculator.py`
**Source**: Copy from `../FinITR-AI-v2/components/05_calculator/calculator.py`

1. Copy the entire `CalculatorTool` class from v2
2. Keep ALL existing methods: `calculate()`, `calculate_new_regime_tax()`, `calculate_ctc_restructure()`, the safe AST evaluator, slab tables, marginal relief logic
3. ADD a new method `calculate_old_regime_tax()`:

```python
def calculate_old_regime_tax(self, gross_salary: float, deductions: dict) -> dict:
    """
    Old Regime tax calculation.
    
    Args:
        gross_salary: Total gross salary
        deductions: {
            "80C": float,      # max 150000 (shared with 80CCC, 80CCD(1))
            "80CCD_1B": float, # max 50000
            "80CCD_2": float,  # max 10% of basic (14% for central govt)
            "80D": float,      # max 25000 (50000 for senior)
            "80E": float,      # no limit (education loan interest)
            "80G": float,      # variable
            "80TTA": float,    # max 10000
            "24b": float,      # max 200000 (home loan interest)
            "HRA": float,      # computed via _compute_hra_exemption()
            "LTA": float,      # actual claim
        }
    
    Returns: same shape as calculate_new_regime_tax() for easy comparison
    """
```

4. ADD `_compute_hra_exemption()`:
```python
def _compute_hra_exemption(self, basic_salary: float, hra_received: float, 
                            rent_paid: float, metro: bool = True) -> float:
    """HRA exemption = min of:
    1. Actual HRA received
    2. 50% of basic (metro) or 40% (non-metro)
    3. Rent paid - 10% of basic
    """
```

5. Old Regime slabs (FY 25-26):
```
0 - 2,50,000:      0%
2,50,001 - 5,00,000: 5%
5,00,001 - 10,00,000: 20%
10,00,001+:          30%
Standard deduction: 50,000
87A rebate: up to 5,00,000 taxable income, max 12,500
```

**Test**:
```bash
python -c "
from tools.calculator import CalculatorTool
calc = CalculatorTool()
# New regime test (should match v2 exactly)
r = calc.calculate_new_regime_tax(1500000)
print(f'New regime tax on 15L: {r[\"total_tax_liability\"]:,.0f}')
assert abs(r['total_tax_liability'] - 109200) < 100, 'New regime mismatch!'

# Old regime test
r2 = calc.calculate_old_regime_tax(1500000, {'80C': 150000, '80D': 25000, 'HRA': 150000})
print(f'Old regime tax on 15L with deductions: {r2[\"total_tax_liability\"]:,.0f}')
print('Calculator migration OK')
"
```

---

## Task 1.2: Migrate Verifier from v2 (Day 1 morning)

**File**: `tools/verifier.py`
**Source**: Copy from `../FinITR-AI-v2/components/07_verifier/verifier.py`

Direct copy — no changes needed. The NLI cross-encoder setup is already correct.

**Test**:
```bash
python -c "
from tools.verifier import FaithfulnessVerifier
v = FaithfulnessVerifier()
r = v.verify('Section 80CCD(2) allows employer NPS deduction up to 14% of basic salary.', 
             'Under section 80CCD(2), employer contribution to NPS is deductible up to 14 percent of salary for central government and 10 percent for others.')
print(f'Verification: {r[\"label\"]} (score: {r[\"score\"]:.2f})')
print('Verifier migration OK')
"
```

---

## Task 1.3: Migrate CSV Parser from v2 (Day 1 afternoon)

**File**: `parsers/csv_parser.py`
**Source**: Adapt from `../FinITR-AI-v2/components/01_csv_parser/parser.py`

Copy the parser but modify the output format. Each transaction dict must NOW include:
```python
{
    "id": "txn_001",
    "date": "2025-04-05",
    "description": "NEFT/SALARY/TECHCORP INDIA PVT LTD/APR25",
    "amount": 151200.0,
    "transaction_type": "credit",  
    "balance": 351200.0,
    "vendor": "TECHCORP INDIA PVT LTD",
    "txn_mode": "NEFT",
    "note": "SAL CREDIT",
    # NEW FIELD — hint for schedule mapping (filled later by AuditorAgent)
    "itr_schedule_hint": None,
}
```

**Test**:
```bash
python -c "
from parsers.csv_parser import CSVParser
txns = CSVParser().parse('data/synthetic/sample_bank_statement.csv')
print(f'Parsed {len(txns)} transactions')
assert len(txns) > 40, f'Expected 40+ transactions, got {len(txns)}'
assert txns[0]['transaction_type'] in ('credit', 'debit')
assert txns[0]['vendor'] is not None or txns[0]['description'] != ''
print('CSV parser OK')
"
```

---

## Task 1.4: Implement AIS Parser (Day 1-2)

**File**: `parsers/ais_parser.py`
**Test data**: `data/synthetic/sample_ais.json`

The skeleton is already in place. Implement ALL methods:

1. `parse()` — reads JSON, normalizes SFT entries, returns structured dict
2. `_normalize_sft()` — maps SFT codes to income types using SFT_CODE_MAP
3. `_parse_tds()` — extracts TDS entries
4. `_build_summary()` — aggregate statistics
5. `_mask_pan()` — already implemented

Output contract:
```python
{
    "pan": "A****234F",
    "assessment_year": "2026-27",
    "sft_entries": [
        {
            "type": "salary",           # normalized from SFT-001
            "amount": 2200000,
            "reporter": "TECHCORP INDIA PVT LTD",
            "tds_deducted": 182400,
            "section": "192",
            "source": "ais",
            "sft_code": "SFT-001",
            "quarter": "ALL",
            "additional_info": {},
        },
        # ... more entries
    ],
    "tds_entries": [...],
    "summary": {
        "total_reported_income": 2564200,  # sum of all SFT amounts
        "total_tds": 190860,
        "income_types_present": ["salary", "interest_savings", "interest_fd", 
                                  "mf_redemption", "crypto_vda", "equity_sale",
                                  "foreign_remittance"],
    }
}
```

**Test**:
```bash
python -c "
from parsers.ais_parser import AISParser
result = AISParser().parse('data/synthetic/sample_ais.json')
print(f'AIS entries: {len(result[\"sft_entries\"])}')
print(f'Income types: {result[\"summary\"][\"income_types_present\"]}')
print(f'Total reported: {result[\"summary\"][\"total_reported_income\"]:,.0f}')
assert len(result['sft_entries']) == 7, 'Expected 7 SFT entries'
assert 'crypto_vda' in result['summary']['income_types_present']
print('AIS parser OK')
"
```

---

## Task 1.5: Implement Form 16 Parser (Day 2)

**File**: `parsers/form16_parser.py`
**Test data**: `data/synthetic/sample_form16.json`

For v3, Form 16 input is structured JSON (not PDF). PDF parsing is a stretch goal for Week 5.

Implement `parse()` that reads the JSON and returns the standardized format shown in the skeleton's docstring. Key fields: `gross_salary`, `basic_salary`, `hra_received`, `tds_deducted`, `deductions_claimed`, `regime`.

**Test**:
```bash
python -c "
from parsers.form16_parser import Form16Parser
f16 = Form16Parser().parse('data/synthetic/sample_form16.json')
print(f'Gross salary: {f16[\"gross_salary\"]:,.0f}')
print(f'TDS deducted: {f16[\"tds_deducted\"]:,.0f}')
print(f'Regime: {f16[\"regime\"]}')
assert f16['gross_salary'] == 2200000
assert f16['hra_received'] == 352000
print('Form 16 parser OK')
"
```

---

## Task 1.6: Migrate Retriever + Build Vector Store (Day 3)

**File**: `tools/retriever.py`
**Source**: Adapt from `../FinITR-AI-v2/components/04_pageindex/retriever.py`

Copy the PageIndex retriever. Then EXPAND the tree to cover at minimum:
- All New Regime allowed deductions (80CCD(2), 80CCH, Family Pension, Standard Deduction)
- Section 115BBH (VDA/crypto taxation)
- Section 111A, 112A, 112 (capital gains)
- Section 44ADA (presumptive profession)
- Section 87A (rebate + marginal relief)
- Section 17(2) (perquisites — for RSU)
- HRA exemption rules (Section 10(13A))
- Section 192 (TDS on salary)

**File**: `tools/vector_store.py`

Implement ChromaDB vector store:
```python
import chromadb
from sentence_transformers import SentenceTransformer

class VectorStore:
    def __init__(self, persist_dir="./data/chroma_db"):
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection("tax_corpus")
    
    def build_index(self, corpus_path="corpus/"):
        # Load from itr_text_corpus.py and itr_knowledge_base.json
        # Chunk into ~200 token segments
        # Embed and store
        pass

    def query(self, query, top_k=3):
        # Embed query, search collection, return results
        pass
```

**Test**:
```bash
python -c "
from tools.retriever import PageIndexRetriever
r = PageIndexRetriever()
result = r.retrieve('Section 80CCD(2) employer NPS deduction limit')
print(f'Retrieved: {result.get(\"title\", \"\")}')
assert result.get('retrieved_text', '') != '', 'Empty retrieval!'
print('Retriever OK')
"
```

---

## Task 1.7: Implement AuditorAgent Reconciliation (Day 3-5)

**File**: `agents/auditor_agent.py`

This is the CORE deliverable of Week 1. Implement ALL the methods in the skeleton:

### _extract_form16_income()
Read `ctx.form16_data` and produce income items tagged with source="form16".

### _extract_ais_income()
Read `ctx.ais_data["sft_entries"]` and return as standardized income items.

### _extract_bank_income()
Migrate the vendor regex detection from v2's `predict.py`:
- CRYPTO_VENDORS, CAPITAL_GAINS_VENDORS, FREELANCE_VENDORS, SALARY_KEYWORDS, etc.
- For each bank transaction, classify and tag with flag_type
- For ambiguous cases, call Ollama LLM (with regex fallback)

### _build_unified_ledger()
The KEY function. For each income item across all sources:
```python
{
    "item": "Salary - TECHCORP",
    "amount_form16": 2200000,
    "amount_ais": 2200000, 
    "amount_bank": 1814400,  # net salary (post TDS)
    "match_status": "confirmed",  # form16 and ais agree
    "delta": 0,
    "itr_schedule": "Schedule Salary",
    "risk_weight": 0,
}
```

For items appearing in AIS but NOT in Form 16:
```python
{
    "item": "Savings Interest - HDFC",
    "amount_form16": 0,        # not reported by employer
    "amount_ais": 14200,       # but government knows!
    "amount_bank": 14200,      # and bank statement confirms
    "match_status": "ais_only",
    "delta": 14200,
    "itr_schedule": "Schedule OS",
    "risk_weight": 10,
}
```

### _cross_ref_ais_form16()
Find every SFT entry in AIS that has no corresponding item in Form 16.
These are the notice-risk items.

### _detect_anomalies()
Migrate v2 anomaly detection:
- CRYPTO_TRIGGER, CAPITAL_GAINS_TRIGGER, FREELANCE_INCOME, HIGH_VALUE_CASH
- For each flagged txn, check if it appears in AIS (in_ais: true/false)
- Items in bank but NOT in AIS are lower risk (government doesn't know yet)
- Items in AIS but NOT addressed are HIGH risk

### _compute_risk_score()
Evidence-based scoring using RISK_WEIGHTS from the skeleton:
```python
total = 0
breakdown = []
for mismatch in mismatches:
    weight = RISK_WEIGHTS.get(mismatch["type"], 5)
    total += weight
    breakdown.append({"item": mismatch["item"], "weight": weight, "reason": ...})

# Normalize to 0-100
score = min(100, total)
level = "LOW" if score < 20 else "MEDIUM" if score < 50 else "HIGH" if score < 75 else "CRITICAL"
```

### _generate_questions()
For each ambiguous item (AIS shows it, but we don't know details):
- Crypto → "What was your cost of acquisition?"
- Capital gains → "Upload Zerodha P&L or enter gains manually"
- Freelance → "Is this professional income under 44ADA?"
- Cash deposit → "Source of ₹75,000 cash deposit?"

---

## Task 1.8: Wire Orchestrator Document Parsing (Day 5)

**File**: `agents/orchestrator.py`

Implement `_parse_documents()` — the TODO block. Import all parsers, call them, populate context.

Implement `_apply_result()` for the auditor agent — map its output fields to context.

**Test (end-to-end Week 1)**:
```bash
python -m agents.orchestrator \
    --bank data/synthetic/sample_bank_statement.csv \
    --ais data/synthetic/sample_ais.json \
    --form16 data/synthetic/sample_form16.json \
    --output outputs/week1_test.json

# Verify output
python -c "
import json
r = json.load(open('outputs/week1_test.json'))
print(f'Reconciliation items: {len(r.get(\"reconciliation\", {}).get(\"ledger\", []))}')
print(f'Anomalies: {len(r.get(\"anomalies\", []))}')
print(f'Risk score: {r.get(\"risk_score\", {}).get(\"total_score\", \"N/A\")}')
print(f'Risk level: {r.get(\"risk_score\", {}).get(\"risk_level\", \"N/A\")}')
# Expected: risk_score should be HIGH because of crypto, freelance, and FD interest not in Form16
"
```

---

## Week 1 Acceptance Criteria

- [ ] Calculator handles both Old and New regime, HRA exemption works
- [ ] AIS parser correctly extracts all 7 SFT entries from synthetic data
- [ ] Form 16 parser extracts salary breakup and deductions
- [ ] CSV parser handles the synthetic bank statement (50+ transactions)
- [ ] AuditorAgent produces a unified ledger with match_status for each item
- [ ] Risk score is > 50 for the synthetic test case (crypto + freelance + FD interest undeclared)
- [ ] PageIndex retriever expanded to 30+ nodes minimum
- [ ] Vector store builds and queries work
- [ ] Full pipeline runs end-to-end and produces JSON output
- [ ] All test commands above pass
