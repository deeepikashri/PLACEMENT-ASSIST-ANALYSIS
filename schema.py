"""
MySQL schema definitions for the Placement Job Fit & Skill Gap Analyzer.

All tables are created with IF NOT EXISTS so that re-running the
application does not destroy existing data. InnoDB is used explicitly
so foreign keys are enforced.
"""

SCHEMA_STATEMENTS = [
    # ---------------------------------------------------------------
    # STUDENTS
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS students (
        student_id VARCHAR(64) PRIMARY KEY,
        name VARCHAR(255),
        email VARCHAR(255),
        phone VARCHAR(50),
        experience_years FLOAT DEFAULT 0,
        education TEXT,
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # ---------------------------------------------------------------
    # SKILLS (controlled skill dictionary, mirrored in DB for FK use)
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS skills (
        skill_id INT AUTO_INCREMENT PRIMARY KEY,
        skill_name VARCHAR(255) UNIQUE NOT NULL,
        category VARCHAR(100)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # ---------------------------------------------------------------
    # STUDENT_SKILLS
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS student_skills (
        student_id VARCHAR(64) NOT NULL,
        skill_id INT NOT NULL,
        proficiency INT NOT NULL DEFAULT 1,
        years_experience FLOAT DEFAULT 0,
        last_updated VARCHAR(32) NOT NULL,
        PRIMARY KEY (student_id, skill_id),
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # ---------------------------------------------------------------
    # JOBS
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id INT AUTO_INCREMENT PRIMARY KEY,
        company_name VARCHAR(255) NOT NULL,
        job_title VARCHAR(255) NOT NULL,
        description TEXT,
        minimum_experience FLOAT DEFAULT 0,
        created_at VARCHAR(32) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # ---------------------------------------------------------------
    # JOB_SKILLS
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS job_skills (
        job_id INT NOT NULL,
        skill_id INT NOT NULL,
        required_level INT NOT NULL DEFAULT 1,
        mandatory BOOLEAN NOT NULL DEFAULT 0,
        weight FLOAT NOT NULL DEFAULT 1.0,
        PRIMARY KEY (job_id, skill_id),
        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
        FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # ---------------------------------------------------------------
    # PROJECTS
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS projects (
        project_id INT AUTO_INCREMENT PRIMARY KEY,
        student_id VARCHAR(64) NOT NULL,
        project_name VARCHAR(255),
        description TEXT,
        technologies VARCHAR(255),
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # ---------------------------------------------------------------
    # CERTIFICATIONS
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS certifications (
        certification_id INT AUTO_INCREMENT PRIMARY KEY,
        student_id VARCHAR(64) NOT NULL,
        certification_name VARCHAR(255),
        issuer VARCHAR(255),
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # ---------------------------------------------------------------
    # ML_PREDICTIONS
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS ml_predictions (
        prediction_id INT AUTO_INCREMENT PRIMARY KEY,
        student_id VARCHAR(64) NOT NULL,
        job_id INT NOT NULL,
        match_percentage FLOAT,
        mandatory_match_percentage FLOAT,
        average_skill_gap FLOAT,
        experience_gap FLOAT,
        projects INT,
        certifications INT,
        selection_probability FLOAT,
        prediction INT,
        created_at VARCHAR(32) NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,

    # ---------------------------------------------------------------
    # RECOMMENDATIONS
    # ---------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS recommendations (
        recommendation_id INT AUTO_INCREMENT PRIMARY KEY,
        student_id VARCHAR(64) NOT NULL,
        job_id INT NOT NULL,
        skill_id INT,
        priority VARCHAR(20),
        recommendation TEXT,
        created_at VARCHAR(32) NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
]

# MySQL does not support "CREATE INDEX IF NOT EXISTS" (unlike SQLite), so
# database.py: init_database() executes these individually and silently
# ignores a "duplicate key name" error (MySQL error 1061) on repeat runs.
INDEX_STATEMENTS = [
    "CREATE INDEX idx_student_skills_student ON student_skills(student_id);",
    "CREATE INDEX idx_job_skills_job ON job_skills(job_id);",
    "CREATE INDEX idx_predictions_student ON ml_predictions(student_id);",
    "CREATE INDEX idx_predictions_job ON ml_predictions(job_id);",
    "CREATE INDEX idx_recommendations_student_job ON recommendations(student_id, job_id);",
]
