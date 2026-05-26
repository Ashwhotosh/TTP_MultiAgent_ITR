"""
dashboard.py — Dashboard & Risk tab component.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def render_risk_gauge(score: int, level: str):
    bar_color = "darkred" if score > 70 else ("orange" if score > 40 else "green")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": f"Notice Risk Score<br><span style='font-size:15px;color:gray'>{level}</span>"},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "darkblue"},
            "bar": {"color": bar_color},
            "bgcolor": "white",
            "borderwidth": 2,
            "bordercolor": "gray",
            "steps": [
                {"range": [0, 20], "color": "#d4edda"},
                {"range": [20, 50], "color": "#fff3cd"},
                {"range": [50, 75], "color": "#f8d7da"},
                {"range": [75, 100], "color": "#dc3545"},
            ],
        }
    ))
    fig.update_layout(height=270, margin=dict(l=20, r=20, t=60, b=20))
    st.plotly_chart(fig, use_container_width=True)


def _color_row(row):
    status = str(row.get("Status", row.get("match_status", "")))
    if status == "confirmed":
        return ["background-color: #d4edda; color: #155724"] * len(row)
    elif status in ("ais_only", "bank_only"):
        return ["background-color: #fff3cd; color: #856404"] * len(row)
    elif status == "mismatch":
        return ["background-color: #f8d7da; color: #721c24"] * len(row)
    return [""] * len(row)


def render_dashboard(report: dict):
    """Render the Dashboard & Risk tab."""
    st.subheader("Notice Risk & Reconciliation Dashboard")

    risk_score = report.get("risk_score", {}).get("total_score", 0)
    risk_level = report.get("risk_score", {}).get("risk_level", "LOW")
    anomalies = report.get("anomalies", [])
    gross = report.get("gross_income", 0)
    comp = report.get("regime_comparison", {})
    new_tax = comp.get("new_regime", {}).get("total_tax_liability", 0) if comp else 0
    old_tax = comp.get("old_regime", {}).get("total_tax_liability", 0) if comp else 0
    estimated_tax = min(new_tax, old_tax) if (new_tax and old_tax) else (new_tax or old_tax)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Gross Income", f"₹{gross:,.0f}")
    with col2:
        st.metric("Flagged Transactions", len(anomalies))
    with col3:
        st.metric("Est. Tax Liability", f"₹{estimated_tax:,.0f}")
    with col4:
        color_map = {"LOW": "normal", "MEDIUM": "normal", "HIGH": "off", "CRITICAL": "off"}
        st.metric("Notice Risk Score", f"{risk_score}/100", delta=risk_level,
                  delta_color=color_map.get(risk_level, "normal"))

    # ML Notice Predictor metric card
    with col5:
        pred = report.get("notice_prediction")
        if pred:
            prob = pred["notice_probability"]
            tier = pred["risk_tier"]
            color = "🔴" if prob > 0.7 else "🟡" if prob > 0.4 else "🟢"
            st.metric(
                f"{color} ML Notice Probability",
                f"{prob:.1%}",
                tier,
            )
        else:
            st.metric("ML Notice Probability", "N/A", "Model not trained")

    st.markdown("---")

    col_gauge, col_breakdown = st.columns([1, 2])
    with col_gauge:
        render_risk_gauge(risk_score, risk_level)

    with col_breakdown:
        st.markdown("#### Risk Contributors")
        breakdown = report.get("risk_score", {}).get("breakdown", [])
        if breakdown:
            for b in breakdown:
                weight = b.get("weight", 0)
                icon = "🔴" if weight >= 20 else ("🟡" if weight >= 10 else "🟢")
                st.write(f"{icon} **{b['item']}** (+{weight}): *{b['reason']}*")
            with st.expander("Full risk breakdown table"):
                st.dataframe(pd.DataFrame(breakdown), use_container_width=True)
        else:
            st.success("No notice risk indicators detected.")

    st.markdown("---")

    # ML-based notice prediction expander
    pred = report.get("notice_prediction")
    if pred:
        with st.expander("🤖 ML Notice Prediction Analysis", expanded=True):
            col_a, col_b = st.columns([2, 3])

            with col_a:
                st.markdown(f"### Probability: **{pred['notice_probability']:.1%}**")
                st.markdown(f"**Risk Tier**: {pred['risk_tier']}")
                st.markdown(f"**Confidence**: {pred['confidence']}")
                st.markdown(f"**Interpretation**: {pred['interpretation']}")
                st.markdown(f"**Top Risk Factors**: {', '.join(pred['top_risk_factors'])}")

            with col_b:
                import plotly.express as px

                contributions = pred.get("feature_contributions", {})
                feat_df = pd.DataFrame([
                    {
                        "Feature": k.replace("_", " ").title(),
                        "Importance": info["importance"],
                        "Value": info["value"],
                    }
                    for k, info in contributions.items()
                ]).sort_values("Importance", ascending=True)

                fig = px.bar(
                    feat_df,
                    x="Importance",
                    y="Feature",
                    orientation="h",
                    title="What's Driving Your Notice Risk",
                    text="Value",
                )
                fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

            st.caption(
                "Predictions from Gradient Boosting Classifier trained on IndianTaxBench v1.0 "
                "(100 cases, 5-fold CV AUC 0.87±0.05). Not legal advice."
            )

    st.markdown("### Unified Income Reconciliation Ledger")
    st.caption("🟢 Green = Confirmed match | 🟡 Yellow = AIS-only or Bank-only | 🔴 Red = Mismatch")

    ledger = report.get("reconciliation", {}).get("ledger", [])
    if ledger:
        df = pd.DataFrame(ledger)
        df_display = df.rename(columns={
            "item": "Income Item",
            "amount_form16": "Form 16 (₹)",
            "amount_ais": "AIS (₹)",
            "amount_bank": "Bank (₹)",
            "match_status": "Status",
            "delta": "Discrepancy (₹)",
            "itr_schedule": "Schedule",
        })
        cols = ["Income Item", "Form 16 (₹)", "AIS (₹)", "Bank (₹)", "Status", "Discrepancy (₹)", "Schedule"]
        available = [c for c in cols if c in df_display.columns]
        try:
            styled = df_display[available].style.apply(_color_row, axis=1)
            st.dataframe(styled, use_container_width=True)
        except Exception:
            st.dataframe(df_display[available], use_container_width=True)
    else:
        st.info("No reconciliation data. Upload documents and run the pipeline.")

    st.markdown("### Detected Transaction Anomalies")
    if anomalies:
        for i, a in enumerate(anomalies):
            flag = a.get("flag_type", "FLAG")
            amt = a.get("amount", 0)
            desc = a.get("description", "")[:60]
            icon = "🔴" if a.get("in_ais") else "🟡"
            with st.expander(f"{icon} {i+1}. {flag}: {desc} (₹{amt:,.0f})"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write(f"**Date:** {a.get('date', 'N/A')}")
                    st.write(f"**Amount:** ₹{amt:,.0f}")
                    st.write(f"**ITR Schedule:** {a.get('itr_schedule', 'N/A')}")
                with col_b:
                    st.write(f"**In AIS (Govt knows):** {'Yes' if a.get('in_ais') else 'No'}")
                    st.write(f"**Risk Weight:** +{a.get('risk_weight', 0)}")
                st.write(f"**Reasoning:** {a.get('reasoning', '')}")
    else:
        st.success("No high-risk transactions detected in bank statements.")
