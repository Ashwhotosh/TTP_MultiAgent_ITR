"""
report.py — Final Report tab component.
"""
import json
import os
import streamlit as st
import pandas as pd


def _render_ca_preview(report: dict):
    """Render a markdown preview of the CA brief."""
    gross = report.get("gross_income", 0)
    ay = report.get("assessment_year", "2026-27")
    itr_form = report.get("itr_form", {}).get("recommended_form", "N/A")
    comp = report.get("regime_comparison", {})
    recommended = comp.get("recommended", "new").upper()
    savings = comp.get("savings", 0)
    risk = report.get("risk_score", {})
    risk_score = risk.get("total_score", 0)
    risk_level = risk.get("risk_level", "LOW")
    schedules = report.get("schedule_mapping", [])

    st.markdown(f"""
---
**CA BRIEF — FinITR-AI v3**
Assessment Year: **{ay}** | ITR Form: **{itr_form}** | Regime: **{recommended} (saves ₹{savings:,.0f})**

**Gross Income:** ₹{gross:,.0f} | **Notice Risk:** {risk_score}/100 ({risk_level})

**Schedule-wise Filing Map:**
""")
    if schedules:
        for m in schedules:
            tds_str = f" | TDS: ₹{m.get('tds_credit',0):,.0f}" if m.get("tds_credit") else ""
            st.write(f"- **{m.get('schedule','?')} ({m.get('section','')})** — {m.get('item','')}: ₹{m.get('amount',0):,.0f}{tds_str}")
    st.markdown("---")


def render_report(report: dict):
    """Render the Final Report tab."""
    st.subheader("Final Report & Downloads")

    # ── CA Brief PDF ──
    st.markdown("### CA Brief PDF")
    pdf_path = "outputs/ca_brief.pdf"
    try:
        os.makedirs("outputs", exist_ok=True)
        from outputs.ca_brief_generator import CABriefGenerator
        gen = CABriefGenerator()
        gen.generate_pdf(report, pdf_path)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        st.download_button(
            label="Download CA Brief (PDF)",
            data=pdf_bytes,
            file_name=f"CA_Brief_{report.get('assessment_year', '2026-27')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.success("CA Brief PDF generated.")
    except Exception as e:
        st.error(f"PDF generation failed: {e}")

    with st.expander("Preview CA Brief (Markdown)"):
        _render_ca_preview(report)

    st.markdown("---")

    # ── ITR-2 JSON Export ──
    st.markdown("### ITR-2 JSON Export (e-filing portal)")
    try:
        from outputs.itr_json_generator import ITRJsonGenerator
        itr_json = ITRJsonGenerator().generate(report)
        itr_str = json.dumps(itr_json, indent=2, default=str)
        st.download_button(
            label="Download ITR-2 JSON (for IT portal upload)",
            data=itr_str.encode("utf-8"),
            file_name=f"ITR2_{report.get('assessment_year', '2026-27')}.json",
            mime="application/json",
            use_container_width=True,
        )
        with st.expander("Preview ITR-2 JSON structure"):
            st.json(itr_json)
    except Exception as e:
        st.warning(f"ITR JSON: {e}")

    # ── Full Report JSON ──
    st.markdown("### Full Agent Report (JSON)")
    report_str = json.dumps(report, indent=2, default=str)
    st.download_button(
        label="Download Full Report (JSON)",
        data=report_str.encode("utf-8"),
        file_name=f"FinITR_Report_{report.get('assessment_year', '2026-27')}.json",
        mime="application/json",
        use_container_width=True,
    )

    st.markdown("---")

    # ── Agent Trace ──
    st.markdown("### Agent Execution Trace")
    trace = report.get("agent_trace", [])
    iterations = report.get("iterations", 1)
    total_time = report.get("total_time_sec", 0)

    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        st.metric("Pipeline Iterations", iterations)
    with col_t2:
        st.metric("Total Runtime", f"{total_time:.1f}s")
    with col_t3:
        st.metric("Agent Invocations", len(trace))

    if trace:
        for entry in trace:
            agent = entry.get("agent", "Unknown")
            status = entry.get("status", "unknown")
            duration = entry.get("duration_sec", 0.0)
            tools = entry.get("tools_called", [])
            warnings = entry.get("warnings", [])
            errors = entry.get("errors", [])
            icon = "✅" if status == "success" else ("⚠️" if status == "needs_review" else "❌")
            with st.expander(f"{icon} {agent} ({status}) — {duration:.2f}s"):
                st.write(f"**Tools Called:** {', '.join(tools) if tools else 'none'}")
                if warnings:
                    for w in warnings:
                        st.warning(str(w))
                if errors:
                    for e in errors:
                        st.error(str(e))
    else:
        st.info("No agent trace available.")

    # ── Critic Feedback ──
    critic_feedback = report.get("critic_feedback", [])
    if critic_feedback:
        st.markdown("### CriticAgent Feedback")
        for i, fb in enumerate(critic_feedback):
            blocked = fb.get("blocked_claims", [])
            issues = fb.get("issues", [])
            with st.expander(f"Iteration {fb.get('iteration', i)+1}: {len(blocked)} blocked, {len(issues)} issues"):
                if blocked:
                    st.error(f"Blocked {len(blocked)} claim(s):")
                    for claim in blocked:
                        st.write(f"  - Section {claim.get('section', '?')}: {claim.get('reason', '')}")
                if issues:
                    st.warning(f"{len(issues)} issue(s) raised:")
                    for issue in issues:
                        st.write(f"  - {issue}")

    # ── ML Model Quality Section ──
    try:
        from pathlib import Path
        metrics_path = Path("models/notice_predictor_metrics.json")
        if metrics_path.exists():
            import json as _json
            metrics = _json.loads(metrics_path.read_text())

            with st.expander("📊 Notice Predictor Model Quality"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Test AUC", f"{metrics['test_auc']:.3f}")
                with col2:
                    st.metric("CV AUC (5-fold)", f"{metrics['cv_auc_mean']:.3f} ± {metrics['cv_auc_std']:.3f}")
                with col3:
                    st.metric("LR Baseline AUC", f"{metrics['baseline_logistic_regression_auc']:.3f}")

                st.markdown("**Confusion Matrix**")
                cm = metrics["confusion_matrix"]
                st.table([
                    {"": "Actual Negative", "Predicted Negative": cm[0][0], "Predicted Positive": cm[0][1]},
                    {"": "Actual Positive", "Predicted Negative": cm[1][0], "Predicted Positive": cm[1][1]},
                ])

                st.markdown("**Feature Importances**")
                imp_df = pd.DataFrame([
                    {"Feature": k, "Importance": v}
                    for k, v in metrics["feature_importances"].items()
                ])
                st.dataframe(imp_df, hide_index=True)
    except Exception:
        pass

    st.markdown("---")

    # ── Faithfulness Verification Summary ──
    st.markdown("### Faithfulness Verification Summary")
    verification = report.get("verification", [])
    if verification:
        faithful = sum(1 for v in verification if v.get("verdict") == "FAITHFUL")
        unverified = sum(1 for v in verification if v.get("verdict") == "UNVERIFIED")
        hallucinated = sum(1 for v in verification if v.get("verdict") == "HALLUCINATED")

        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            st.metric("FAITHFUL", faithful)
        with col_v2:
            st.metric("UNVERIFIED", unverified)
        with col_v3:
            st.metric("HALLUCINATED", hallucinated)

        with st.expander("All verification results"):
            st.dataframe(pd.DataFrame(verification), use_container_width=True)
    else:
        st.info("Faithfulness verification results not available.")
