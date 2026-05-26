# Week 5: Polish — Streamlit UI, FastAPI, Voice Demo, ITR JSON

## Goal
A demo-ready application that can be presented in a viva. Everything should work end-to-end on the synthetic test case with a polished UI. Voice input is a bonus.

---

## Task 5.1: FastAPI Backend (Day 1)

**File**: `api/main.py`

Create REST API that wraps the orchestrator:

```python
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
import uvicorn

app = FastAPI(title="FinITR-AI v3", version="3.0")

@app.post("/analyze")
async def analyze(
    bank_csv: UploadFile = File(None),
    ais_json: UploadFile = File(None),
    form16_json: UploadFile = File(None),
    gross_income: float = 0,
):
    """Run the full multi-agent pipeline."""
    # Save uploaded files to temp dir
    # Call Orchestrator.run()
    # Return JSON report
    pass

@app.post("/interview/answer")
async def answer_interview(answers: dict):
    """Submit interview answers and re-run pipeline with them."""
    pass

@app.get("/report/ca-brief")
async def get_ca_brief(format: str = "pdf"):
    """Download CA Brief as PDF."""
    pass

@app.get("/health")
async def health():
    return {"status": "ok", "ollama": check_ollama(), "version": "3.0"}
```

Run: `uvicorn api.main:app --reload --port 8000`

---

## Task 5.2: Streamlit UI Overhaul (Day 1-3)

**File**: `frontend/app.py` + `frontend/components/*.py`

### Tab 1: Dashboard & Risk
**File**: `frontend/components/dashboard.py`

- Top row: 4 metric cards (st.metric)
  - Total Gross Income
  - Flagged Transactions Count
  - Estimated Tax Liability
  - Notice Risk Score
- Risk Gauge: plotly Indicator gauge (green/yellow/red)
- Reconciliation Table: st.dataframe with color-coded match_status
  - Green rows: "confirmed" (all sources agree)
  - Yellow rows: "ais_only" (in AIS but not Form 16)
  - Red rows: "mismatch" (amounts differ)
- Risk breakdown: expandable section showing per-item risk weights

```python
import plotly.graph_objects as go

def render_risk_gauge(score: int, level: str):
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        title={"text": "Notice Risk Score"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkred" if score > 70 else "orange" if score > 40 else "green"},
            "steps": [
                {"range": [0, 20], "color": "#d4edda"},
                {"range": [20, 50], "color": "#fff3cd"},
                {"range": [50, 75], "color": "#f8d7da"},
                {"range": [75, 100], "color": "#dc3545"},
            ],
        }
    ))
    st.plotly_chart(fig, use_container_width=True)
```

### Tab 2: ITR Assist Wizard
**File**: `frontend/components/interview.py`

- Display ITR form recommendation with bold alert
- For each interview question from AuditorAgent:
  - Show the triggering evidence (transaction + AIS entry)
  - Render appropriate input (radio, number_input, file_uploader)
  - On answer submission, update session state and re-compute
- After all questions answered, show schedule mapping table

### Tab 3: Regime Comparator & CTC Simulator
**File**: `frontend/components/simulator.py`

- Side-by-side columns: Old Regime vs New Regime
- For each: show deductions, taxable income, slab-wise tax, cess, total
- Bottom: verdict with savings amount
- Sankey diagram (plotly): Gross → Deductions → Taxable → Slabs → Tax → TDS → Net Payable
- NPS slider: drag to simulate employer NPS contribution, live-update both columns

```python
import plotly.graph_objects as go

def render_sankey(tax_data):
    """Money flow: Gross → Deductions → Taxable → Tax → Cess → TDS → Payable"""
    fig = go.Figure(go.Sankey(
        node=dict(label=[...], color=[...]),
        link=dict(source=[...], target=[...], value=[...]),
    ))
    st.plotly_chart(fig, use_container_width=True)
```

### Tab 4: Final Report
**File**: `frontend/components/report.py`

- CA Brief preview (rendered in Streamlit with markdown)
- Download buttons: "Download CA Brief (PDF)" and "Download Full Report (JSON)"
- Agent trace expandable section (shows which agents ran, iterations, blocked claims)
- Verification summary: FAITHFUL / UNVERIFIED / HALLUCINATED counts

---

## Task 5.3: ITR JSON Export (Day 3-4, if time permits)

