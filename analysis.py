"""
Job Fit Analysis page (spec sections 10-19).

Two flows live on this page now:

  PRIMARY  — "Best Suited Job Role": the candidate's profile is scored
             against every job role in the database (analysis.role_ranking)
             and the single best-fit role is surfaced automatically,
             along with its selection probability and stats. No job
             selection is required to see this.

  SECONDARY — "Compare Against a Specific Job Role": the original
             single-job workflow, kept for candidates (or placement
             staff) who want to check fit against one particular
             role by hand.

Both flows share the same deterministic + ML pipeline:
    candidate skills + job skills -> skill_gap.compare_skills (deterministic)
    -> feature_engineering.build_feature_dict
    -> models.predict.JobFitPredictor (ML — the ONLY ML step)
    -> analysis.recommendations.generate_recommendations (deterministic)
    -> persist to ml_predictions / recommendations tables
    -> render dashboard
"""

import plotly.graph_objects as go
import streamlit as st

from database import database as db
from analysis.skill_gap import compare_skills
from analysis.feature_engineering import build_feature_dict
from analysis.recommendations import generate_recommendations
from analysis.role_ranking import rank_all_jobs
from models.predict import get_predictor, classify_fit, SELECTION_DISCLAIMER, ModelNotTrainedError


def _fit_color(label: str) -> str:
    return {
        "Excellent Fit": "🟢",
        "Good Fit": "🔵",
        "Moderate Fit": "🟡",
        "Low Fit": "🔴",
    }.get(label, "⚪")


