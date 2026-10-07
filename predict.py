"""
Inference wrapper around the saved Joblib model (spec section 15).

The Streamlit app loads the model ONCE via `get_predictor()` and reuses
it — it never retrains on startup (spec section 14: "The application
should load the saved model rather than retraining every time.").
"""

import os
from typing import Dict

import joblib
import numpy as np

from utils.paths import MODEL_PATH

# Fit classification thresholds (spec section 15).
# Kept as a simple, clearly-defined, easy-to-modify constant.
FIT_THRESHOLDS = [
    (80, 100, "Excellent Fit"),
    (65, 79.999, "Good Fit"),
    (50, 64.999, "Moderate Fit"),
    (0, 49.999, "Low Fit"),
]

SELECTION_DISCLAIMER = (
    "Selection probability is an ML-based estimate based on the information "
    "analyzed by this system. It does not represent a guaranteed hiring outcome."
)


class ModelNotTrainedError(Exception):
    """Raised when the app tries to predict before a model has been trained."""


def classify_fit(selection_probability_pct: float) -> str:
    for low, high, label in FIT_THRESHOLDS:
        if low <= selection_probability_pct <= high:
            return label
    return "Low Fit"


class JobFitPredictor:
    """Loads the trained model bundle once and exposes a predict() method."""

    def __init__(self):
        if not os.path.exists(MODEL_PATH):
            raise ModelNotTrainedError(
                "No trained model found. Please run "
                "`python models/generate_dataset.py` and then "
                "`python models/train_model.py` before using the app."
            )
        bundle = joblib.load(MODEL_PATH)
        self.model = bundle["model"]
        self.scaler = bundle["scaler"]
        self.needs_scaling = bundle["needs_scaling"]
        self.feature_columns = bundle["feature_columns"]

    def predict_probability(self, feature_dict: Dict[str, float]) -> float:
        """
        Returns the selection probability as a percentage (0-100),
        rounded to 2 decimals.
        """
        vector = np.array([[feature_dict[col] for col in self.feature_columns]])
        if self.needs_scaling:
            vector = self.scaler.transform(vector)
        proba = self.model.predict_proba(vector)[0, 1]
        return round(float(proba) * 100, 2)


_predictor_instance = None


def get_predictor() -> JobFitPredictor:
    """Singleton accessor so the model is loaded from disk only once per process."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = JobFitPredictor()
    return _predictor_instance
