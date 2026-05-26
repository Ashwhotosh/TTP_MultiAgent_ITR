"""
simulator.py — Regime Comparator & CTC Simulator tab component.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def render_sankey(report: dict, nps_override: float = 0.0):
    """Render Sankey: Gross → Deductions → Taxable → Tax → TDS → Net Payable."""
    comp = report.get("regime_comparison", {})
    if not comp:
        return
    recommended = comp.get("recommended", "new")
    reg = comp.get(f"{recommended}_regime", {})
    if not reg:
        return

    gross = reg.get("gross_income", 0)
    std_ded = reg.get("standard_deduction", 0)
    base_other_ded = reg.get("total_deductions", 0)
    other_ded = max(base_other_ded, nps_override)
    taxable = max(0, gross - std_ded - other_ded)
    slab_tax = reg.get("slab_tax", 0)
    rebate = reg.get("rebate_87a", 0)
    cess = reg.get("cess", 0)
    total_tax = reg.get("total_tax_liability", 0)

    # Estimate TDS from salary TDS credit
    tds = sum(m.get("tds_credit", 0) for m in report.get("schedule_mapping", []))
    net_payable = max(0.0, total_tax - tds)

    labels = [
        "Gross Income",       # 0
        "Std Deduction",      # 1
        "Other Deductions",   # 2
        "Taxable Income",     # 3
        "Slab Tax",           # 4
        "Rebate 87A",         # 5
        "Cess (4%)",          # 6
        "Total Tax",          # 7
        "TDS Credit",         # 8
        "Net Tax Payable",    # 9
    ]
    node_colors = [
        "#1a73e8", "#34a853", "#fbbc04",
        "#4285f4", "#ea4335", "#34a853",
        "#ff6d00", "#d93025", "#0f9d58", "#e91e63",
    ]

    sources = [0, 0, 0, 3, 4, 4, 7, 7]
    targets = [1, 2, 3, 4, 5, 6, 8, 9]
    values = [
        max(1, std_ded),
        max(1, other_ded),
        max(1, taxable),
        max(1, slab_tax),
        max(1, rebate),
        max(1, cess),
        max(1, min(tds, total_tax)),
        max(1, net_payable),
    ]

    fig = go.Figure(go.Sankey(
        node=dict(label=labels, color=node_colors, pad=15, thickness=20),
        link=dict(
            source=sources, target=targets, value=values,
            color=["rgba(100,100,100,0.12)"] * len(sources),
        ),
    ))
    fig.update_layout(
        title_text=f"Tax Money Flow — {recommended.title()} Regime",
        font_size=11, height=420,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_simulator(report: dict):
    """Render the Regime Comparator & CTC Simulator tab."""
    st.subheader("Tax Regime Comparator & CTC Simulator")

    comp = report.get("regime_comparison", {})
    if not comp:
        st.info("Regime comparison data unavailable. Run the pipeline first.")
        return

    recommended = comp.get("recommended", "new")
    savings = comp.get("savings", 0.0)
    reason = comp.get("reason", "")
    old = comp.get("old_regime", {})
    new = comp.get("new_regime", {})

    # Recommendation banner
    rec_name = "New Regime (Section 115BAC)" if recommended == "new" else "Old Regime"
    banner_color = "#1a73e8" if recommended == "new" else "#0f9d58"
    st.markdown(f"""
    <div style="background:{banner_color}; color:white; padding:18px; border-radius:8px; margin-bottom:16px;">
        <h3 style="margin:0;">Recommended: {rec_name}</h3>
        <p style="font-size:18px; margin:8px 0 4px;">Savings: <b>₹{savings:,.0f}</b></p>
        <p style="margin:0; opacity:0.9;">{reason}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Side-by-side comparison ──
    col_old, col_new = st.columns(2)

    def _regime_box(regime_data: dict, label: str, is_rec: bool):
        border = "3px solid #1a73e8" if is_rec else "1px solid #ddd"
        badge = " ✅ Recommended" if is_rec else ""
        st.markdown(f"""
        <div style="border:{border}; border-radius:8px; padding:12px; background:#fafafa;">
        <h4 style="margin:0; color:#333;">{label}{badge}</h4>
        </div>
        """, unsafe_allow_html=True)
        if regime_data:
            total = regime_data.get("total_tax_liability", 0)
            st.metric("Total Tax Payable", f"₹{total:,.0f}")
            st.write(f"Gross Income: ₹{regime_data.get('gross_income', 0):,.0f}")
            st.write(f"Standard Deduction: ₹{regime_data.get('standard_deduction', 0):,.0f}")
            st.write(f"Total Deductions: ₹{regime_data.get('total_deductions', 0):,.0f}")
            st.write(f"Taxable Income: ₹{regime_data.get('taxable_income', 0):,.0f}")
            st.write(f"Rebate 87A: ₹{regime_data.get('rebate_87a', 0):,.0f}")
            st.write(f"Surcharge: ₹{regime_data.get('surcharge', 0):,.0f}")
            st.write(f"Cess (4%): ₹{regime_data.get('cess', 0):,.0f}")
            st.write(f"**Effective Rate: {regime_data.get('effective_rate', 0)}%**")
            if regime_data.get("marginal_relief_applied"):
                st.success("Marginal relief applied")
            deds = regime_data.get("deductions", {})
            if deds and any(v > 0 for v in deds.values()):
                st.markdown("**Deductions claimed:**")
                for k, v in deds.items():
                    if v > 0:
                        st.write(f"  - {k}: ₹{v:,.0f}")
            if regime_data.get("slab_breakdown"):
                with st.expander("Slab-wise breakdown"):
                    st.table(pd.DataFrame(regime_data["slab_breakdown"]))
        else:
            st.info("Data unavailable")

    with col_old:
        _regime_box(old, "Old Regime", recommended == "old")
    with col_new:
        _regime_box(new, "New Regime (115BAC)", recommended == "new")

    st.markdown("---")

    # ── NPS Slider ──
    st.markdown("### Employer NPS Simulator (Section 80CCD(2))")
    ctc_data = report.get("ctc_strategy", {}).get("computation", {}) or {}
    gross = report.get("gross_income", 0)
    basic = report.get("basic_salary", 0)
    max_nps = ctc_data.get("max_employer_nps", basic * 0.10 if basic else gross * 0.04)
    current_nps = ctc_data.get("current_employer_nps", 0.0)

    nps_slider_max = max(int(max_nps * 2), 500000)
    nps_val = st.slider(
        "Employer NPS Contribution (₹/year)",
        min_value=0,
        max_value=nps_slider_max,
        value=int(current_nps),
        step=5000,
        help=f"Max deductible under 80CCD(2): ₹{max_nps:,.0f} (10% of basic salary)",
    )

    new_tax_baseline = new.get("total_tax_liability", 0) if new else 0
    if gross > 0:
        try:
            from tools.calculator import CalculatorTool
            calc = CalculatorTool()
            updated = calc.calculate_new_regime_tax(gross, {"80CCD_2": float(nps_val)})
            nps_savings = max(0, new_tax_baseline - updated["total_tax_liability"])

            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("NPS Contribution", f"₹{nps_val:,.0f}")
            with col_s2:
                st.metric("Updated New Regime Tax", f"₹{updated['total_tax_liability']:,.0f}")
            with col_s3:
                st.metric("Additional Savings", f"₹{nps_savings:,.0f}",
                          delta=f"vs ₹{new_tax_baseline:,.0f} baseline")
        except Exception:
            pass

    if ctc_data:
        st.markdown("### CTC Restructuring Strategy")
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            st.metric("Max NPS Allowed", f"₹{ctc_data.get('max_employer_nps', 0):,.0f}")
        with col_c2:
            st.metric("Additional Room", f"₹{ctc_data.get('additional_nps_room', 0):,.0f}")
        with col_c3:
            st.metric("Annual Savings", f"₹{ctc_data.get('annual_savings', 0):,.0f}")
        narrative = report.get("ctc_strategy", {}).get("narrative", "")
        if narrative:
            st.info(narrative)

    # ── Sankey Diagram ──
    st.markdown("### Tax Money Flow (Sankey Diagram)")
    render_sankey(report, nps_override=float(nps_val))

    # Deduction Gap Analyzer Integration
    try:
        from frontend.components.deduction_gap import render_deduction_gap
        render_deduction_gap(report)
    except Exception as e:
        st.error(f"Failed to render deduction gaps: {e}")