def _render_skill_level_chart(gap_result):
    skills = [r.skill_name for r in gap_result.rows]
    required = [r.required_level for r in gap_result.rows]
    candidate = [r.candidate_level for r in gap_result.rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Required Level", x=skills, y=required, marker_color="#636EFA"))
    fig.add_trace(go.Bar(name="Candidate Level", x=skills, y=candidate, marker_color="#00CC96"))
    fig.update_layout(
        barmode="group", title="Required vs Candidate Skill Levels",
        yaxis=dict(title="Level (1-5)", range=[0, 5]), height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_gap_chart(gap_result):
    skills = [r.skill_name for r in gap_result.rows]
    gaps = [r.gap for r in gap_result.rows]
    colors = ["#EF553B" if r.mandatory else "#FFA15A" for r in gap_result.rows]

    fig = go.Figure(go.Bar(x=skills, y=gaps, marker_color=colors))
    fig.update_layout(title="Skill Gap by Skill (red = mandatory)", yaxis=dict(title="Gap"), height=350)
    st.plotly_chart(fig, use_container_width=True)


def _render_gauge(value: float, title: str):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#636EFA"},
            "steps": [
                {"range": [0, 50], "color": "#FFE5E5"},
                {"range": [50, 65], "color": "#FFF4CC"},
                {"range": [65, 80], "color": "#DCE9FF"},
                {"range": [80, 100], "color": "#DFF7E5"},
            ],
        },
    ))
    fig.update_layout(height=280, margin=dict(t=40, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


def _render_ranking_chart(ranking):
    labels = [f"{e.job['job_title']} — {e.job['company_name']}" for e in reversed(ranking)]
    probs = [e.selection_probability for e in reversed(ranking)]
    colors = ["#00CC96" if i == len(ranking) - 1 else "#636EFA" for i in range(len(ranking))]

    fig = go.Figure(go.Bar(x=probs, y=labels, orientation="h", marker_color=colors))
    fig.update_layout(
        title="Selection Probability Across All Job Roles",
        xaxis=dict(title="Selection Probability (%)", range=[0, 100]),
        height=max(280, 40 * len(labels)),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_fit_stats(gap_result, features, selection_probability, fit_label, job):
    """Shared stats block used by both the best-role card and the specific-job section."""
    col1, col2, col3 = st.columns(3)
    col1.metric("Selection Probability", f"{selection_probability:.1f}%")
    col2.metric("Overall Skill Match", f"{gap_result.match_percentage:.1f}%")
    col3.metric("Mandatory Skill Match", f"{gap_result.mandatory_match_percentage:.1f}%")

    st.markdown(f"### Fit Classification: {_fit_color(fit_label)} **{fit_label}**")
    st.caption(SELECTION_DISCLAIMER)

    col4, col5 = st.columns(2)
    with col4:
        st.progress(min(int(gap_result.match_percentage), 100), text="Overall Skill Match")
    with col5:
        st.progress(min(int(selection_probability), 100), text="Selection Probability")

    st.markdown("#### Experience")
    exp_col1, exp_col2, exp_col3 = st.columns(3)
    exp_col1.metric("Required", f"{job['minimum_experience']} yr")
    exp_col2.metric("Candidate", f"{features['student_experience']} yr")
    exp_col3.metric("Gap", f"{features['experience_gap']} yr")

    st.divider()
    col_charts1, col_charts2 = st.columns(2)
    with col_charts1:
        _render_gauge(gap_result.match_percentage, "Overall Skill Match")
    with col_charts2:
        _render_gauge(selection_probability, "Selection Probability")

    _render_skill_level_chart(gap_result)
    _render_gap_chart(gap_result)

    st.divider()
    col_matched, col_missing = st.columns(2)
    with col_matched:
        st.markdown("#### ✅ Matched Skills")
        if gap_result.matched_skills:
            for s in gap_result.matched_skills:
                st.markdown(f"- ✓ {s}")
        else:
            st.write("_None_")
    with col_missing:
        st.markdown("#### ❌ Missing / Gap Skills")
        if gap_result.missing_skills:
            for s in gap_result.missing_skills:
                st.markdown(f"- ✗ {s}")
        else:
            st.write("_None — full match!_")

    st.markdown("#### Skill Gap Detail")
    st.table([
        {
            "Skill": r.skill_name,
            "Required": r.required_level,
            "Candidate": r.candidate_level,
            "Gap": r.gap,
            "Mandatory": "Yes" if r.mandatory else "No",
            "Status": r.status,
        }
        for r in gap_result.rows
    ])

    st.markdown(f"**Projects:** {features['projects']}  |  **Certifications:** {features['certifications']}")


def _render_best_role_section(student_id, student, candidate_skills, projects, certifications, jobs):
    st.header("🏆 Best Suited Job Role")
    st.caption(
        "Your profile is automatically scored against every job role in the database. "
        "This is your headline prediction — no job selection needed."
    )

    if st.button("🏆 Find My Best Suited Role", type="primary"):
        try:
            ranking = rank_all_jobs(
                student=student,
                candidate_skills=candidate_skills,
                projects_count=len(projects),
                certifications_count=len(certifications),
                jobs=jobs,
            )
        except ModelNotTrainedError as exc:
            st.error(str(exc))
            return

        if not ranking:
            st.warning("No job roles have required skills configured yet. Ask the placement organization to configure one.")
            return

        best = ranking[0]
        recommendations = generate_recommendations(best.gap_result)

        db.save_prediction(
            student_id=student_id, job_id=best.job["job_id"],
            match_percentage=best.gap_result.match_percentage,
            mandatory_match_percentage=best.gap_result.mandatory_match_percentage,
            average_skill_gap=best.gap_result.average_skill_gap,
            experience_gap=best.features["experience_gap"],
            projects=len(projects), certifications=len(certifications),
            selection_probability=best.selection_probability,
            prediction=1 if best.selection_probability >= 50 else 0,
        )
        db.save_recommendations(student_id, best.job["job_id"], [
            {"skill_id": db.get_skill_id_by_name(r["skill_name"]) if r["skill_name"] else None,
             "priority": r["priority"], "recommendation": r["recommendation"]}
            for r in recommendations
        ])

        st.session_state["best_role_result"] = {
            "ranking": ranking, "recommendations": recommendations,
        }

    result = st.session_state.get("best_role_result")
    if not result:
        st.info("Click **Find My Best Suited Role** to generate your prediction.")
        return

    ranking = result["ranking"]
    recommendations = result["recommendations"]
    best = ranking[0]

    st.divider()
    st.subheader(f"🥇 Best Fit: {best.job['job_title']} — {best.job['company_name']}")
    _render_fit_stats(best.gap_result, best.features, best.selection_probability, best.fit_label, best.job)

    if len(ranking) > 1:
        st.divider()
        st.markdown("#### 📊 How This Compares to Other Roles")
        _render_ranking_chart(ranking[:10])
        st.table([
            {
                "Rank": i + 1,
                "Job Role": e.job["job_title"],
                "Company": e.job["company_name"],
                "Selection Probability": f"{e.selection_probability:.1f}%",
                "Overall Skill Match": f"{e.gap_result.match_percentage:.1f}%",
                "Fit": e.fit_label,
            }
            for i, e in enumerate(ranking)
        ])

    st.divider()
    st.markdown("### 💡 Improvement Suggestions (for your best-fit role)")
    if not recommendations:
        st.success("No skill gaps detected for this role — great job!")
    else:
        priority_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡"}
        for rec in recommendations:
            st.markdown(f"{priority_icon.get(rec['priority'], '⚪')} **[{rec['priority']}]** {rec['recommendation']}")


def _render_specific_job_section(student_id, student, candidate_skills, projects, certifications, jobs):
    with st.expander("🔍 Compare Against a Specific Job Role (optional)", expanded=False):
        st.caption(
            "Prefer to check fit against one particular role by hand instead of your "
            "auto-predicted best fit above? Pick it here."
        )

        job_id = st.session_state.get("selected_job_id")
        job_options = {f"{j['job_title']} — {j['company_name']}": j["job_id"] for j in jobs}
        default_index = 0
        if job_id:
            ids = list(job_options.values())
            if job_id in ids:
                default_index = ids.index(job_id)
        selected_label = st.selectbox("Job to analyze against", list(job_options.keys()), index=default_index)
        job_id = job_options[selected_label]
        job = db.get_job(job_id)
        job_skills = db.get_job_skills(job_id)

        if not job_skills:
            st.error("This job has no required skills defined yet. Ask the placement organization to configure it.")
            return

        if st.button("🔍 Analyze Job Fit", type="primary"):
            gap_result = compare_skills(job_skills, candidate_skills)
            features = build_feature_dict(
                gap_result=gap_result,
                student_experience=student["experience_years"],
                required_experience=job["minimum_experience"],
                projects_count=len(projects),
                certifications_count=len(certifications),
            )

            try:
                predictor = get_predictor()
                selection_probability = predictor.predict_probability(features)
            except ModelNotTrainedError as exc:
                st.error(str(exc))
                return

            fit_label = classify_fit(selection_probability)
            recommendations = generate_recommendations(gap_result)

            db.save_prediction(
                student_id=student_id, job_id=job_id,
                match_percentage=gap_result.match_percentage,
                mandatory_match_percentage=gap_result.mandatory_match_percentage,
                average_skill_gap=gap_result.average_skill_gap,
                experience_gap=features["experience_gap"],
                projects=len(projects), certifications=len(certifications),
                selection_probability=selection_probability,
                prediction=1 if selection_probability >= 50 else 0,
            )
            db.save_recommendations(student_id, job_id, [
                {"skill_id": db.get_skill_id_by_name(r["skill_name"]) if r["skill_name"] else None,
                 "priority": r["priority"], "recommendation": r["recommendation"]}
                for r in recommendations
            ])

            st.session_state["last_analysis"] = {
                "gap_result": gap_result, "features": features,
                "selection_probability": selection_probability,
                "fit_label": fit_label, "recommendations": recommendations,
                "job": job,
            }

        result = st.session_state.get("last_analysis")
        if not result or result["job"]["job_id"] != job_id:
            st.info("Click **Analyze Job Fit** to generate results for this specific role.")
            return

        gap_result = result["gap_result"]
        selection_probability = result["selection_probability"]
        fit_label = result["fit_label"]
        recommendations = result["recommendations"]
        job = result["job"]

        st.divider()
        st.subheader(f"{job['job_title']} — {job['company_name']}")
        _render_fit_stats(gap_result, result["features"], selection_probability, fit_label, job)

        st.divider()
        st.markdown("### 💡 Improvement Suggestions")
        if not recommendations:
            st.success("No skill gaps detected — great job!")
        else:
            priority_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡"}
            for rec in recommendations:
                st.markdown(f"{priority_icon.get(rec['priority'], '⚪')} **[{rec['priority']}]** {rec['recommendation']}")


def render():
    st.title("🎯 Job Fit Analysis")

    student_id = st.session_state.get("student_id")
    if not student_id:
        st.warning("Please complete the **Candidate Resume Analysis** page first.")
        return

    student = db.get_student(student_id)
    if not student:
        st.warning("No saved candidate profile found. Please complete resume analysis and save your profile first.")
        return

    jobs = db.get_all_jobs()
    if not jobs:
        st.warning("No jobs available. Ask the placement organization to add one.")
        return

    candidate_skills = db.get_student_skills(student_id)
    projects = db.get_student_projects(student_id)
    certifications = db.get_student_certifications(student_id)

    _render_best_role_section(student_id, student, candidate_skills, projects, certifications, jobs)

    st.divider()
    _render_specific_job_section(student_id, student, candidate_skills, projects, certifications, jobs)
