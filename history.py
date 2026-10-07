"""
Prediction History page (spec section 24).
"""

import streamlit as st

from database import database as db
from models.predict import classify_fit


def render():
    st.title("🕒 Prediction History")

    student_id = st.session_state.get("student_id", "")
    student_id_input = st.text_input("Enter your Student ID to view your analysis history", value=student_id)

    if not student_id_input.strip():
        st.info("Enter a Student ID above to view past analyses.")
        return

    student_id_input = student_id_input.strip()
    student = db.get_student(student_id_input)
    if not student:
        st.warning("No candidate found with this Student ID.")
        return

    history = db.get_prediction_history(student_id_input)
    if not history:
        st.info("No previous analyses found for this candidate yet.")
        return

    st.success(f"Showing history for **{student['name'] or student_id_input}** ({student_id_input})")

    rows = []
    for h in history:
        rows.append({
            "Date": h["created_at"],
            "Job Title": h["job_title"],
            "Company": h["company_name"],
            "Overall Match %": h["match_percentage"],
            "Mandatory Match %": h["mandatory_match_percentage"],
            "Selection Probability %": h["selection_probability"],
            "Fit": classify_fit(h["selection_probability"]),
        })

    st.dataframe(rows, use_container_width=True)

    st.divider()
    st.markdown("#### Selection Probability Trend")
    if len(history) > 1:
        import plotly.graph_objects as go
        dates = [h["created_at"] for h in reversed(history)]
        probs = [h["selection_probability"] for h in reversed(history)]
        jobs = [h["job_title"] for h in reversed(history)]
        fig = go.Figure(go.Scatter(x=dates, y=probs, mode="lines+markers", text=jobs))
        fig.update_layout(yaxis=dict(title="Selection Probability (%)", range=[0, 100]), height=350)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("Run more than one analysis to see a trend over time.")