**File**: `outputs/itr_json_generator.py`

Generate ITR-2 JSON matching the IT Department's schema (FY 25-26).

The schema is published annually. Key structures:
```json
{
    "ITR": {
        "ITR2": {
            "PartA_GEN1": {
                "PersonalInfo": { ... },
                "FilingStatus": { "ReturnFileSec": 139, "NewTaxRegime": "Y" }
            },
            "ScheduleS": {
                "Salary": [{ "NameOfEmployer": "...", "GrossSalary": 2200000 }]
            },
            "ScheduleOS": {
                "IncFromOthSrc": { "OthSrcIncome": 14200 }
            },
            "ScheduleCGPost": {
                "ShortTermCapGainFor15Per": { ... },
                "LongTermCapGain20Per": { ... }
            },
            "ScheduleVDA": {
                "VDADetails": [{ "Consideration": 128000, "CostOfAcq": 95000 }]
            },
            "PartBTI": {
                "TotalIncome": 2264200
            },
            "PartBTTI": {
                "TaxPayable": 189696,
                "TDSClaimed": 190860,
                "RefundDue": 1164
            }
        }
    }
}
```

This is complex. Implement only the schedules you've built (Salary, OS, CG, VDA, Part B-TI, Part B-TTI). Leave other schedules as empty/null.

Provide a download button in Tab 4: "Download ITR-2 JSON (for e-filing portal upload)"

---

## Task 5.4: Voice Input Demo (Day 4-5, BONUS)

**File**: `frontend/components/voice_input.py`

Use the browser's Web Speech API via Streamlit's `st.audio_input` or a custom component.

If `st.audio_input` is available (Streamlit 1.33+):
```python
audio = st.audio_input("Speak your financial details")
if audio:
    # Save to temp file
    # Transcribe with Whisper (via Ollama or local whisper)
    # Parse the transcript for financial info
    # Auto-fill the interview answers
```

Alternative: use `streamlit-webrtc` or a simple text input with a Hindi/Hinglish prompt:
```
"मेरी salary 22 lakh है, Zerodha pe 85 hazaar ka equity sale kiya, 
WazirX pe crypto bhi trade kiya, aur Upwork se 85k freelance income aayi"
```

The LLM parses this into structured data:
```python
prompt = f"""Extract financial information from this Hindi/Hinglish text.
Return JSON with: gross_income, equity_sales, crypto_trades, freelance_income.
Text: {transcript}"""
```

This is DEMO-ONLY quality. The goal is a 30-second wow moment in the presentation, not production-grade voice input.

---

## Task 5.5: Demo Script Preparation (Day 5)

**File**: `DEMO_SCRIPT.md`

Write the exact demo flow for a 10-minute presentation:

1. (0:00) Upload 3 documents → show reconciliation table with mismatches
2. (2:00) Zoom into risk score → explain why it's HIGH → show AIS evidence
3. (3:00) Show ITR form recommendation → "You MUST file ITR-2"
4. (4:00) Answer interview questions → watch schedules auto-populate
5. (5:00) Show regime comparator → "New Regime saves ₹53,928"
6. (6:00) Drag NPS slider → live-update tax → "Additional ₹24,400 saved"
7. (7:00) Show agent trace → "CriticAgent blocked 80C hallucination on iteration 1"
8. (8:00) Download CA Brief PDF → open it → show schedule-wise filing map
9. (9:00) Show IndianTaxBench results → your system vs GPT-4o-mini
10. (10:00) Voice demo → "मेरी salary 22 lakh hai..." → auto-fills form

Prepare backup plans for each step in case something fails during live demo.

---

## Week 5 Acceptance Criteria

- [ ] FastAPI backend serves all endpoints
- [ ] Streamlit UI has polished 4-tab layout with plotly visualizations
- [ ] Risk gauge renders correctly with color coding
- [ ] Reconciliation table shows color-coded match status
- [ ] Sankey diagram renders money flow
- [ ] NPS slider updates tax computation in real-time
- [ ] CA Brief PDF downloads correctly
- [ ] ITR JSON generates (at least for basic schedules)
- [ ] Demo script written and rehearsed
- [ ] Voice input works for at least one Hinglish sentence (bonus)
- [ ] Everything runs on a fresh machine with just `pip install` + `ollama`
