"""
Streamlit frontend for FinITR-AI v3.
Runs the multi-agent pipeline and displays structured results in 5 tabs.
"""
import os
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="FinITR-AI v3", page_icon="💰", layout="wide")

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 16px; }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: #f1f2f6;
        border-radius: 5px 5px 0 0;
        padding: 10px 20px;
        font-weight: bold;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2e86de !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("FinITR-AI v3")
st.caption("Agentic Multi-Document Reconciliation & Tax Optimization for Indian ITR Filing")

# ── Session state init ──
if "report" not in st.session_state:
    st.session_state.report = None
if "interview_answers" not in st.session_state:
    st.session_state.interview_answers = {}


def _save_uploaded(file, prefix: str = "form16") -> str:
    os.makedirs("outputs", exist_ok=True)
    ext = Path(file.name).suffix.lower()
    path = Path("outputs") / f"{prefix}_uploaded{ext}"
    with open(path, "wb") as f:
        f.write(file.getbuffer())
    return str(path)


# ── Sidebar ──
st.sidebar.header("Document Uploads")
bank_file = st.sidebar.file_uploader("Bank Statement (CSV)", type=["csv"])
ais_file = st.sidebar.file_uploader("AIS (JSON)", type=["json"])
form16_file = st.sidebar.file_uploader(
    "Form 16 (PDF or JSON)",
    type=["pdf", "json"],
    help="Upload your employer-issued Form 16. PDF or pre-parsed JSON."
)
zerodha_file = st.sidebar.file_uploader("Zerodha P&L (CSV)", type=["csv"])
wazirx_file = st.sidebar.file_uploader("WazirX Trades (CSV)", type=["csv"])

st.sidebar.header("User Profile")
# Pre-fill from voice input if available
voice_income = st.session_state.get("voice_gross_income", 0.0)
gross_income_input = st.sidebar.number_input(
    "Gross Income (₹)", min_value=0.0, step=50000.0,
    value=voice_income, help="Leave 0 to auto-derive from Form 16"
)
basic_salary_input = st.sidebar.number_input(
    "Basic Salary (₹)", min_value=0.0, step=25000.0, value=0.0
)

run_pipeline = st.sidebar.button("Run Orchestrator Pipeline", use_container_width=True, type="primary")

if run_pipeline:
    bank_path = _save_uploaded(bank_file, "bank") if bank_file else None
    ais_path = _save_uploaded(ais_file, "ais") if ais_file else None
    form16_path = _save_uploaded(form16_file, "form16") if form16_file else None

    if zerodha_file:
        z_path = _save_uploaded(zerodha_file, "zerodha")
        st.session_state.interview_answers["zerodha_csv"] = z_path
    if wazirx_file:
        w_path = _save_uploaded(wazirx_file, "wazirx")
        st.session_state.interview_answers["wazirx_csv"] = w_path

    with st.spinner("Executing multi-agent tax pipeline..."):
        try:
            from agents.orchestrator import Orchestrator
            orch = Orchestrator()
            report = orch.run(
                bank_csv=bank_path,
                ais_json=ais_path,
                form16_json=form16_path,
                gross_income=gross_income_input,
                basic_salary=basic_salary_input,
                interview_answers=st.session_state.interview_answers,
            )
            st.session_state.report = report
            st.sidebar.success("Pipeline complete!")
        except Exception as e:
            st.sidebar.error(f"Pipeline failed: {e}")
            st.exception(e)

# ── Sample data quick-load ──
with st.sidebar.expander("Load Sample Data"):
    if st.button("Use Synthetic Test Case"):
        sample_bank = "data/synthetic/sample_bank_statement.csv"
        sample_ais = "data/synthetic/sample_ais.json"
        sample_f16 = "data/synthetic/sample_form16.json"
        if all(Path(p).exists() for p in [sample_bank, sample_ais, sample_f16]):
            with st.spinner("Running pipeline on synthetic data..."):
                try:
                    from agents.orchestrator import Orchestrator
                    orch = Orchestrator()
                    report = orch.run(
                        bank_csv=sample_bank,
                        ais_json=sample_ais,
                        form16_json=sample_f16,
                    )
                    st.session_state.report = report
                    st.sidebar.success("Synthetic data loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
        else:
            st.warning("Synthetic data files not found.")

# ── Main tabs ──
if st.session_state.report:
    report = st.session_state.report

    tab_dash, tab_assist, tab_compare, tab_report, tab_voice = st.tabs([
        "Dashboard & Risk",
        "ITR Assist Wizard",
        "Regime Comparator",
        "Final Report",
        "Voice Demo",
    ])

    with tab_dash:
        from frontend.components.dashboard import render_dashboard
        render_dashboard(report)

    with tab_assist:
        from frontend.components.interview import render_interview
        render_interview(report)

    with tab_compare:
        from frontend.components.simulator import render_simulator
        render_simulator(report)

    with tab_report:
        from frontend.components.report import render_report
        render_report(report)

    with tab_voice:
        from frontend.components.voice_input import render_voice_input
        render_voice_input()

else:
    # Landing state — show voice demo as standalone
    tab_main, tab_voice = st.tabs(["Get Started", "Voice Demo"])

    with tab_main:
        st.info("Upload your tax documents and click **Run Orchestrator Pipeline** in the sidebar to begin.")
        st.markdown("""
        **What you need:**
        - Bank Statement (CSV)
        - AIS — Annual Information Statement (JSON)
        - Form 16 (JSON)

        **Optional:**
        - Zerodha P&L (for Schedule CG auto-population)
        - WazirX trades (for Schedule VDA auto-population)
        """)

    with tab_voice:
        from frontend.components.voice_input import render_voice_input
        render_voice_input()
