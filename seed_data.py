"""
Initial sample data seeding (spec section 21).

Seeds the skill dictionary into the `skills` table and creates 8
realistic job roles, each with a distinct required-skill profile, so
the application is usable immediately after setup.
"""

from database.database import get_connection, add_job
from resume.skill_extractor import get_all_known_skills, get_skill_category

SAMPLE_JOBS = [
    {
        "company_name": "ABC Technologies",
        "job_title": "Data Scientist",
        "description": "Analyze data and build machine learning models to drive business decisions.",
        "minimum_experience": 1,
        "skills": [
            {"skill_name": "Python", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "SQL", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Pandas", "required_level": 3, "mandatory": True, "weight": 0.9},
            {"skill_name": "NumPy", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "Scikit-learn", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Machine Learning", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Statistics", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "TensorFlow", "required_level": 3, "mandatory": False, "weight": 0.6},
            {"skill_name": "Power BI", "required_level": 2, "mandatory": False, "weight": 0.4},
        ],
    },
    {
        "company_name": "DataWorks Analytics",
        "job_title": "Data Analyst",
        "description": "Turn raw data into actionable business insights through analysis and reporting.",
        "minimum_experience": 0,
        "skills": [
            {"skill_name": "SQL", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Excel", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Python", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "Power BI", "required_level": 3, "mandatory": True, "weight": 0.9},
            {"skill_name": "Data Visualization", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "Statistics", "required_level": 2, "mandatory": False, "weight": 0.6},
            {"skill_name": "Tableau", "required_level": 2, "mandatory": False, "weight": 0.5},
        ],
    },
    {
        "company_name": "NeuralWorks AI",
        "job_title": "Machine Learning Engineer",
        "description": "Design, train and deploy machine learning models into production systems.",
        "minimum_experience": 1,
        "skills": [
            {"skill_name": "Python", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Scikit-learn", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "TensorFlow", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Deep Learning", "required_level": 4, "mandatory": True, "weight": 0.9},
            {"skill_name": "SQL", "required_level": 3, "mandatory": False, "weight": 0.6},
            {"skill_name": "PyTorch", "required_level": 3, "mandatory": False, "weight": 0.6},
            {"skill_name": "Git", "required_level": 3, "mandatory": False, "weight": 0.5},
            {"skill_name": "Docker", "required_level": 2, "mandatory": False, "weight": 0.4},
        ],
    },
    {
        "company_name": "CodeBridge Software",
        "job_title": "Python Developer",
        "description": "Build and maintain backend services and applications using Python.",
        "minimum_experience": 0,
        "skills": [
            {"skill_name": "Python", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Django", "required_level": 3, "mandatory": True, "weight": 0.9},
            {"skill_name": "REST API", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "SQL", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "Git", "required_level": 3, "mandatory": False, "weight": 0.5},
            {"skill_name": "Flask", "required_level": 2, "mandatory": False, "weight": 0.4},
            {"skill_name": "Docker", "required_level": 2, "mandatory": False, "weight": 0.3},
        ],
    },
    {
        "company_name": "Innotech Solutions",
        "job_title": "Software Developer",
        "description": "Develop, test and maintain full-stack software applications.",
        "minimum_experience": 0,
        "skills": [
            {"skill_name": "Java", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "SQL", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "Git", "required_level": 3, "mandatory": True, "weight": 0.7},
            {"skill_name": "HTML", "required_level": 2, "mandatory": False, "weight": 0.4},
            {"skill_name": "CSS", "required_level": 2, "mandatory": False, "weight": 0.4},
            {"skill_name": "JavaScript", "required_level": 2, "mandatory": False, "weight": 0.5},
            {"skill_name": "Agile", "required_level": 2, "mandatory": False, "weight": 0.3},
        ],
    },
    {
        "company_name": "MarketPulse Consulting",
        "job_title": "Business Analyst",
        "description": "Bridge business needs and data-driven solutions through analysis and reporting.",
        "minimum_experience": 1,
        "skills": [
            {"skill_name": "Excel", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "SQL", "required_level": 3, "mandatory": True, "weight": 0.9},
            {"skill_name": "Business Analysis", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Power BI", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "Communication", "required_level": 4, "mandatory": True, "weight": 0.7},
            {"skill_name": "Statistics", "required_level": 2, "mandatory": False, "weight": 0.4},
        ],
    },
    {
        "company_name": "StreamData Systems",
        "job_title": "Data Engineer",
        "description": "Build and maintain scalable data pipelines and infrastructure.",
        "minimum_experience": 1,
        "skills": [
            {"skill_name": "Python", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "SQL", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "ETL", "required_level": 4, "mandatory": True, "weight": 0.9},
            {"skill_name": "Spark", "required_level": 3, "mandatory": True, "weight": 0.8},
            {"skill_name": "Airflow", "required_level": 3, "mandatory": False, "weight": 0.6},
            {"skill_name": "AWS", "required_level": 2, "mandatory": False, "weight": 0.5},
            {"skill_name": "Hadoop", "required_level": 2, "mandatory": False, "weight": 0.4},
        ],
    },
    {
        "company_name": "Visionary AI Labs",
        "job_title": "AI/ML Engineer",
        "description": "Research and implement AI solutions spanning NLP, vision and generative models.",
        "minimum_experience": 2,
        "skills": [
            {"skill_name": "Python", "required_level": 5, "mandatory": True, "weight": 1.0},
            {"skill_name": "Machine Learning", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "Deep Learning", "required_level": 4, "mandatory": True, "weight": 1.0},
            {"skill_name": "NLP", "required_level": 3, "mandatory": False, "weight": 0.7},
            {"skill_name": "Computer Vision", "required_level": 3, "mandatory": False, "weight": 0.7},
            {"skill_name": "Hugging Face", "required_level": 3, "mandatory": False, "weight": 0.6},
            {"skill_name": "PyTorch", "required_level": 4, "mandatory": True, "weight": 0.9},
        ],
    },
]


def seed_skills() -> None:
    """Load every skill from the controlled dictionary into the skills table."""
    with get_connection() as conn:
        cur = conn.cursor()
        for skill_name in get_all_known_skills():
            cur.execute("SELECT skill_id FROM skills WHERE skill_name = %s", (skill_name,))
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO skills (skill_name, category) VALUES (%s, %s)",
                    (skill_name, get_skill_category(skill_name)),
                )


def seed_jobs() -> None:
    """Create sample jobs only if the jobs table is currently empty."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM jobs")
        count = cur.fetchone()["c"]
    if count > 0:
        return

    for job in SAMPLE_JOBS:
        add_job(
            company_name=job["company_name"],
            job_title=job["job_title"],
            description=job["description"],
            minimum_experience=job["minimum_experience"],
            skills=job["skills"],
        )


def run_seed() -> None:
    seed_skills()
    seed_jobs()
