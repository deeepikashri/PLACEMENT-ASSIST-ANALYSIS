"""
AI-Powered Placement Job Fit & Skill Gap Analyzer
Main Streamlit application entry point.

Run with:
    streamlit run app.py

Prerequisite one-time setup:
    pip install -r requirements.txt
    python models/generate_dataset.py
    python models/train_model.py
"""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.paths import ensure_directories, MODEL_PATH  # noqa: E402
from database.database import init_database  # noqa: E402
from database.seed_data import run_seed  # noqa: E402
from pages import jobs, candidate, analysis, history  # noqa: E402


st.set_page_config(
    page_title="Placement Job Fit & Skill Gap Analyzer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def bootstrap():
    """One-time setup: ensure folders/DB exist and seed sample data."""
    ensure_directories()
    init_database()
    run_seed()
    return True


bootstrap()


def render_home():
    st.title("🎯 AI-Powered Placement Job Fit & Skill Gap Analyzer")
    st.markdown(
        """
Welcome! This tool evaluates **how well your resume and skillset match the job roles in the
placement database**, automatically predicts your **best suited job role**, and estimates your
selection probability for it using a trained machine learning model. You can also compare your
profile against any one specific role by hand.

### How it works
1. **Upload your Resume** (PDF) — text is extracted automatically, with OCR fallback for scanned PDFs.
2. **Review your extracted profile** and confirm your skill proficiency levels.
3. **Find Your Best Suited Role** — every job role is scored automatically; the best match is
   shown first, along with its selection probability and stats.
4. **(Optional) Compare Against a Specific Job Role** — pick any one role by hand for a
   detailed skill match %, skill gaps, and ML-based selection probability.
5. **View improvement suggestions** to close your skill gaps.

Use the sidebar to navigate between pages.
        """
    )

    if not os.path.exists(MODEL_PATH):
        st.warning(
            "⚠️ No trained ML model was found yet. Selection-probability predictions will not work "
            "until you run:\n\n"
            "```\npython models/generate_dataset.py\npython models/train_model.py\n```",
            icon="⚠️",
        )
    else:
        st.success("✅ ML model loaded and ready.")

    col1, col2, col3 = st.columns(3)
    from database import database as db
    col1.metric("Jobs Available", len(db.get_all_jobs()))
    col2.metric("Skills Tracked", len(db.get_all_skills()))
    col3.metric("Scope", "1 Candidate vs All Jobs")


def render_about():
    st.title("ℹ️ About This Application")
    st.markdown(
        """
**AI-Powered Placement Job Fit & Skill Gap Analyzer**

This application evaluates **one candidate against the job roles in the placement
database**, automatically surfacing that candidate's best-suited role — it is
**not** a candidate ranking system or recruiter shortlist tool (it never ranks
multiple candidates against each other; the ranking here is roles for one
candidate).

**Technology stack:** Python, Streamlit, MySQL, PyMuPDF, Tesseract OCR (fallback),
scikit-learn, Pandas, NumPy, Plotly, Joblib.

**Design principle:** Deterministic rule-based logic is used for skill extraction,
skill gap calculation, and match percentages. Machine learning is used **only**
for the selection-probability prediction, since selection outcomes depend on
non-linear interactions between skills, experience, projects and certifications
that a fixed formula cannot capture as well.

**Disclaimer:** Selection probability is a statistical estimate, not a
guaranteed hiring outcome.
        """
    )


PAGES = {
    "🏠 Home": render_home,
    "🏢 Placement Organization / Job Management": jobs.render,
    "📄 Candidate Resume Analysis": candidate.render,
    "🎯 Job Fit Analysis": analysis.render,
    "🕒 Prediction History": history.render,
    "ℹ️ About": render_about,
}


def main():
    st.sidebar.title("🎯 Navigation")
    choice = st.sidebar.radio("Go to", list(PAGES.keys()), label_visibility="collapsed")
    st.sidebar.divider()
    st.sidebar.caption(
        "Local prototype — no authentication. "
        "Uploaded resumes are processed in-memory and not stored permanently."
    )

    PAGES[choice]()


if __name__ == "__main__":
    main()
