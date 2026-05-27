# Week 3: Deep Vertical — Schedule CG/VDA + CA Brief

## Goal
By end of week 3, the system can ingest a Zerodha P&L CSV and WazirX CSV, auto-populate Schedule CG and Schedule VDA, and generate a downloadable CA Brief PDF.

---

## Task 3.1: Implement Schedule CG Builder (Day 1-2)

**File**: `schedules/schedule_cg.py`

### Zerodha P&L Format
Zerodha's Tax P&L CSV (downloadable from Console) looks like:
```
Symbol,ISIN,Trade Date,Buy Date,Buy Price,Buy Qty,Sell Date,Sell Price,Sell Qty,P&L
INFY,INE009A01021,2025-06-15,2024-03-10,1450.00,10,2025-06-15,1680.00,10,2300.00
HDFCBANK,INE040A01034,2025-09-20,2025-07-15,1620.00,5,2025-09-20,1590.00,5,-150.00
```

Create synthetic test data: `data/synthetic/sample_zerodha_pnl.csv`

### Implement build_from_zerodha():
1. Parse the CSV
2. For each trade, determine:
   - Holding period (buy date to sell date)
   - If holding period > 12 months AND STT was paid → LTCG under 112A
   - If holding period ≤ 12 months AND STT was paid → STCG under 111A
   - If holding period > 24 months for debt/unlisted → LTCG under 112
   - Otherwise → STCG other
3. For LTCG 112A: apply grandfathering
   - Cost of acquisition = MAX(actual cost, FMV on 31-Jan-2018)
   - FMV = closing price on 31-Jan-2018 (hardcode a lookup table for top 50 stocks, or use the buy price if before 2018)
   - First ₹1,25,000 of LTCG is exempt (FY 25-26)
4. Aggregate by category:
```python
{
    "schedule_cg": {
        "stcg_111a": {"gains": X, "losses": Y, "net": Z, "tax_rate": 0.20},
        "ltcg_112a": {"gains": X, "exemption_125k": min(X, 125000), "taxable": max(0, X-125000), "tax_rate": 0.125},
        "ltcg_112": {"gains": X, "tax_rate": 0.20},
        "stcg_other": {"gains": X, "tax_rate": "slab"},
    },
    "trade_details": [
        {"symbol": "INFY", "type": "LTCG_112A", "buy_date": ..., "sell_date": ..., "gain": 2300, ...},
    ],
    "loss_carryforward": {"stcg": 0, "ltcg": 0},
    "total_cg_tax": float,
}
```

### Loss set-off rules:
- STCG can offset both STCG and LTCG
- LTCG can offset only LTCG
- Net loss carried forward for 8 years

**Test**:
```bash
python -c "
from schedules.schedule_cg import ScheduleCGBuilder
cg = ScheduleCGBuilder()
result = cg.build_from_zerodha('data/synthetic/sample_zerodha_pnl.csv')
print(f'STCG 111A: {result[\"schedule_cg\"][\"stcg_111a\"][\"net\"]:,.0f}')
print(f'LTCG 112A: {result[\"schedule_cg\"][\"ltcg_112a\"][\"taxable\"]:,.0f}')
print(f'Trades processed: {len(result[\"trade_details\"])}')
"
```

---

## Task 3.2: Implement Schedule VDA Builder (Day 2-3)

**File**: `schedules/schedule_vda.py`

### WazirX Export Format
WazirX trade history CSV looks like:
```
Date,Market,Type,Price,Volume,Total,Fee,Fee Currency
2025-06-25,BTC/INR,Buy,4500000,0.011,49500,74.25,INR
2025-08-10,BTC/INR,Sell,5200000,0.015,78000,117.00,INR
2025-09-20,ETH/INR,Sell,230000,0.217,49910,74.87,INR
```

Create synthetic test data: `data/synthetic/sample_wazirx_trades.csv`

### Implement build_from_wazirx():
Section 115BBH rules:
- Tax rate: 30% flat on gains (NO basic exemption threshold)
- Cost: ONLY acquisition cost (no other deduction except cost of acquisition)
- Loss: CANNOT be set off against ANY other income
- Loss: CANNOT be carried forward
- TDS: 1% under Section 194S (already deducted by exchange)
- Fee: NOT deductible

