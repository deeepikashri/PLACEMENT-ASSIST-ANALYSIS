"""
Feature engineering for the ML selection-probability model
(spec section 12).

This module converts deterministic skill-gap results + candidate
profile facts into the numeric feature vector consumed by the trained
scikit-learn model. The SAME feature construction logic is used both
for synthetic training data generation and for live inference, so the
model always sees features in a consistent shape.
"""

from typing import Dict

from analysis.skill_gap import SkillGapResult

# The exact ordered list of feature columns the ML model is trained on.
# Keeping this centralized avoids column-order bugs between training
# and inference.
FEATURE_COLUMNS = [
    "total_required_skills",
    "skills_matched",
    "skills_missing",
    "match_percentage",
    "mandatory_required",
    "mandatory_matched",
    "mandatory_match_percentage",
    "average_skill_gap",
    "max_skill_gap",
    "student_experience",
    "required_experience",
    "experience_gap",
    "projects",
    "certifications",
]


def build_feature_dict(
    gap_result: SkillGapResult,
    student_experience: float,
    required_experience: float,
    projects_count: int,
    certifications_count: int,
) -> Dict[str, float]:
    """
    Build the full feature dictionary for one candidate-job pair.
    experience_gap is clipped at 0 (extra experience beyond the
    requirement does not create a negative gap).
    """
    experience_gap = max(required_experience - student_experience, 0)

    features = {
        "total_required_skills": gap_result.total_required_skills,
        "skills_matched": gap_result.skills_matched,
        "skills_missing": gap_result.skills_missing,
        "match_percentage": gap_result.match_percentage,
        "mandatory_required": gap_result.mandatory_required,
        "mandatory_matched": gap_result.mandatory_matched,
        "mandatory_match_percentage": gap_result.mandatory_match_percentage,
        "average_skill_gap": gap_result.average_skill_gap,
        "max_skill_gap": gap_result.max_skill_gap,
        "student_experience": student_experience,
        "required_experience": required_experience,
        "experience_gap": experience_gap,
        "projects": projects_count,
        "certifications": certifications_count,
    }
    return features


def feature_dict_to_vector(features: Dict[str, float]) -> list:
    """Order a feature dict into the exact vector the model expects."""
    return [features[col] for col in FEATURE_COLUMNS]
