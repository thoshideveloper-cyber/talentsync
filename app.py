import pandas as pd
import streamlit as st
from pathlib import Path

from talentsync.llm import extract

RESULTS_PATH = Path("results.csv")

st.set_page_config(page_title="TalentSync", layout="wide")
st.title("TalentSync — Job Description Intelligence")
st.caption("Paste any job ad — watch it normalize live.")

# ── Results table ────────────────────────────────────────────────────────────
st.header("Batch Results")
if RESULTS_PATH.exists():
    df = pd.read_csv(RESULTS_PATH)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total rows", len(df))
    col2.metric("Verified quotes", int(df["is_verified"].sum()))
    col3.metric("Audit mismatches", int(df["audit_mismatch"].sum()))
    col4.metric("Failed extractions", int((df["status"] == "failed").sum()))

    show_cols = ["company", "title", "city", "canonical_label", "ai_seniority",
                 "skills", "summary", "is_verified", "audit_mismatch", "status"]
    st.dataframe(df[show_cols], use_container_width=True, height=400)
else:
    st.info("No results yet — run `python -m talentsync.pipeline` to generate results.csv")

st.divider()

# ── Live paste box ────────────────────────────────────────────────────────────
st.header("Try It Live")
jd_text = st.text_area(
    "Paste a job description here:",
    height=300,
    placeholder="Senior Backend Engineer, Bengaluru. 6+ years…",
)

if st.button("Extract", type="primary") and jd_text.strip():
    with st.spinner("Calling Groq / Llama-3.3-70b…"):
        result = extract(jd_text.strip())

    if result is None:
        st.error("Extraction failed after 3 attempts. Check your GROQ_API_KEY or try again.")
    else:
        is_verified = result.raw_text_justification.lower() in jd_text.lower()
        audit_col, verify_col = st.columns(2)
        verify_col.metric("Justification verified", "Yes" if is_verified else "No")

        c1, c2 = st.columns([1, 2])
        with c1:
            st.subheader("Seniority")
            st.write(f"**{result.seniority_level.value}**")
            st.subheader("Skills")
            for skill in result.required_skills:
                st.write(f"- {skill}")
        with c2:
            st.subheader("Summary")
            st.write(result.one_line_summary)
            st.subheader("Justification quote")
            st.info(f'"{result.raw_text_justification}"')
