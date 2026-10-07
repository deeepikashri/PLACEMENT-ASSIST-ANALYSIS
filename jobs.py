"""
Placement Organization / Job Management page (spec sections 5 & 22).

Lets the placement organization add, edit, delete and view jobs, and
manage each job's required skills (level 1-5, mandatory flag, weight).
"""

import streamlit as st

from database import database as db
from resume.skill_extractor import get_all_known_skills, normalize_skill_name, extract_skills
from integrations.job_board_api import search_live_jobs


def _skill_editor(existing_skills=None, key_prefix="new"):
    """
    Renders an editable table of job-required skills using a
    st.data_editor, seeded with `existing_skills` if provided.
    Returns the list of skill dicts the user has configured.
    """
    known_skills = get_all_known_skills()

    if existing_skills:
        default_rows = [
            {
                "skill_name": s["skill_name"],
                "required_level": s["required_level"],
                "mandatory": bool(s["mandatory"]),
                "weight": s["weight"],
            }
            for s in existing_skills
        ]
    else:
        default_rows = [
            {"skill_name": known_skills[0] if known_skills else "Python",
             "required_level": 3, "mandatory": True, "weight": 1.0}
        ]

    edited = st.data_editor(
        default_rows,
        num_rows="dynamic",
        use_container_width=True,
        key=f"{key_prefix}_skill_editor",
        column_config={
            "skill_name": st.column_config.TextColumn(
                "Skill", help="Type a skill name (dictionary skills are recognized automatically)."
            ),
            "required_level": st.column_config.NumberColumn(
                "Required Level (1-5)", min_value=1, max_value=5, step=1
            ),
            "mandatory": st.column_config.CheckboxColumn("Mandatory"),
            "weight": st.column_config.NumberColumn(
                "Weight", min_value=0.1, max_value=2.0, step=0.1
            ),
        },
    )

    cleaned = []
    for row in edited:
        name = (row.get("skill_name") or "").strip()
        if not name:
            continue
        cleaned.append({
            "skill_name": normalize_skill_name(name),
            "required_level": int(row.get("required_level") or 1),
            "mandatory": bool(row.get("mandatory")),
            "weight": float(row.get("weight") or 1.0),
        })
    return cleaned


