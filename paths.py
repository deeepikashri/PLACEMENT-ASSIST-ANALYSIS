"""
Centralized, project-safe path resolution.

Every module that needs a file path (database, model, dataset, temp
resume storage) should import from here instead of hardcoding paths.
This guarantees the application runs correctly regardless of the
current working directory it is launched from.
"""

import os

# Root of the project (the directory that contains app.py)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_DIR = os.path.join(PROJECT_ROOT, "database")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
TEMP_DIR = os.path.join(PROJECT_ROOT, "data", "temp_uploads")

# NOTE: the database is now MySQL (see database/config.py for connection
# settings), so there is no local .db file path anymore.
TRAINING_DATASET_PATH = os.path.join(DATA_DIR, "training_dataset.csv")
MODEL_PATH = os.path.join(MODELS_DIR, "job_fit_model.joblib")
MODEL_METADATA_PATH = os.path.join(MODELS_DIR, "model_metadata.joblib")
SKILL_DICTIONARY_PATH = os.path.join(DATA_DIR, "skill_dictionary.json")


def ensure_directories() -> None:
    """Create all directories the app depends on if they do not exist."""
    for directory in (DATA_DIR, MODELS_DIR, TEMP_DIR, DATABASE_DIR):
        os.makedirs(directory, exist_ok=True)
