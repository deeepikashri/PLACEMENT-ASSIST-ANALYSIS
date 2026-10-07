"""
Simple rule-based skill improvement recommendation engine
(spec section 17). Intentionally NOT a complex recommender system.

Priority rules:
    HIGH   -> mandatory skill with a significant gap (gap >= 2)
    MEDIUM -> non-mandatory skill with a significant gap (gap >= 2)
              OR mandatory skill with a small gap (gap == 1)
    LOW    -> small gap (gap == 1) on a non-mandatory skill
"""

from typing import Dict, List

from analysis.skill_gap import SkillGapResult
from resume.skill_extractor import get_skill_category

SIGNIFICANT_GAP_THRESHOLD = 2

# Lightweight topic hints per skill so recommendation text is specific
# rather than generic. Extend this dictionary as needed.
SKILL_LEARNING_HINTS: Dict[str, str] = {
    "SQL": "joins, aggregation, subqueries and database querying",
    "Python": "core syntax, data structures, functions and OOP concepts",
    "Pandas": "dataframes, groupby operations and data cleaning workflows",
    "NumPy": "array operations, broadcasting and vectorized computation",
    "Scikit-learn": "model building, pipelines, cross-validation and evaluation metrics",
    "TensorFlow": "building and training neural networks with the Keras API",
    "Keras": "sequential and functional model APIs for deep learning",
    "Machine Learning": "core algorithms, model evaluation and the ML workflow",
    "Deep Learning": "neural network architectures and training techniques",
    "NLP": "text preprocessing, embeddings and transformer-based models",
    "Computer Vision": "image processing, CNNs and object detection basics",
    "Power BI": "dashboards, data modeling and visualization",
    "Tableau": "interactive dashboards and visual analytics",
    "Statistics": "probability, hypothesis testing and statistical inference",
    "Excel": "formulas, pivot tables and data analysis features",
    "Git": "version control workflows, branching and collaboration",
    "Docker": "containerization basics and writing Dockerfiles",
    "AWS": "core cloud services relevant to your target role",
    "Spark": "distributed data processing with PySpark",
    "Data Visualization": "chart design principles and storytelling with data",
}


def _priority_for(gap: int, mandatory: bool) -> str:
    if mandatory and gap >= SIGNIFICANT_GAP_THRESHOLD:
        return "HIGH"
    if (not mandatory and gap >= SIGNIFICANT_GAP_THRESHOLD) or (mandatory and gap == 1):
        return "MEDIUM"
    return "LOW"


def _recommendation_text(skill_name: str, category: str) -> str:
    hint = SKILL_LEARNING_HINTS.get(skill_name)
    if hint:
        return f"Improve {skill_name}: focus on {hint}."
    return f"Strengthen your {skill_name} ({category}) skills through hands-on practice and projects."


def generate_recommendations(gap_result: SkillGapResult) -> List[Dict]:
    """
    Build a prioritized list of recommendations for every skill that is
    not fully matched (status GAP or MISSING).

    Returns a list of dicts: {skill_name, priority, recommendation}
    sorted HIGH -> MEDIUM -> LOW.
    """
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations = []

    for row in gap_result.rows:
        if row.status == "MATCHED":
            continue
        priority = _priority_for(row.gap, row.mandatory)
        category = get_skill_category(row.skill_name)
        recommendations.append({
            "skill_name": row.skill_name,
            "priority": priority,
            "recommendation": _recommendation_text(row.skill_name, category),
        })

    recommendations.sort(key=lambda r: priority_order[r["priority"]])

    # General, non-skill-specific advice appended at the end
    if gap_result.average_skill_gap > 0:
        recommendations.append({
            "skill_name": None,
            "priority": "MEDIUM",
            "recommendation": "Gain practical project experience applying the missing skills above.",
        })
    if gap_result.mandatory_matched < gap_result.mandatory_required:
        recommendations.append({
            "skill_name": None,
            "priority": "HIGH",
            "recommendation": "Prioritize mandatory skills first — they carry the most weight in this role's evaluation.",
        })

    return recommendations
