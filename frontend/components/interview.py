"""
interview.py — ITR Assist Wizard tab component.
"""
import streamlit as st
import pandas as pd


_CATEGORY_ICONS = {
    "crypto": "🪙",
    "capital_gains": "📈",
    "freelance": "💻",
    "cash_deposit": "💵",
    "interest": "🏦",
}


def render_interview(report: dict):
    """Render the ITR Assist Wizard tab."""
    st.subheader("ITR Assist Wizard")

    # ── ITR Form Recommendation banner ──
    itr_form = report.get("itr_form", {})
    rec_form = itr_form.get("recommended_form", "")
    reason = itr_form.get("reason", "")

    if rec_form:
        danger_forms = ("ITR-2", "ITR-3")
        bg = "#dc3545" if rec_form in danger_forms else "#28a745"
        st.markdown(f"""
        <div style="background:{bg}; color:white; padding:16px; border-radius:8px; margin-bottom:16px;">
            <h3 style="margin:0;">You MUST file: {rec_form}</h3>
            <p style="margin:6px 0 0; opacity:0.9;">{reason}</p>
        </div>
        """, unsafe_allow_html=True)

    required_schedules = itr_form.get("required_schedules", [])
    if required_schedules:
        st.markdown("**Required Schedules:** " + " | ".join(f"`{s}`" for s in required_schedules))

    blocked = itr_form.get("blocked_forms", {})
    if blocked:
        with st.expander("Why you can't use simpler forms"):
            for form, blockers in blocked.items():
                st.write(f"**{form}** blocked by: {', '.join(blockers)}")

    st.markdown("---")

    # ── Interview Questions ──
    questions = report.get("interview_questions", [])
    if not questions:
        questions = report.get("reconciliation", {}).get("interview_questions", [])

    if questions:
        st.markdown("### Answer These Questions to Finalize Your Return")
        st.caption("The following questions were triggered by anomalies detected in your uploaded documents.")

        updated_answers = {}
        for q in questions:
            q_id = q.get("id", "")
            q_text = q.get("question", "")
            q_ctx = q.get("context", "")
            q_type = q.get("input_type", "number")
            q_schedule = q.get("itr_schedule", "")
            q_category = q.get("category", "")
            required_q = q.get("required", False)

            icon = _CATEGORY_ICONS.get(q_category, "❓")

            with st.container():
                st.markdown(f"#### {icon} {q_text}")
                if q_ctx:
                    st.info(f"Evidence: {q_ctx}")
                if q_schedule:
                    st.caption(f"ITR Schedule: `{q_schedule}`")

                current_val = st.session_state.get("interview_answers", {}).get(q_id)
                label_suffix = " *" if required_q else ""

                if q_type == "number":
                    val = st.number_input(
                        f"Enter amount (₹){label_suffix}",
                        min_value=0.0,
                        value=float(current_val) if current_val else 0.0,
                        key=f"q_{q_id}",
                        step=1000.0,
                    )
                elif q_type == "file_or_number":
                    val = st.number_input(
                        f"Enter cost of acquisition / capital gains (₹){label_suffix}",
                        min_value=0.0,
                        value=float(current_val) if current_val else 0.0,
                        key=f"q_{q_id}",
                        step=1000.0,
                    )
                elif q_type == "boolean":
                    val = st.checkbox(
                        "Yes, this is professional/freelance income (Section 44ADA)",
                        value=bool(current_val) if current_val else False,
                        key=f"q_{q_id}",
                    )
                elif q_type == "confirm_or_edit":
                    val = st.number_input(
                        f"Confirm or edit amount (₹)",
                        min_value=0.0,
                        value=float(current_val) if current_val else 0.0,
                        key=f"q_{q_id}",
                        step=100.0,
                    )
                else:
                    val = st.text_input(
                        f"Explain the source{label_suffix}",
                        value=str(current_val) if current_val else "",
                        key=f"q_{q_id}",
                    )

                updated_answers[q_id] = val
                st.markdown("---")

        if st.button("Save Answers & Re-run Pipeline", type="primary", use_container_width=True):
            if "interview_answers" not in st.session_state:
                st.session_state["interview_answers"] = {}
            st.session_state["interview_answers"].update(updated_answers)
            st.rerun()
    else:
        st.success("All information reconciled. No further interview questions needed.")

    # ── Schedule Mapping Table ──
    schedule_mapping = report.get("schedule_mapping", [])
    if schedule_mapping:
        st.markdown("### Schedule-wise Filing Map")
        df = pd.DataFrame(schedule_mapping)
        display_cols = [c for c in ["item", "schedule", "section", "amount", "tds_credit", "tds_section", "source"] if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True)
