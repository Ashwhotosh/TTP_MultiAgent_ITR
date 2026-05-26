"""Deduction Gap component for Streamlit Tab 3 (Regime Comparator)."""
import streamlit as st

def render_deduction_gap(report: dict):
    gap_report = report.get("deduction_gaps") or {}
    if not gap_report or not gap_report.get("gaps"):
        st.info("No significant unclaimed deductions detected.")
        return

    gaps = gap_report["gaps"]
    old_saving = gap_report.get("estimated_old_regime_saving", 0)
    switch_rec = gap_report.get("regime_switch_recommended", False)
    switch_sav = gap_report.get("switch_saving", 0)
    regime = gap_report.get("current_regime", "new")

    st.markdown("---")
    st.subheader("Deductions You Have Not Claimed")
    st.caption(gap_report.get("summary", ""))

    c1, c2, c3 = st.columns(3)
    c1.metric("Gaps Found", len(gaps))
    c2.metric("Potential Saving (Old Regime)", f"Rs{old_saving:,.0f}")
    if switch_rec:
        c3.metric("Regime Switch Saving", f"Rs{switch_sav:,.0f}", "Switch recommended")
    else:
        c3.metric("New Regime Saving", f"Rs{gap_report.get('estimated_new_regime_saving',0):,.0f}")

    if regime == "new":
        blocked = [g for g in gaps if g.get("blocked_under_new_regime")]
        if blocked:
            st.warning(f"{len(blocked)} deductions blocked under New Regime (HRA, 80C, 80D, 24b). "
                       "Switch to Old Regime to unlock them.")

    icons = {"HRA":"House","80GG":"House","INSURANCE":"Shield","HOME_LOAN":"Bank","INVESTMENT":"Chart"}
    for gap in gaps:
        suf = " [New Regime BLOCKED]" if gap.get("blocked_under_new_regime") else " [Both Regimes]"
        with st.expander(f"{gap['section']} - Gap Rs{gap['gap_amount']:,.0f} | Saves Rs{gap['saving_old_regime']:,.0f}{suf}", expanded=True):
            a, b = st.columns([3,2])
            with a:
                st.write(gap["description"])
                if gap.get("note"): st.info(gap["note"])
                if gap.get("caveat"): st.caption(f"Note: {gap['caveat']}")
            with b:
                st.markdown(f"- **Detected:** Rs{gap['detected_amount']:,.0f}")
                st.markdown(f"- **Claimed:** Rs{gap['claimed_amount']:,.0f}")
                st.markdown(f"- **Gap:** Rs{gap['gap_amount']:,.0f}")
                if gap.get("gap_breakdown"):
                    for sec, amt in gap["gap_breakdown"].items():
                        st.markdown(f"  - {sec}: Rs{amt:,.0f}")