def render():
    st.title("🏢 Placement Organization — Job Management")
    st.caption("Add, edit, and manage job roles and their required skills.")

    tab_view, tab_add, tab_edit, tab_import = st.tabs(
        ["📋 View Jobs", "➕ Add Job", "✏️ Edit / Delete Job", "🌐 Import Live Posting"]
    )

    # -----------------------------------------------------------
    # VIEW JOBS
    # -----------------------------------------------------------
    with tab_view:
        jobs = db.get_all_jobs()
        if not jobs:
            st.info("No jobs have been added yet. Use the 'Add Job' tab to create one.")
        for job in jobs:
            with st.expander(f"**{job['job_title']}** — {job['company_name']} (ID: {job['job_id']})"):
                st.write(job["description"] or "_No description provided._")
                st.write(f"**Minimum Experience:** {job['minimum_experience']} year(s)")
                skills = db.get_job_skills(job["job_id"])
                if skills:
                    st.table([
                        {
                            "Skill": s["skill_name"],
                            "Required Level": s["required_level"],
                            "Mandatory": "Yes" if s["mandatory"] else "No",
                            "Weight": s["weight"],
                        }
                        for s in skills
                    ])
                else:
                    st.warning("This job has no required skills defined.")

    # -----------------------------------------------------------
    # IMPORT LIVE JOB POSTING (optional external API)
    #
    # NOTE: this block is intentionally placed here in the code (even
    # though it renders in the last, right-most tab) so that its
    # session_state writes for add_job_title/add_company_name/etc. run
    # BEFORE those keys' widgets are instantiated in tab_add below —
    # Streamlit forbids setting a widget's session_state key after that
    # widget has already been created in the same script run. Tab
    # *visual* order is controlled solely by the st.tabs(...) call above,
    # not by the order these `with tab_x:` blocks appear in the code.
    # -----------------------------------------------------------
    with tab_import:
        st.subheader("Import a Real Job Posting")
        st.caption(
            "Search live, currently-open remote job postings (via the free Remotive API, "
            "no account needed) and use one as a starting point instead of typing a job by hand. "
            "Required skills are auto-suggested from the posting's description using the same "
            "skill dictionary used for resumes — review and adjust them before creating the job."
        )

        query = st.text_input(
            "Search live postings by keyword", value="", placeholder="e.g. data scientist, python developer"
        )
        if st.button("🔎 Search Live Jobs"):
            with st.spinner("Searching live postings..."):
                results = search_live_jobs(query)
            st.session_state["live_job_results"] = results
            if not results:
                st.warning(
                    "No live postings found (or the live jobs API is unreachable right now). "
                    "Try a different keyword, or add the job manually in the 'Add Job' tab."
                )

        results = st.session_state.get("live_job_results", [])
        if results:
            options = {
                f"{r['job_title']} — {r['company_name']}": i for i, r in enumerate(results)
            }
            chosen_label = st.selectbox("Select a posting to preview", list(options.keys()))
            chosen = results[options[chosen_label]]

            with st.expander("Preview posting", expanded=True):
                st.write(f"**{chosen['job_title']}** — {chosen['company_name']}")
                if chosen.get("category"):
                    st.caption(f"Category: {chosen['category']}")
                st.write(chosen["description"] or "_No description available._")
                if chosen.get("url"):
                    st.caption(f"Source: {chosen['url']}")

            if st.button("✅ Use This Posting", type="primary"):
                suggested_skill_names = extract_skills(chosen["description"])
                st.session_state["add_job_title"] = chosen["job_title"]
                st.session_state["add_company_name"] = chosen["company_name"]
                st.session_state["add_description"] = chosen["description"]
                st.session_state["add_min_exp"] = float(chosen.get("minimum_experience", 0) or 0)
                st.session_state["live_import_skills"] = [
                    {"skill_name": s, "required_level": 3, "mandatory": True, "weight": 1.0}
                    for s in suggested_skill_names
                ] or None
                st.session_state["live_import_pending"] = True
                st.success("Posting imported — switch to the **➕ Add Job** tab to review and create it.")

    # -----------------------------------------------------------
    # ADD JOB
    # -----------------------------------------------------------
    with tab_add:
        st.subheader("Add a New Job Role")

        if st.session_state.get("live_import_pending"):
            st.info(
                "Fields below were pre-filled from a live job posting import. "
                "Review, adjust the suggested skills, and click **Create Job** when ready.",
                icon="🌐",
            )

        col1, col2 = st.columns(2)
        with col1:
            job_title = st.text_input("Job Title", key="add_job_title")
        with col2:
            company_name = st.text_input("Company Name", key="add_company_name")

        description = st.text_area("Job Description", key="add_description")
        minimum_experience = st.number_input(
            "Minimum Experience (years)", min_value=0.0, max_value=20.0, step=0.5, key="add_min_exp"
        )

        st.markdown("**Required Skills**")
        st.caption("Add rows for each required skill. Use the (+) icon below the table to add more.")
        prefill_skills = st.session_state.get("live_import_skills")
        skills = _skill_editor(existing_skills=prefill_skills, key_prefix="add")

        if st.button("Create Job", type="primary"):
            if not job_title.strip() or not company_name.strip():
                st.error("Job Title and Company Name are required.")
            elif not skills:
                st.error("Please add at least one required skill.")
            else:
                job_id = db.add_job(
                    company_name=company_name.strip(),
                    job_title=job_title.strip(),
                    description=description.strip(),
                    minimum_experience=minimum_experience,
                    skills=skills,
                )
                st.session_state["live_import_pending"] = False
                st.session_state.pop("live_import_skills", None)
                st.success(f"Job '{job_title}' created successfully (Job ID: {job_id}).")
                st.rerun()

    # -----------------------------------------------------------
    # EDIT / DELETE JOB
    # -----------------------------------------------------------
    with tab_edit:
        jobs = db.get_all_jobs()
        if not jobs:
            st.info("No jobs available to edit.")
            return

        job_options = {f"{j['job_title']} — {j['company_name']} (ID: {j['job_id']})": j["job_id"] for j in jobs}
        selected_label = st.selectbox("Select a job to edit or delete", list(job_options.keys()))
        job_id = job_options[selected_label]
        job = db.get_job(job_id)
        current_skills = db.get_job_skills(job_id)

        col1, col2 = st.columns(2)
        with col1:
            job_title = st.text_input("Job Title", value=job["job_title"], key="edit_job_title")
        with col2:
            company_name = st.text_input("Company Name", value=job["company_name"], key="edit_company_name")

        description = st.text_area("Job Description", value=job["description"] or "", key="edit_description")
        minimum_experience = st.number_input(
            "Minimum Experience (years)", min_value=0.0, max_value=20.0, step=0.5,
            value=float(job["minimum_experience"]), key="edit_min_exp"
        )

        st.markdown("**Required Skills**")
        skills = _skill_editor(existing_skills=current_skills, key_prefix="edit")

        col_save, col_delete = st.columns(2)
        with col_save:
            if st.button("Save Changes", type="primary"):
                if not skills:
                    st.error("A job must have at least one required skill.")
                else:
                    db.update_job(
                        job_id=job_id,
                        company_name=company_name.strip(),
                        job_title=job_title.strip(),
                        description=description.strip(),
                        minimum_experience=minimum_experience,
                        skills=skills,
                    )
                    st.success("Job updated successfully.")
                    st.rerun()
        with col_delete:
            if st.button("🗑️ Delete Job", type="secondary"):
                db.delete_job(job_id)
                st.success("Job deleted.")
                st.rerun()
