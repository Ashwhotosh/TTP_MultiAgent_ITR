"""
Generate a realistic synthetic Form 16 PDF for testing the PDF parser.
Mimics CBDT-prescribed Form 16 Part A + Part B layout.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

OUTPUT = Path("data/synthetic/sample_form16.pdf")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

styles = getSampleStyleSheet()
bold = ParagraphStyle("bold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10)
normal = ParagraphStyle("normal", parent=styles["Normal"], fontName="Helvetica", fontSize=9)
heading = ParagraphStyle("heading", parent=styles["Normal"], fontName="Helvetica-Bold",
                         fontSize=12, alignment=TA_CENTER, spaceAfter=6)
subheading = ParagraphStyle("subheading", parent=styles["Normal"], fontName="Helvetica-Bold",
                             fontSize=10, spaceBefore=8, spaceAfter=4)

def row(label, value, indent=""):
    return [Paragraph(f"{indent}{label}", normal), Paragraph(str(value), normal)]

def amt(n):
    return f"{n:,.2f}"

doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4,
                        leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=15*mm, bottomMargin=15*mm)

story = []

# ─── HEADER ───
story.append(Paragraph("FORM 16", heading))
story.append(Paragraph("Certificate under Section 203 of the Income Tax Act, 1961", heading))
story.append(Paragraph("for Tax Deducted at Source from Income Chargeable under the Head 'Salaries'", normal))
story.append(Spacer(1, 6*mm))

# ─── PART A ───
story.append(Paragraph("PART A", subheading))

part_a = [
    ["Name and address of the Employer", "TECHCORP INDIA PVT LTD, 42 MG Road, Bengaluru - 560001"],
    ["PAN of the Deductor", "AAACT1234E"],
    ["TAN of the Deductor", "BLRA12345B"],
    ["Assessment Year", "2026-27"],
    ["Period of employment", "01-04-2025 to 31-03-2026"],
    ["PAN of the Employee", "ARJPK9876Z"],
    ["Name of the Employee", "ARJUN KUMAR SHARMA"],
    ["Designation", "Senior Software Engineer"],
]

t = Table(part_a, colWidths=[80*mm, 100*mm])
t.setStyle(TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("PADDING", (0, 0), (-1, -1), 4),
]))
story.append(t)
story.append(Spacer(1, 4*mm))

# TDS Summary
story.append(Paragraph("Summary of Tax Deducted at Source", subheading))
tds_summary = [
    ["Quarter", "Quarter Ending", "TDS Deducted (Rs.)", "TDS Deposited (Rs.)"],
    ["Q1", "30-06-2025", amt(62500), amt(62500)],
    ["Q2", "30-09-2025", amt(62500), amt(62500)],
    ["Q3", "31-12-2025", amt(62500), amt(62500)],
    ["Q4", "31-03-2026", amt(62500), amt(62500)],
    ["Total", "", amt(250000), amt(250000)],
]
t2 = Table(tds_summary, colWidths=[30*mm, 40*mm, 50*mm, 50*mm])
t2.setStyle(TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
    ("PADDING", (0, 0), (-1, -1), 4),
]))
story.append(t2)
story.append(Spacer(1, 8*mm))

# ─── PART B ───
story.append(Paragraph("PART B (Annexure)", subheading))
story.append(Paragraph(
    "Statement showing particulars of perquisites, other fringe benefits or amenities "
    "and profits in lieu of salary with value thereof",
    normal
))
story.append(Spacer(1, 4*mm))

# Regime declaration
story.append(Paragraph(
    "TAX REGIME: New Tax Regime (Section 115BAC) — Employee has opted for new tax regime.",
    bold
))
story.append(Spacer(1, 4*mm))

# Salary breakdown
story.append(Paragraph("1. GROSS SALARY", subheading))
salary_table = [
    ["Component", "Amount (Rs.)"],
    ["(a) Basic Salary", amt(1320000)],
    ["    House Rent Allowance (HRA)", amt(396000)],
    ["    Special Allowance", amt(264000)],
    ["    Leave Travel Allowance (LTA)", amt(110000)],
    ["    Medical Allowance", amt(110000)],
    ["(b) Value of perquisites under section 17(2)", amt(0)],
    ["(c) Profits in lieu of salary under section 17(3)", amt(0)],
    ["Salary as per section 17(1)", amt(2200000)],
    ["Gross Salary", amt(2200000)],
]
t3 = Table(salary_table, colWidths=[120*mm, 50*mm])
t3.setStyle(TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D9E1F2")),
    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("PADDING", (0, 0), (-1, -1), 4),
]))
story.append(t3)
story.append(Spacer(1, 4*mm))

# Deductions
story.append(Paragraph("2. DEDUCTIONS", subheading))
ded_table = [
    ["Deduction", "Amount (Rs.)"],
    ["Standard Deduction under section 16(ia)", amt(75000)],
    ["Professional Tax under section 16(iii)", amt(2400)],
    ["Total Deductions", amt(77400)],
]
t4 = Table(ded_table, colWidths=[120*mm, 50*mm])
t4.setStyle(TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D9E1F2")),
    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("PADDING", (0, 0), (-1, -1), 4),
]))
story.append(t4)
story.append(Spacer(1, 4*mm))

# Income chargeable
story.append(Paragraph("3. INCOME CHARGEABLE UNDER THE HEAD 'SALARIES'", subheading))
income_table = [
    ["", "Amount (Rs.)"],
    ["Gross Salary", amt(2200000)],
    ["Less: Total Deductions", amt(77400)],
    ["Income Chargeable under Head Salaries", amt(2122600)],
    ["Gross Total Income", amt(2122600)],
    ["Total Taxable Income", amt(2122600)],
]
t5 = Table(income_table, colWidths=[120*mm, 50*mm])
t5.setStyle(TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D9E1F2")),
    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("PADDING", (0, 0), (-1, -1), 4),
]))
story.append(t5)
story.append(Spacer(1, 4*mm))

# Tax computation
story.append(Paragraph("4. TAX COMPUTATION (New Tax Regime — Section 115BAC)", subheading))
tax_table = [
    ["Particulars", "Amount (Rs.)"],
    ["Total Taxable Income", amt(2122600)],
    ["Tax on Total Income (as per new regime slabs)", amt(242800)],
    ["Add: Surcharge", amt(0)],
    ["Add: Health and Education Cess @ 4%", amt(9712)],
    ["Total Tax Payable", amt(252512)],
    ["Less: Relief under section 87A", amt(0)],
    ["Tax Deducted at Source (TDS)", amt(250000)],
    ["Balance Tax Payable / (Refundable)", amt(2512)],
]
t6 = Table(tax_table, colWidths=[120*mm, 50*mm])
t6.setStyle(TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, -2), (-1, -2), "Helvetica-Bold"),
    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ("BACKGROUND", (0, -2), (-1, -2), colors.HexColor("#D9E1F2")),
    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("PADDING", (0, 0), (-1, -1), 4),
]))
story.append(t6)
story.append(Spacer(1, 8*mm))

# Verification
story.append(Paragraph(
    "I, Rajesh Gupta, son/daughter of Ramesh Gupta, working as HR Manager in TECHCORP INDIA PVT LTD "
    "having TAN BLRA12345B do hereby certify that a sum of Rs. 2,50,000/- has been deducted and "
    "deposited to the credit of the Central Government.",
    normal
))

doc.build(story)
print(f"Generated: {OUTPUT}")
print(f"Size: {OUTPUT.stat().st_size:,} bytes")
