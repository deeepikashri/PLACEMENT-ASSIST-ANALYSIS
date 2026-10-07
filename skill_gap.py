"""
Deterministic skill gap analysis (spec sections 10-11).

Per spec rule #25: skill matching, gap calculation, and match
percentage are pure Python logic — NOT ML. ML is reserved only for
selection-probability prediction.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SkillComparisonRow:
    skill_name: str
    required_level: int
    candidate_level: int
    gap: int
    mandatory: bool
    weight: float
    status: str  # "MATCHED" or "GAP" or "MISSING"


@dataclass
class SkillGapResult:
    rows: List[SkillComparisonRow] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    match_percentage: float = 0.0
    mandatory_match_percentage: float = 0.0
    weighted_match_percentage: float = 0.0
    average_skill_gap: float = 0.0
    max_skill_gap: int = 0
    total_required_skills: int = 0
    mandatory_required: int = 0
    mandatory_matched: int = 0
    skills_matched: int = 0
    skills_missing: int = 0


def compare_skills(
    job_skills: List[Dict],
    candidate_skills: Dict[str, int],
) -> SkillGapResult:
    """
    Compare a job's required skills against a candidate's confirmed
    skill proficiencies (1-5 scale).

    job_skills: list of dicts with keys
        skill_name, required_level, mandatory, weight
    candidate_skills: dict of skill_name -> proficiency (1-5)

    Rule: current_level >= required_level -> MATCHED, else GAP.
    A skill entirely absent from the candidate's profile is treated as
    candidate_level = 0 (MISSING is reported as a GAP with gap ==
    required_level).
    """
    result = SkillGapResult()
    result.total_required_skills = len(job_skills)

    total_gap = 0
    max_gap = 0
    mandatory_required = 0
    mandatory_matched = 0
    weighted_total_weight = 0.0
    weighted_matched_weight = 0.0

    for js in job_skills:
        skill_name = js["skill_name"]
        required_level = int(js["required_level"])
        mandatory = bool(js["mandatory"])
        weight = float(js.get("weight", 1.0))

        candidate_level = int(candidate_skills.get(skill_name, 0))
        gap = max(required_level - candidate_level, 0)
        status = "MATCHED" if candidate_level >= required_level else (
            "MISSING" if candidate_level == 0 else "GAP"
        )

        row = SkillComparisonRow(
            skill_name=skill_name,
            required_level=required_level,
            candidate_level=candidate_level,
            gap=gap,
            mandatory=mandatory,
            weight=weight,
            status=status,
        )
        result.rows.append(row)

        total_gap += gap
        max_gap = max(max_gap, gap)

        weighted_total_weight += weight
        if status == "MATCHED":
            result.matched_skills.append(skill_name)
            weighted_matched_weight += weight
        else:
            result.missing_skills.append(skill_name)

        if mandatory:
            mandatory_required += 1
            if status == "MATCHED":
                mandatory_matched += 1

    n = result.total_required_skills
    result.skills_matched = len(result.matched_skills)
    result.skills_missing = len(result.missing_skills)
    result.mandatory_required = mandatory_required
    result.mandatory_matched = mandatory_matched

    result.match_percentage = round((result.skills_matched / n) * 100, 2) if n else 0.0
    result.mandatory_match_percentage = (
        round((mandatory_matched / mandatory_required) * 100, 2) if mandatory_required else 100.0
    )
    result.weighted_match_percentage = (
        round((weighted_matched_weight / weighted_total_weight) * 100, 2)
        if weighted_total_weight else 0.0
    )
    result.average_skill_gap = round(total_gap / n, 2) if n else 0.0
    result.max_skill_gap = max_gap

    return result
