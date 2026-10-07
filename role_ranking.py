"""
Best-Suited Job Role ranking.

This does NOT introduce a new ML model. It reuses the exact same
deterministic skill-gap logic (analysis.skill_gap) and the exact same
trained selection-probability model (models.predict) that the
single-job "Job Fit Analysis" flow already uses — it simply runs that
pipeline once per job role in the database and ranks the results, so
the candidate's best-fit role can be surfaced as the headline
prediction instead of requiring the user to pick a job first.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from database import database as db
from analysis.skill_gap import compare_skills, SkillGapResult
from analysis.feature_engineering import build_feature_dict
from models.predict import get_predictor, classify_fit


@dataclass
class RoleRankingEntry:
    job: Dict
    gap_result: SkillGapResult
    features: Dict
    selection_probability: float
    fit_label: str


def rank_all_jobs(
    student: Dict,
    candidate_skills: Dict[str, int],
    projects_count: int,
    certifications_count: int,
    jobs: Optional[List[Dict]] = None,
) -> List[RoleRankingEntry]:
    """
    Score the candidate against every job role that has required
    skills configured, and return the results sorted best-first.

    Ranking key: selection probability first, overall skill match
    percentage as a tiebreaker. Jobs with no configured required
    skills are skipped (they can't be scored).

    Raises ModelNotTrainedError (propagated from models.predict) if
    no trained model is available — callers should handle this the
    same way the single-job analysis page already does.
    """
    if jobs is None:
        jobs = db.get_all_jobs()

    predictor = get_predictor()

    entries: List[RoleRankingEntry] = []
    for job in jobs:
        job_skills = db.get_job_skills(job["job_id"])
        if not job_skills:
            continue

        gap_result = compare_skills(job_skills, candidate_skills)
        features = build_feature_dict(
            gap_result=gap_result,
            student_experience=student["experience_years"],
            required_experience=job["minimum_experience"],
            projects_count=projects_count,
            certifications_count=certifications_count,
        )
        selection_probability = predictor.predict_probability(features)
        fit_label = classify_fit(selection_probability)

        entries.append(
            RoleRankingEntry(
                job=job,
                gap_result=gap_result,
                features=features,
                selection_probability=selection_probability,
                fit_label=fit_label,
            )
        )

    entries.sort(
        key=lambda e: (e.selection_probability, e.gap_result.match_percentage),
        reverse=True,
    )
    return entries
