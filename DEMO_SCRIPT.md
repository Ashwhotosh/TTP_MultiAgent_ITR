# FinITR-AI v3 — Demo Script (10-minute Viva Presentation)

**Setup before demo:**
- `streamlit run frontend/app.py` running on localhost:8501
- Synthetic data files ready in `data/synthetic/`
- Ollama running: `ollama serve` + `qwen2.5:7b` model pulled
- Backup: pre-computed `outputs/demo_report.json` ready to load

---

## Timeline

### 0:00 — Upload Documents & Run Pipeline
**Action:** Open Streamlit UI → upload `sample_bank_statement.csv`, `sample_ais.json`, `sample_form16.json` from sidebar → click **Run Orchestrator Pipeline**

**Say:** "I'm uploading three documents simultaneously — bank statement, government's AIS (Annual Information Statement), and Form 16. The system runs a multi-agent pipeline that cross-references all three."

**What to show:** Spinner → "Pipeline complete!" → Switch to **Dashboard & Risk** tab

**Backup:** Use **Load Sample Data** → "Use Synthetic Test Case" button

---

### 2:00 — Zoom into Risk Score
**Action:** Point to the risk gauge (showing ~75/100 = HIGH/CRITICAL)

**Say:** "The Notice Risk Score is 75/100 — HIGH. This means filing without addressing these items significantly increases ITR scrutiny probability."

**What to show:**
- Risk gauge with dark red needle
- Risk Contributors section: "Crypto undeclared (+30), Capital gains not in Form 16 (+20), Freelance income (+25)"
- Expand one anomaly: show the AIS evidence + reasoning

**Backup:** If gauge shows 0, scroll to "Risk Contributors" section and explain the breakdown table

---

### 3:00 — ITR Form Recommendation
**Action:** Switch to **ITR Assist Wizard** tab

**Say:** "Based on the income profile — salary plus capital gains plus crypto — the system says: *You MUST file ITR-2*. ITR-1 (Sahaj) is blocked because capital gains and VDA income are present."

**What to show:**
- Red banner: "You MUST file: ITR-2"
- Blocked forms section: ITR-1 blocked by `capital_gains`, `crypto_vda`
- Required schedules list: `Schedule CG | Schedule VDA | Schedule OS`

---

### 4:00 — Answer Interview Questions
**Action:** Answer the interview questions shown below the form recommendation

**Say:** "The AuditorAgent generated these questions from the anomalies it detected. This is where the user provides the cost of acquisition for crypto and capital gains."

**What to show:**
- Crypto question: enter cost of acquisition (e.g., ₹95,000)
- Capital gains question: enter amount (e.g., ₹85,000)
- Freelance checkbox: tick "Yes, Section 44ADA"
- Click **Save Answers & Re-run Pipeline**
- Watch schedule mapping table update at the bottom

---

### 5:00 — Regime Comparator
**Action:** Switch to **Regime Comparator** tab

**Say:** "After incorporating interview answers, OptimizerAgent compared both regimes. New Regime saves ₹53,928 — the system recommends New Regime despite the freelance income."

**What to show:**
- Blue banner: "Recommended: New Regime (115BAC) — Savings: ₹53,928"
- Side-by-side: Old Regime (₹2.43L) vs New Regime (₹1.90L)
- Effective tax rate comparison
- Slab-wise breakdown in expander

**Backup:** Point to the deductions table — "Old regime shows 80C, HRA, but still doesn't beat New Regime for this income profile"

---

### 6:00 — NPS Slider Demo
**Action:** Drag the **Employer NPS Contribution** slider from 0 to ₹2.2L (max)

**Say:** "Now watch this — if the employer restructures the CTC to maximize NPS contributions under Section 80CCD(2), the tax drops further in real-time."

**What to show:**
- Slider moves from ₹0 to ₹2,20,000
- "Additional Savings: ₹24,400" metric updates live
- Updated New Regime Tax drops from ₹1.90L to ₹1.66L
- Sankey diagram updates at the bottom

---

### 7:00 — Agent Trace & Critic
**Action:** Switch to **Final Report** tab → scroll to Agent Execution Trace

**Say:** "This is the audit trail. You can see every agent that ran, how long it took, and what the CriticAgent did. On iteration 1, CriticAgent blocked an 80C deduction claim that wasn't supported by Form 16 evidence."

**What to show:**
- Expand AuditorAgent trace: "✅ AuditorAgent (success) — 0.8s"
- Expand CriticAgent trace: "⚠️ CriticAgent (needs_review) — 1.2s"
- Critic Feedback section: "Blocked 1 claim — Section 80C: claimed ₹1.5L not supported by Form 16"

---

### 8:00 — Download CA Brief PDF
**Action:** Click **Download CA Brief (PDF)** button → open the downloaded PDF

**Say:** "The CA Brief is a 2-page professional summary for the chartered accountant. Page 1 has the client profile and regime verdict. Page 2 has the schedule-wise filing map with exact amounts and TDS credits."

**What to show:**
- PDF opens: Section 1 (Client Profile), Section 2 (Schedule Map), Section 3 (Notice Risk)
- Point to: "PAN, Gross Income, ITR-2, New Regime saves ₹53,928"
- Point to schedule table: "Salary → Schedule 17(1), Interest → Schedule OS 56, Capital Gains → Schedule CG 111A"

---

### 9:00 — IndianTaxBench Results
**Action:** Open terminal / show benchmark output

**Say:** "We benchmarked against the IndianTaxBench dataset — 50 Indian tax questions across 8 categories. FinITR-AI v3 scores 84% vs GPT-4o-mini at 71%, primarily due to the deterministic calculator engine."

**What to show:** Terminal output or screenshot from `benchmarks/indian_tax_bench/`

---

### 10:00 — Voice Demo
**Action:** Switch to **Voice Demo** tab → text field has pre-filled Hinglish text

**Say:** "Finally — the bonus feature. Watch what happens when I input financial details in Hindi/Hinglish, like someone would actually speak them."

**Type/submit:** *"मेरी salary 22 lakh है, Zerodha pe 85 hazaar ka equity sale kiya, WazirX pe crypto bhi trade kiya, aur Upwork se 85k freelance income aayi"*

**Click:** Parse Financial Details

**What to show:**
- Extracted: Gross Income ₹22,00,000 | Equity Sales ₹85,000 | Crypto: Yes | Freelance ₹85,000
- "This could auto-fill the interview form — making the app accessible to users who don't know English tax terminology"

---

## Backup Plans

| Step | Primary | Backup |
|------|---------|--------|
| Pipeline run | Upload files + run | Click "Use Synthetic Test Case" |
| Risk gauge shows 0 | - | Explain breakdown table, show anomalies |
| Ollama down | LLM narrative shows | Fallback template narrative still works |
| PDF fails | - | Show Markdown preview in expander |
| NPS slider no update | - | Show CTC strategy metrics instead |
| Voice parsing fails | Ollama parses | Regex fallback extracts values |
| Streamlit crash | - | Show `outputs/demo_report.json` via `st.json()` |

---

## Key Numbers to Memorise

- Gross Income: ₹22,00,000
- Capital Gains (STCG 15%): ₹85,000
- Freelance (44ADA 50%): ₹42,500 taxable
- VDA/Crypto gain: ₹33,000 (at 30% = ₹9,900 tax)
- Old Regime Tax: ~₹2,43,000
- New Regime Tax: ~₹1,89,000
- Savings: ~₹53,928
- With NPS restructuring: ~₹24,400 additional savings
- Notice Risk: 75/100 (HIGH)
- ITR Form: ITR-2 (mandatory due to CG + VDA)
