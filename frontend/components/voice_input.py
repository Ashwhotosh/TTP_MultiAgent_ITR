"""
voice_input.py — Voice / Hinglish input demo component.
Parses Hindi/Hinglish financial text into structured data.
DEMO-ONLY quality — designed for a 30-second wow moment in the viva.
"""
import json
import re
import streamlit as st


_EXAMPLE = (
    "मेरी salary 22 lakh है, Zerodha pe 85 hazaar ka equity sale kiya, "
    "WazirX pe crypto bhi trade kiya, aur Upwork se 85k freelance income aayi"
)


def _parse_hinglish(text: str) -> dict:
    """Parse Hindi/Hinglish text using Ollama, with regex fallback."""
    prompt = (
        "Extract financial information from this Hindi/Hinglish text. "
        "Return ONLY valid JSON with keys: gross_income (number in rupees), "
        "equity_sales (number), crypto_trades (boolean), freelance_income (number). "
        f"Use 0/false for missing. Text: {text}"
    )
    try:
        from tools.ollama_client import chat as llm_chat
        content = llm_chat(prompt=prompt)
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
    except Exception:
        pass

    # Regex fallback
    result = {"gross_income": 0, "equity_sales": 0, "crypto_trades": False, "freelance_income": 0}

    salary_m = re.search(r'salary\s+(\d+(?:\.\d+)?)\s*(lakh|lacs?)\b', text, re.IGNORECASE)
    if salary_m:
        result["gross_income"] = int(float(salary_m.group(1)) * 100000)

    equity_m = re.search(r'(\d+(?:\.\d+)?)\s*(hazaar|k|lakh)?\s*(?:ka\s+)?(?:equity|zerodha|sale)', text, re.IGNORECASE)
    if equity_m:
        amt = float(equity_m.group(1))
        unit = (equity_m.group(2) or "").lower()
        if unit in ("hazaar", "k"):
            amt *= 1000
        elif unit == "lakh":
            amt *= 100000
        result["equity_sales"] = int(amt)

    freelance_m = re.search(r'(\d+(?:\.\d+)?)\s*(k|hazaar|lakh)?\s*(?:freelance|upwork)', text, re.IGNORECASE)
    if freelance_m:
        amt = float(freelance_m.group(1))
        unit = (freelance_m.group(2) or "").lower()
        if unit in ("k", "hazaar"):
            amt *= 1000
        result["freelance_income"] = int(amt)

    if re.search(r'crypto|wazirx|bitcoin|btc|vda|coinswitch', text, re.IGNORECASE):
        result["crypto_trades"] = True

    return result


def render_voice_input():
    """Render the Voice Input Demo tab."""
    st.subheader("Voice Input Demo — Hinglish")
    st.caption("Speak or type financial details in Hindi/Hinglish. The AI extracts structured data automatically.")

    st.markdown("""
> **Example:**
> *"मेरी salary 22 lakh है, Zerodha pe 85 hazaar ka equity sale kiya,
> WazirX pe crypto bhi trade kiya, aur Upwork se 85k freelance income aayi"*
    """)

    # Try audio_input (Streamlit 1.33+)
    try:
        audio = st.audio_input("Click to record (Hindi/Hinglish)")
        if audio:
            st.audio(audio)
            st.info("Audio captured. Whisper transcription requires `ollama pull whisper` — use text input below as fallback.")
    except AttributeError:
        st.caption("Audio input requires Streamlit 1.33+. Use text input below.")

    user_text = st.text_area(
        "Or type your details here (Hindi, Hinglish, or English):",
        value=_EXAMPLE,
        height=100,
    )

    if st.button("Parse Financial Details", type="primary", use_container_width=True):
        if user_text.strip():
            with st.spinner("Parsing with AI..."):
                parsed = _parse_hinglish(user_text)

            st.success("Financial details extracted!")

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.metric("Gross Income", f"₹{parsed.get('gross_income', 0):,.0f}")
                st.metric("Freelance Income", f"₹{parsed.get('freelance_income', 0):,.0f}")
            with col_p2:
                st.metric("Equity Sales", f"₹{parsed.get('equity_sales', 0):,.0f}")
                st.metric("Crypto Trades", "Yes 🪙" if parsed.get("crypto_trades") else "No")

            st.json(parsed)
            st.session_state["_voice_parsed"] = parsed

            if st.button("Auto-fill into Pipeline", key="autofill_btn"):
                if "interview_answers" not in st.session_state:
                    st.session_state["interview_answers"] = {}
                if parsed.get("gross_income"):
                    st.session_state["voice_gross_income"] = float(parsed["gross_income"])
                if parsed.get("equity_sales"):
                    st.session_state["interview_answers"]["capital_gains_proceeds"] = float(parsed["equity_sales"])
                if parsed.get("freelance_income"):
                    st.session_state["interview_answers"]["freelance_amount"] = float(parsed["freelance_income"])
                st.success("Auto-filled! Upload documents and run the pipeline.")
        else:
            st.warning("Please enter some text first.")
