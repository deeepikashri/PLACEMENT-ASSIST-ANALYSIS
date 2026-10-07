"""
Candidate Resume Analysis page (spec sections 6, 8, 9, 18).

Implements Steps 1-4 of the candidate workflow:
    1. Select Job
    2. Upload Resume
    3. Extract Resume
    4. Review / Edit Candidate Profile

The resulting candidate profile is stored in st.session_state so the
"Job Fit Analysis" page can consume it, and persisted to the database
keyed by a permanent student_id (spec section 23).
"""

import streamlit as st

from database import database as db
from resume.resume_parser import process_resume, ResumeParsingError
from resume.profile_extractor import extract_candidate_profile
from resume.skill_extractor import extract_skills, get_all_known_skills, normalize_skill_name
from resume.llm_extractor import extract_profile_with_llm, is_llm_configured


def _load_existing_student(student_id: str):
    student = db.get_student(student_id)
    if not student:
        return None
    return {
        "student": student,
        "skills": db.get_student_skills(student_id),
        "projects": db.get_student_projects(student_id),
        "certifications": db.get_student_certifications(student_id),
    }


def render():
    st.title("📄 Candidate Resume Analysis")
    st.caption("Upload your resume, review the extracted profile, then head to Job Fit Analysis.")

    # -----------------------------------------------------------
    # STEP 1: Select Job
    # -----------------------------------------------------------
    st.subheader("Step 1: Select a Job Role")
    jobs = db.get_all_jobs()
    if not jobs:
        st.warning("No jobs are available yet. Ask the placement organization to add one first.")
        return

    job_options = {f"{j['job_title']} — {j['company_name']}": j["job_id"] for j in jobs}
    selected_job_label = st.selectbox("Choose the job you want to be evaluated against", list(job_options.keys()))
    selected_job_id = job_options[selected_job_label]
    st.session_state["selected_job_id"] = selected_job_id

    st.divider()

    # -----------------------------------------------------------
    # Student ID (returning candidate support — spec section 23)
    # -----------------------------------------------------------
    st.subheader("Step 2: Identify Yourself")
    col_id, col_help = st.columns([2, 3])
    with col_id:
        student_id = st.text_input(
            "Student ID",
            value=st.session_state.get("student_id", ""),
            help="Returning candidates: enter your existing Student ID to update your profile. "
                 "New candidates: choose any unique ID, e.g. STU1001.",
        )
    with col_help:
        st.info("Your Student ID is permanent. Re-using it later updates your existing record "
                "instead of creating a duplicate.", icon="ℹ️")

    if not student_id.strip():
        st.stop()
    student_id = student_id.strip()
    st.session_state["student_id"] = student_id

    existing = _load_existing_student(student_id)
    if existing:
        st.success(f"Welcome back, {existing['student']['name'] or student_id}! Your previous profile was loaded.")

    st.divider()

    # -----------------------------------------------------------
    # STEP 3: Upload Resume
    # -----------------------------------------------------------
    st.subheader("Step 3: Upload Resume (PDF)")
    uploaded_file = st.file_uploader("Upload your resume", type=["pdf"])

    llm_available = is_llm_configured()
    use_ai_extraction = st.checkbox(
        "✨ Enhance extraction with AI",
        value=False,
        disabled=not llm_available,
        help=(
            "Uses Google's free-tier Gemini API to read the resume for potentially more accurate "
            "name/contact/education/project/certification extraction. Falls back automatically to "
            "the standard extractor if unavailable. Requires GEMINI_API_KEY to be set "
            "(free key: https://aistudio.google.com/apikey)."
            if llm_available else
            "Not available: set the GEMINI_API_KEY environment variable to enable this "
            "(free key: https://aistudio.google.com/apikey)."
        ),
    )

    if uploaded_file is not None:
        if st.button("Extract Resume", type="primary"):
            with st.spinner("Processing resume (text extraction, OCR fallback if needed)..."):
                try:
                    file_bytes = uploaded_file.read()
                    cleaned_text, used_ocr = process_resume(file_bytes)

                    # Skill detection always stays deterministic/dictionary-based,
                    # regardless of the AI-enhanced-extraction toggle (see README).
                    detected_skills = extract_skills(cleaned_text)

                    profile = None
                    used_ai = False
                    if use_ai_extraction and llm_available:
                        profile = extract_profile_with_llm(cleaned_text)
                        used_ai = profile is not None

                    if profile is None:
                        profile = extract_candidate_profile(cleaned_text)

                    st.session_state["resume_text"] = cleaned_text
                    st.session_state["used_ocr"] = used_ocr
                    st.session_state["extracted_profile"] = profile
                    st.session_state["detected_skills"] = detected_skills

                    status_msg = "Resume processed successfully"
                    status_msg += " (OCR fallback was used for this scanned PDF)." if used_ocr else "."
                    st.success(status_msg)
                    if use_ai_extraction and llm_available:
                        if used_ai:
                            st.caption("✨ Profile fields were extracted using AI. Please still review them below.")
                        else:
                            st.caption("⚠️ AI extraction was unavailable for this request — used the standard extractor instead.")
                except ResumeParsingError as exc:
                    st.error(f"Could not process this resume: {exc}")
                except Exception:
                    st.error("An unexpected error occurred while processing the resume. "
                              "Please check the file and try again.")

    st.divider()

    # -----------------------------------------------------------
    # STEP 4: Review / Edit Candidate Profile
    # -----------------------------------------------------------
    st.subheader("Step 4: Review & Edit Candidate Profile")

    profile = st.session_state.get("extracted_profile")
    detected_skills = st.session_state.get("detected_skills", [])

    if not profile and not existing:
        st.info("Upload and extract a resume above, or enter a Student ID with an existing profile.")
        return

    # Merge extracted data with any previously saved data as sensible defaults
    default_name = profile["name"] if profile else (existing["student"]["name"] if existing else "")
    default_email = profile["email"] if profile else (existing["student"]["email"] if existing else "")
    default_phone = profile["phone"] if profile else (existing["student"]["phone"] if existing else "")
    default_education = profile["education"] if profile else (existing["student"]["education"] if existing else "")
    default_experience = profile["experience_years"] if profile else (
        existing["student"]["experience_years"] if existing else 0.0
    )

    with st.form("candidate_profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name", value=default_name)
            email = st.text_input("Email", value=default_email)
        with col2:
            phone = st.text_input("Phone", value=default_phone)
            experience_years = st.number_input(
                "Experience (years)", min_value=0.0, max_value=40.0, step=0.5,
                value=float(default_experience or 0.0),
            )

        education = st.text_area("Education", value=default_education, height=80)

        st.markdown("**Detected / Confirmed Skills & Proficiency**")
        st.caption(
            "PDF parsing can only detect that a skill was mentioned — it cannot know your true "
            "proficiency. Please confirm each skill's level by picking a star rating "
            "(⭐ = Beginner ... ⭐⭐⭐⭐⭐ = Expert)."
        )

        # Build the starting skill rows: previously saved skills take priority,
        # then newly detected skills default to proficiency 3.
        base_skills = dict(existing["skills"]) if existing else {}
        for s in detected_skills:
            base_skills.setdefault(s, 3)

        STAR_OPTIONS = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]

        def _level_to_stars(level: int) -> str:
            level = max(1, min(5, int(level or 1)))
            return STAR_OPTIONS[level - 1]

        def _stars_to_level(stars: str) -> int:
            # Count star characters so it's robust even if the value comes
            # back as something slightly different than our exact options.
            count = (stars or "").count("⭐")
            return max(1, min(5, count)) if count else 1

        skill_rows = [
            {"skill_name": k, "proficiency": _level_to_stars(v)}
            for k, v in sorted(base_skills.items())
        ]
        if not skill_rows:
            skill_rows = [{"skill_name": get_all_known_skills()[0], "proficiency": _level_to_stars(3)}]

        edited_skills = st.data_editor(
            skill_rows,
            num_rows="dynamic",
            use_container_width=True,
            key="candidate_skill_editor",
            column_config={
                "skill_name": st.column_config.TextColumn("Skill"),
                "proficiency": st.column_config.SelectboxColumn(
                    "Proficiency",
                    help="Pick a star rating instead of typing a number: "
                         "⭐ Beginner · ⭐⭐ Basic · ⭐⭐⭐ Intermediate · ⭐⭐⭐⭐ Advanced · ⭐⭐⭐⭐⭐ Expert",
                    options=STAR_OPTIONS,
                    required=True,
                ),
            },
        )

        st.markdown("**Projects**")
        base_projects = profile["projects"] if profile else existing["projects"] if existing else []
        project_rows = [
            {"name": p.get("name") or p.get("project_name", ""),
             "description": p.get("description", ""),
             "technologies": p.get("technologies", "")}
            for p in base_projects
        ] or [{"name": "", "description": "", "technologies": ""}]
        edited_projects = st.data_editor(
            project_rows, num_rows="dynamic", use_container_width=True, key="candidate_project_editor"
        )

        st.markdown("**Certifications**")
        base_certs = profile["certifications"] if profile else existing["certifications"] if existing else []
        cert_rows = [
            {"name": c.get("name") or c.get("certification_name", ""), "issuer": c.get("issuer", "")}
            for c in base_certs
        ] or [{"name": "", "issuer": ""}]
        edited_certs = st.data_editor(
            cert_rows, num_rows="dynamic", use_container_width=True, key="candidate_cert_editor"
        )

        submitted = st.form_submit_button("Save Candidate Profile", type="primary")

    if submitted:
        skills_dict = {}
        for row in edited_skills:
            name_val = (row.get("skill_name") or "").strip()
            if not name_val:
                continue
            canonical = normalize_skill_name(name_val)
            skills_dict[canonical] = _stars_to_level(row.get("proficiency"))

        projects_list = [
            {"name": r.get("name", ""), "description": r.get("description", ""), "technologies": r.get("technologies", "")}
            for r in edited_projects if (r.get("name") or "").strip()
        ]
        certs_list = [
            {"name": r.get("name", ""), "issuer": r.get("issuer", "")}
            for r in edited_certs if (r.get("name") or "").strip()
        ]

        db.upsert_student(
            student_id=student_id, name=name, email=email, phone=phone,
            experience_years=experience_years, education=education,
        )
        db.set_student_skills(student_id, skills_dict)
        db.set_student_projects(student_id, projects_list)
        db.set_student_certifications(student_id, certs_list)

        st.session_state["candidate_saved"] = True
        st.success("Candidate profile saved. Go to **Job Fit Analysis** in the sidebar to see your results.")
