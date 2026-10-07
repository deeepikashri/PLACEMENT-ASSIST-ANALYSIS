"""
Database access layer.

Provides a single point of contact (get_connection) for MySQL access
plus CRUD helper functions used throughout the application. All SQL
lives in this module so the rest of the app never writes raw queries.

Connection settings come from database/config.py (env-driven). Every
public function signature here is unchanged from the previous SQLite
version, so nothing above this layer (pages/, analysis/, etc.) needs
to change.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any

import pymysql
import pymysql.cursors

from database.config import DB_CONFIG, MYSQL_DATABASE
from database.schema import SCHEMA_STATEMENTS, INDEX_STATEMENTS

# MySQL error code for "Duplicate key name" -- raised when an index we
# already created is created again. Safe to ignore (see init_database).
_ERR_DUP_KEYNAME = 1061


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def get_connection():
    """Yield a MySQL connection (rows returned as dicts) with commit/rollback handling."""
    conn = pymysql.connect(
        cursorclass=pymysql.cursors.DictCursor,
        database=MYSQL_DATABASE,
        **DB_CONFIG,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_database_exists() -> None:
    """Create the target MySQL database if it doesn't already exist."""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conn.commit()
    finally:
        conn.close()


def init_database() -> None:
    """Create all tables and indexes if they do not already exist."""
    _ensure_database_exists()
    with get_connection() as conn:
        cur = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cur.execute(statement)
        for statement in INDEX_STATEMENTS:
            try:
                cur.execute(statement)
            except pymysql.err.OperationalError as exc:
                if exc.args and exc.args[0] == _ERR_DUP_KEYNAME:
                    continue
                raise


# =====================================================================
# SKILLS
# =====================================================================

