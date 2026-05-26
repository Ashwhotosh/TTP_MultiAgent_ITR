import os
import json
from agents.orchestrator import Orchestrator
from outputs.ca_brief_generator import CABriefGenerator

def test_week3_integration():
    """Verify Week 3 integration of broker files and CA Brief PDF generation."""
    bank_csv = "data/synthetic/sample_bank_statement.csv"
    ais_json = "data/synthetic/sample_ais.json"
    form16_json = "data/synthetic/sample_form16.json"
    zerodha_csv = "data/synthetic/sample_zerodha_pnl.csv"
    wazirx_csv = "data/synthetic/sample_wazirx_trades.csv"

    # Verify input files exist
    assert os.path.exists(bank_csv)
    assert os.path.exists(ais_json)
    assert os.path.exists(form16_json)
    assert os.path.exists(zerodha_csv)
    assert os.path.exists(wazirx_csv)

    interview_answers = {
        "zerodha_csv": zerodha_csv,
        "wazirx_csv": wazirx_csv,
        "q_txn_017": 95000.0, # Cost of acquisition for crypto
    }

    orch = Orchestrator()
    report = orch.run(
        bank_csv=bank_csv,
        ais_json=ais_json,
        form16_json=form16_json,
        interview_answers=interview_answers
    )

    # Verify report output contains schedule mapping entries
    mapping = report.get("schedule_mapping", [])
    assert len(mapping) > 0

    # Verify we have Schedule CG and Schedule VDA entries from broker files
    cg_entries = [m for m in mapping if m.get("schedule") == "Schedule CG"]
    vda_entries = [m for m in mapping if m.get("schedule") == "Schedule VDA"]

    assert len(cg_entries) > 0, "No Schedule CG entries mapped"
    assert len(vda_entries) > 0, "No Schedule VDA entries mapped"

    # Verify total gains match expected values
    vda_summary = vda_entries[0]
    assert vda_summary["amount"] == 33000.0, f"Expected 33,000.0 VDA gains, got {vda_summary['amount']}"
    assert vda_summary["tds_credit"] == 3840.0, f"Expected 3840.0 VDA TDS, got {vda_summary['tds_credit']}"

    # Verify PDF generation
    pdf_path = "outputs/test_ca_brief.pdf"
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    generator = CABriefGenerator()
    generated_path = generator.generate_pdf(report, pdf_path)
    
    assert os.path.exists(generated_path), "CA Brief PDF was not generated"
    assert os.path.getsize(generated_path) > 0, "Generated PDF is empty"
    print("Week 3 integration test PASSED")
