"""
ca_brief_generator.py — ReportLab PDF Generator for CA Brief.
Generates a structured, client-facing PDF summary report for CAs.
"""
from __future__ import annotations
import os
from typing import Any
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class ContextWrapper:
    """Wraps either an AgentContext or a report dict to provide uniform attribute access."""
    def __init__(self, data: Any):
        self.data = data

    def __getattr__(self, name: str) -> Any:
        if not isinstance(self.data, dict):
            try:
                return getattr(self.data, name)
            except AttributeError:
                # Map specific fields if name is different
                if name == "itr_form_recommendation":
                    return getattr(self.data, "itr_form_recommendation", {})
                raise

        # Dictionary access mapping
        if name == "ais_data":
            return self.data.get("ais_data", {})
        if name == "assessment_year":
            return self.data.get("assessment_year", "2026-27")
        if name == "itr_form_recommendation":
            return self.data.get("itr_form", {})
        if name == "regime_comparison":
            return self.data.get("regime_comparison", {})
        if name == "gross_income":
            return self.data.get("gross_income", 0.0)
        if name == "schedule_mapping":
            return self.data.get("schedule_mapping", [])
        if name == "risk_score":
            return self.data.get("risk_score", {})
        return self.data.get(name)

class CABriefGenerator:
    """Generates a professional 2-page PDF summary for tax professionals."""

    def generate_pdf(self, ctx: Any, output_path: str) -> str:
        """Create a CA Brief PDF based on the current AgentContext or report dict.
        
        Returns the absolute path to the generated PDF.
        """
        ctx_wrapped = ContextWrapper(ctx)
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Define clean, modern color scheme
        primary_color = colors.HexColor("#1A365D")   # Deep Blue
        secondary_color = colors.HexColor("#2B6CB0") # Medium Blue
        accent_color = colors.HexColor("#E53E3E")    # Red
        bg_light = colors.HexColor("#EDF2F7")        # Light Grey

        # Custom paragraph styles
        title_style = ParagraphStyle(
            name="TitleStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=primary_color,
            spaceAfter=15
        )
        
        header_style = ParagraphStyle(
            name="HeaderStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=primary_color,
            spaceBefore=15,
            spaceAfter=10
        )

        text_bold_style = ParagraphStyle(
            name="TextBoldStyle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.black
        )

        text_style = ParagraphStyle(
            name="TextStyle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.black,
            leading=14
        )

        story = []

        # Header Title
        story.append(Paragraph("FinITR-AI v3 — CA Brief Report", title_style))
        story.append(Spacer(1, 10))

        # ────────────────────── SECTION 1: Client Profile ──────────────────────
        story.append(Paragraph("Section 1: Client Profile Summary", header_style))
        
        pan = ctx_wrapped.ais_data.get("pan", "ABCDE1234F")
        masked_pan = pan[:5] + "****" + pan[-1] if len(pan) >= 10 else pan
        ay = ctx_wrapped.assessment_year
        form_recom = ctx_wrapped.itr_form_recommendation.get("recommended_form", "ITR-2")
        regime_recom = ctx_wrapped.regime_comparison.get("recommended", "new").upper()
        savings = ctx_wrapped.regime_comparison.get("savings", 0.0)

        profile_data = [
            [
                Paragraph("<b>Client Name:</b>", text_style), 
                Paragraph(ctx_wrapped.ais_data.get("name", "Arjun Kumar Sharma"), text_style),
                Paragraph("<b>Assessment Year:</b>", text_style),
                Paragraph(ay, text_style)
            ],
            [
                Paragraph("<b>PAN:</b>", text_style),
                Paragraph(masked_pan, text_style),
                Paragraph("<b>Recommended Form:</b>", text_style),
                Paragraph(form_recom, text_style)
            ],
            [
                Paragraph("<b>Regime Verdict:</b>", text_style),
                Paragraph(f"{regime_recom} (Saves Rs {savings:,.2f})", text_style),
                Paragraph("<b>Gross Income:</b>", text_style),
                Paragraph(f"Rs {ctx_wrapped.gross_income:,.2f}", text_style)
            ]
        ]
        
        profile_table = Table(profile_data, colWidths=[100, 160, 120, 140])
        profile_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_light),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ]))
        
        story.append(profile_table)
        story.append(Spacer(1, 15))

        # ────────────────────── SECTION 2: Schedule-wise Filing Map ──────────────────────
        story.append(Paragraph("Section 2: Schedule-wise Filing Map", header_style))

        # Table headers
        table_headers = [
            Paragraph("<b>Schedule</b>", text_bold_style),
            Paragraph("<b>Filing Item</b>", text_bold_style),
            Paragraph("<b>Amount (Rs)</b>", text_bold_style),
            Paragraph("<b>Section</b>", text_bold_style),
            Paragraph("<b>TDS Credit (Rs)</b>", text_bold_style),
            Paragraph("<b>Source</b>", text_bold_style)
        ]

        table_rows = [table_headers]

        # Add mapping entries
        for mapping in ctx_wrapped.schedule_mapping:
            amt = mapping.get("amount", 0.0)
            tds = mapping.get("tds_credit", 0.0)
            
            # Format TDS credit/section label
            tds_section = mapping.get("tds_section", "")
            tds_str = f"{tds:,.2f}"
            if tds_section:
                tds_str += f" ({tds_section})"

            table_rows.append([
                Paragraph(mapping.get("schedule", "OS"), text_style),
                Paragraph(mapping.get("item", "Other Sources"), text_style),
                Paragraph(f"{amt:,.2f}", text_style),
                Paragraph(mapping.get("section", ""), text_style),
                Paragraph(tds_str, text_style),
                Paragraph(mapping.get("source", "ais"), text_style),
            ])

        map_table = Table(table_rows, colWidths=[90, 130, 90, 60, 90, 100])
        map_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
        ]))
        
        story.append(map_table)
        story.append(Spacer(1, 15))

        # ────────────────────── SECTION 3: Notice Risk & Audit Flags ──────────────────────
        story.append(Paragraph("Section 3: Audit Flags & Notice Risks", header_style))

        risk_score = ctx_wrapped.risk_score.get("total_score", 0)
        risk_level = ctx_wrapped.risk_score.get("risk_level", "LOW")
        
        risk_text = f"<b>Notice Risk Index:</b> {risk_score}/100 ({risk_level})"
        story.append(Paragraph(risk_text, text_bold_style))
        story.append(Spacer(1, 5))

        risk_rows = []
        breakdown = ctx_wrapped.risk_score.get("breakdown", [])
        for item in breakdown:
            risk_rows.append([
                Paragraph(f"⚠️ <b>{item['item']}</b>", text_style),
                Paragraph(f"Score Weight: <b>+{item['weight']}</b>", text_style),
                Paragraph(item["reason"], text_style),
            ])

        if risk_rows:
            risk_table = Table(risk_rows, colWidths=[150, 100, 270])
            risk_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FFF5F5") if risk_score >= 50 else colors.HexColor("#FFFFF0")),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#FED7D7") if risk_score >= 50 else colors.HexColor("#FEFCBF")),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('TOPPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(risk_table)
        else:
            story.append(Paragraph("No major notice risks or document discrepancies were flagged by AuditorAgent.", text_style))

        # Build PDF document
        doc.build(story)
        return output_path