def upsert_skill(skill_name: str, category: str = "General") -> int:
    """Insert a skill if it doesn't exist and return its skill_id."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT skill_id FROM skills WHERE skill_name = %s", (skill_name,))
        row = cur.fetchone()
        if row:
            return row["skill_id"]
        cur.execute(
            "INSERT INTO skills (skill_name, category) VALUES (%s, %s)",
            (skill_name, category),
        )
        return cur.lastrowid


def get_all_skills() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM skills ORDER BY skill_name")
        return [dict(r) for r in cur.fetchall()]


def get_skill_id_by_name(skill_name: str) -> Optional[int]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT skill_id FROM skills WHERE skill_name = %s", (skill_name,))
        row = cur.fetchone()
        return row["skill_id"] if row else None


# =====================================================================
# STUDENTS
# =====================================================================

def upsert_student(
    student_id: str,
    name: str = "",
    email: str = "",
    phone: str = "",
    experience_years: float = 0.0,
    education: str = "",
) -> None:
    """
    Insert a new student or update an existing one.
    A student keeps ONE permanent student_id across visits (requirement #23).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT student_id FROM students WHERE student_id = %s", (student_id,))
        existing = cur.fetchone()
        now = _now()
        if existing:
            cur.execute(
                """
                UPDATE students
                SET name = %s, email = %s, phone = %s, experience_years = %s,
                    education = %s, updated_at = %s
                WHERE student_id = %s
                """,
                (name, email, phone, experience_years, education, now, student_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO students
                    (student_id, name, email, phone, experience_years, education,
                     created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (student_id, name, email, phone, experience_years, education, now, now),
            )


def get_student(student_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def student_exists(student_id: str) -> bool:
    return get_student(student_id) is not None


def set_student_skills(student_id: str, skills: Dict[str, int]) -> None:
    """
    Replace a student's skill set.
    `skills` maps skill_name -> proficiency (1-5).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM student_skills WHERE student_id = %s", (student_id,))
        now = _now()
        for skill_name, proficiency in skills.items():
            cur.execute("SELECT skill_id FROM skills WHERE skill_name = %s", (skill_name,))
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO skills (skill_name, category) VALUES (%s, %s)",
                    (skill_name, "General"),
                )
                skill_id = cur.lastrowid
            else:
                skill_id = row["skill_id"]
            cur.execute(
                """
                INSERT INTO student_skills (student_id, skill_id, proficiency, years_experience, last_updated)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (student_id, skill_id, proficiency, 0, now),
            )


def get_student_skills(student_id: str) -> Dict[str, int]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.skill_name, ss.proficiency
            FROM student_skills ss
            JOIN skills s ON s.skill_id = ss.skill_id
            WHERE ss.student_id = %s
            """,
            (student_id,),
        )
        return {r["skill_name"]: r["proficiency"] for r in cur.fetchall()}


def set_student_projects(student_id: str, projects: List[Dict[str, str]]) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM projects WHERE student_id = %s", (student_id,))
        for p in projects:
            cur.execute(
                """
                INSERT INTO projects (student_id, project_name, description, technologies)
                VALUES (%s, %s, %s, %s)
                """,
                (student_id, p.get("name", ""), p.get("description", ""), p.get("technologies", "")),
            )


def get_student_projects(student_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM projects WHERE student_id = %s", (student_id,))
        return [dict(r) for r in cur.fetchall()]


def set_student_certifications(student_id: str, certifications: List[Dict[str, str]]) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM certifications WHERE student_id = %s", (student_id,))
        for c in certifications:
            cur.execute(
                """
                INSERT INTO certifications (student_id, certification_name, issuer)
                VALUES (%s, %s, %s)
                """,
                (student_id, c.get("name", ""), c.get("issuer", "")),
            )


def get_student_certifications(student_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM certifications WHERE student_id = %s", (student_id,))
        return [dict(r) for r in cur.fetchall()]


# =====================================================================
# JOBS
# =====================================================================

def add_job(
    company_name: str,
    job_title: str,
    description: str,
    minimum_experience: float,
    skills: List[Dict[str, Any]],
) -> int:
    """
    Create a job with its required skills.
    `skills` is a list of dicts: {skill_name, required_level, mandatory, weight}
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO jobs (company_name, job_title, description, minimum_experience, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (company_name, job_title, description, minimum_experience, _now()),
        )
        job_id = cur.lastrowid
        _insert_job_skills(cur, job_id, skills)
        return job_id


def update_job(
    job_id: int,
    company_name: str,
    job_title: str,
    description: str,
    minimum_experience: float,
    skills: List[Dict[str, Any]],
) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE jobs SET company_name = %s, job_title = %s, description = %s, minimum_experience = %s
            WHERE job_id = %s
            """,
            (company_name, job_title, description, minimum_experience, job_id),
        )
        cur.execute("DELETE FROM job_skills WHERE job_id = %s", (job_id,))
        _insert_job_skills(cur, job_id, skills)


def _insert_job_skills(cur, job_id: int, skills: List[Dict[str, Any]]) -> None:
    for s in skills:
        skill_name = s["skill_name"]
        cur.execute("SELECT skill_id FROM skills WHERE skill_name = %s", (skill_name,))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO skills (skill_name, category) VALUES (%s, %s)",
                (skill_name, s.get("category", "General")),
            )
            skill_id = cur.lastrowid
        else:
            skill_id = row["skill_id"]
        cur.execute(
            """
            INSERT INTO job_skills (job_id, skill_id, required_level, mandatory, weight)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                job_id,
                skill_id,
                int(s.get("required_level", 1)),
                1 if s.get("mandatory") else 0,
                float(s.get("weight", 1.0)),
            ),
        )


def delete_job(job_id: int) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM jobs WHERE job_id = %s", (job_id,))


def get_all_jobs() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs ORDER BY job_title")
        return [dict(r) for r in cur.fetchall()]


def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_job_skills(job_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT s.skill_id, s.skill_name, js.required_level, js.mandatory, js.weight
            FROM job_skills js
            JOIN skills s ON s.skill_id = js.skill_id
            WHERE js.job_id = %s
            ORDER BY js.mandatory DESC, s.skill_name
            """,
            (job_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# =====================================================================
# ML PREDICTIONS / HISTORY
# =====================================================================

def save_prediction(
    student_id: str,
    job_id: int,
    match_percentage: float,
    mandatory_match_percentage: float,
    average_skill_gap: float,
    experience_gap: float,
    projects: int,
    certifications: int,
    selection_probability: float,
    prediction: int,
) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ml_predictions (
                student_id, job_id, match_percentage, mandatory_match_percentage,
                average_skill_gap, experience_gap, projects, certifications,
                selection_probability, prediction, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                student_id, job_id, match_percentage, mandatory_match_percentage,
                average_skill_gap, experience_gap, projects, certifications,
                selection_probability, prediction, _now(),
            ),
        )
        return cur.lastrowid


def get_prediction_history(student_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.*, j.job_title, j.company_name
            FROM ml_predictions p
            JOIN jobs j ON j.job_id = p.job_id
            WHERE p.student_id = %s
            ORDER BY p.created_at DESC
            """,
            (student_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def save_recommendations(student_id: str, job_id: int, recommendations: List[Dict[str, Any]]) -> None:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM recommendations WHERE student_id = %s AND job_id = %s",
            (student_id, job_id),
        )
        now = _now()
        for rec in recommendations:
            cur.execute(
                """
                INSERT INTO recommendations (student_id, job_id, skill_id, priority, recommendation, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (student_id, job_id, rec.get("skill_id"), rec["priority"], rec["recommendation"], now),
            )


def get_recommendations(student_id: str, job_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM recommendations WHERE student_id = %s AND job_id = %s ORDER BY priority",
            (student_id, job_id),
        )
        return [dict(r) for r in cur.fetchall()]
