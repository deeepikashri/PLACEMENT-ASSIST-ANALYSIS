"""
Synthetic training dataset generator (spec section 13).

Generates several thousand synthetic candidate-job feature rows with a
`selected` target that is logically related to the features (higher
skill match, higher mandatory match, lower gaps, sufficient
experience, more projects/certifications -> higher chance of
selection) plus random noise so the problem is not perfectly
deterministic.

The exact scoring formula used to build the synthetic label is an
internal implementation detail and is intentionally not surfaced to
end users of the application.

Run:
    python models/generate_dataset.py
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.paths import TRAINING_DATASET_PATH, ensure_directories  # noqa: E402
from analysis.feature_engineering import FEATURE_COLUMNS  # noqa: E402

RANDOM_SEED = 42
N_SAMPLES = 6000


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def generate_synthetic_dataset(n_samples: int = N_SAMPLES, seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    total_required_skills = rng.integers(4, 12, size=n_samples)
    match_percentage = np.clip(rng.normal(60, 25, size=n_samples), 0, 100)
    skills_matched = np.round(total_required_skills * (match_percentage / 100)).astype(int)
    skills_matched = np.clip(skills_matched, 0, total_required_skills)
    skills_missing = total_required_skills - skills_matched
    # Recompute match percentage from the integer matched count for consistency
    match_percentage = np.where(
        total_required_skills > 0, (skills_matched / total_required_skills) * 100, 0.0
    )

    mandatory_required = np.clip(
        np.round(total_required_skills * rng.uniform(0.4, 0.8, size=n_samples)).astype(int), 1, None
    )
    mandatory_required = np.minimum(mandatory_required, total_required_skills)
    mandatory_match_ratio = np.clip(rng.normal(0.65, 0.28, size=n_samples), 0, 1)
    mandatory_matched = np.round(mandatory_required * mandatory_match_ratio).astype(int)
    mandatory_matched = np.clip(mandatory_matched, 0, mandatory_required)
    mandatory_match_percentage = np.where(
        mandatory_required > 0, (mandatory_matched / mandatory_required) * 100, 100.0
    )

    average_skill_gap = np.clip(rng.exponential(1.0, size=n_samples), 0, 5)
    max_skill_gap = np.clip(average_skill_gap + rng.exponential(1.0, size=n_samples), 0, 5)

    required_experience = rng.choice([0, 0.5, 1, 2, 3, 5], size=n_samples,
                                      p=[0.15, 0.1, 0.35, 0.25, 0.1, 0.05])
    student_experience = np.clip(
        required_experience + rng.normal(0, 1.2, size=n_samples), 0, 15
    )
    experience_gap = np.clip(required_experience - student_experience, 0, None)

    projects = rng.integers(0, 8, size=n_samples)
    certifications = rng.integers(0, 5, size=n_samples)

    # ---- Internal (hidden) scoring logic used only to generate a
    # logically-consistent synthetic label. Not exposed to end users. ----
    z = (
        0.045 * match_percentage
        + 0.035 * mandatory_match_percentage
        - 0.55 * average_skill_gap
        - 0.35 * max_skill_gap
        - 0.9 * experience_gap
        + 0.22 * projects
        + 0.30 * certifications
        - 4.2
    )
    probability = _sigmoid(z)
    noise = rng.normal(0, 0.12, size=n_samples)
    noisy_probability = np.clip(probability + noise, 0.01, 0.99)
    selected = (rng.uniform(0, 1, size=n_samples) < noisy_probability).astype(int)

    df = pd.DataFrame({
        "student_id": [f"SYN{i:05d}" for i in range(n_samples)],
        "job_id": rng.integers(1, 10, size=n_samples),
        "total_required_skills": total_required_skills,
        "skills_matched": skills_matched,
        "skills_missing": skills_missing,
        "match_percentage": np.round(match_percentage, 2),
        "mandatory_required": mandatory_required,
        "mandatory_matched": mandatory_matched,
        "mandatory_match_percentage": np.round(mandatory_match_percentage, 2),
        "average_skill_gap": np.round(average_skill_gap, 2),
        "max_skill_gap": np.round(max_skill_gap, 2),
        "student_experience": np.round(student_experience, 2),
        "required_experience": required_experience,
        "experience_gap": np.round(experience_gap, 2),
        "projects": projects,
        "certifications": certifications,
        "selected": selected,
    })

    # Sanity check: all model feature columns must be present
    missing_cols = [c for c in FEATURE_COLUMNS if c not in df.columns]
    assert not missing_cols, f"Generated dataset is missing feature columns: {missing_cols}"

    return df


def main():
    ensure_directories()
    df = generate_synthetic_dataset()
    df.to_csv(TRAINING_DATASET_PATH, index=False)
    print(f"Generated {len(df)} synthetic rows -> {TRAINING_DATASET_PATH}")
    print(f"Selected rate: {df['selected'].mean():.2%}")


if __name__ == "__main__":
    main()
