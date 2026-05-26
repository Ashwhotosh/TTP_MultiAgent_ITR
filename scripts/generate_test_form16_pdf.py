"""Generate test Form 16 PDFs for both personas."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm

def make_form16(path, employer, tan, employee, pan, gross, basic, hra, tds, regime="new"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    std = 75000
    regime_label = "New Tax Regime (Section 115BAC)" if regime == "new" else "Old Tax Regime"
    data = [
        ["Field", "Details"],
        ["Name and address of the Employer", employer],
        ["PAN of the Deductor", "ABCDE5555F"],
        ["TAN of the Deductor", tan],
        ["Name of the Employee", employee],
        ["PAN of the Employee", pan],
        ["Assessment Year", "2026-27"],
        ["Tax Regime", regime_label],
        ["", ""],
        ["Gross Salary as per section 17(1)", f"Rs {gross:,.2f}"],
        ["  Basic Salary", f"Rs {basic:,.2f}"],
        ["  HRA Received", f"Rs {hra:,.2f}"],
        ["Standard Deduction u/s 16(ia)", f"Rs {std:,.2f}"],
        ["Income chargeable (Salary)", f"Rs {gross - std:,.2f}"],
        ["HRA Exemption u/s 10(13A)", "Rs 0.00  [Employee did not submit rent receipts]"],
        ["", ""],
        ["Gross Total Income", f"Rs {gross - std:,.2f}"],
        ["Deductions Chapter VI-A", "Rs 0.00  [New Regime - not applicable]"],
        ["Total Taxable Income", f"Rs {gross - std:,.2f}"],
        ["Total Tax Payable", f"Rs {tds:,.2f}"],
        ["Tax Deducted at Source (TDS)", f"Rs {tds:,.2f}"],
    ]
    table = Table(data, colWidths=[70*mm, 105*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    story = [
        Paragraph("FORM NO. 16", styles["Title"]),
        Paragraph("Certificate under Section 203 of the Income Tax Act, 1961", styles["Normal"]),
        Spacer(1, 8), table, Spacer(1, 8),
        Paragraph("* Computer generated Form 16 for testing purposes only. *", styles["Normal"])
    ]
    doc.build(story)
    print(f"Generated: {path}  ({Path(path).stat().st_size // 1024} KB)")

if __name__ == "__main__":
    make_form16("data/real/test_form16_arjun.pdf",
                "TECHCORP INDIA PVT LTD", "DELT12345A",
                "ARJUN KUMAR SHARMA", "ABCDE1234F",
                2200000, 880000, 352000, 182400)
    make_form16("data/real/test_form16_vikram.pdf",
                "INFOSYS BPM LIMITED", "BLRI09876K",
                "VIKRAM MEHTA", "FGHJK5678L",
                2622000, 1048800, 419520, 298400)