1. Match buys to sells (FIFO method)
2. Compute gain per trade = sell_amount - buy_cost
3. Aggregate:
```python
{
    "schedule_vda": {
        "total_sale_consideration": 128000,
        "total_cost_of_acquisition": 95000,
        "total_gains": 33000,
        "tax_at_30_percent": 9900,
        "tds_194s_credit": 3840,
        "net_tax_payable": 6060,
    },
    "trade_details": [...],
    "asset_wise_summary": {
        "BTC": {"gains": X, "losses": Y},
        "ETH": {"gains": X, "losses": Y},
    }
}
```

**Test**:
```bash
python -c "
from schedules.schedule_vda import ScheduleVDABuilder
vda = ScheduleVDABuilder()
result = vda.build_from_wazirx('data/synthetic/sample_wazirx_trades.csv')
print(f'Total VDA gains: {result[\"schedule_vda\"][\"total_gains\"]:,.0f}')
print(f'Tax at 30%: {result[\"schedule_vda\"][\"tax_at_30_percent\"]:,.0f}')
print(f'TDS credit: {result[\"schedule_vda\"][\"tds_194s_credit\"]:,.0f}')
"
```

---

## Task 3.3: Integrate Schedules into Pipeline (Day 3)

**File**: `agents/compliance_agent.py`

When ComplianceAgent detects capital_gains or crypto_vda income types,
and the user uploads a broker/exchange CSV, auto-populate the schedule:

```python
if "capital_gains" in income_types and ctx.interview_answers.get("zerodha_csv"):
    from schedules.schedule_cg import ScheduleCGBuilder
    cg_data = ScheduleCGBuilder().build_from_zerodha(ctx.interview_answers["zerodha_csv"])
    ctx.schedule_mapping.extend(self._cg_to_schedule_entries(cg_data))
```

---

## Task 3.4: Build CA Brief Generator (Day 4-5)

**File**: `outputs/ca_brief_generator.py` (NEW)

Generate a PDF using ReportLab with 3 sections:

### Section 1: Client Profile
- PAN (masked), AY, income summary, recommended ITR form, regime recommendation

### Section 2: Schedule-wise Filing Map
Table format:
| Schedule | Item | Amount | Section | TDS Credit | Source |
|----------|------|--------|---------|------------|--------|
| Salary | TECHCORP | 22,00,000 | 17(1) | 1,82,400 | Form 16 + AIS |
| Schedule OS | Savings Interest | 14,200 | 56 | 1,420 | AIS only ⚠️ |
| Schedule VDA | Crypto - WazirX | 33,000 | 115BBH | 3,840 | AIS + Interview |
| Schedule CG | LTCG - Zerodha | 8,400 | 112A | 0 | Broker P&L |

### Section 3: Risk Items
- Items needing CA judgment (RSU, ambiguous credits, etc.)
- Notice risk score with breakdown

**File**: `frontend/components/report.py`

Streamlit component for Tab 4 that renders the CA Brief data and offers PDF download.

**Test**: Generate a CA Brief PDF from the synthetic data and verify it opens correctly.

---

## Task 3.5: Create Synthetic Broker Data (Day 1 — do this first)

**Files**:
- `data/synthetic/sample_zerodha_pnl.csv` — 8-10 trades covering STCG and LTCG
- `data/synthetic/sample_wazirx_trades.csv` — 5-7 crypto trades

Make sure the amounts are consistent with what the AIS shows:
- Zerodha equity sales: ₹85,000 total (matching AIS SFT-009)
- WazirX crypto: ₹1,28,000 total sale (matching AIS SFT-016)

---

## Week 3 Acceptance Criteria

- [ ] Schedule CG builder correctly classifies STCG 111A vs LTCG 112A
- [ ] Grandfathering applies to pre-2018 purchases
- [ ] LTCG exemption of ₹1.25L applied correctly
- [ ] Schedule VDA computes 30% flat tax, no loss offset
- [ ] TDS credits (194, 194S) correctly accumulated
- [ ] CA Brief PDF generates with all 3 sections
- [ ] CA Brief is downloadable from Streamlit Tab 4
- [ ] Pipeline output includes schedule_mapping with all entries
- [ ] Synthetic broker data is consistent with AIS synthetic data
