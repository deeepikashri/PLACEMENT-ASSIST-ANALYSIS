"""
ML training pipeline (spec section 14).

Trains and compares:
    1. Logistic Regression
    2. Decision Tree
    3. Random Forest
    4. XGBoost (optional, only if the package is installed)

Evaluates each with accuracy, precision, recall, F1 and ROC-AUC on a
held-out test split, selects the best model by ROC-AUC, and saves it
(plus a StandardScaler and metadata) with Joblib so the Streamlit app
never has to retrain on startup.

Run:
    python models/train_model.py
"""

import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.paths import (  # noqa: E402
    TRAINING_DATASET_PATH, MODEL_PATH, MODEL_METADATA_PATH, ensure_directories,
)
from analysis.feature_engineering import FEATURE_COLUMNS  # noqa: E402

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

RANDOM_SEED = 42


def load_dataset() -> pd.DataFrame:
    if not os.path.exists(TRAINING_DATASET_PATH):
        raise FileNotFoundError(
            f"Training dataset not found at {TRAINING_DATASET_PATH}. "
            "Run `python models/generate_dataset.py` first."
        )
    return pd.read_csv(TRAINING_DATASET_PATH)


def evaluate(model, X_test, y_test, use_scaled_input) -> dict:
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1_score": f1_score(y_test, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_proba),
    }


def main():
    ensure_directories()
    df = load_dataset()

    X = df[FEATURE_COLUMNS].values
    y = df["selected"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    # Scale features for Logistic Regression; tree-based models don't need it
    # but we keep a single scaler for consistent inference-time transforms.
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    candidates = {}

    lr = LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)
    lr.fit(X_train_scaled, y_train)
    candidates["Logistic Regression"] = (lr, True)

    dt = DecisionTreeClassifier(max_depth=6, random_state=RANDOM_SEED)
    dt.fit(X_train, y_train)
    candidates["Decision Tree"] = (dt, False)

    rf = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=RANDOM_SEED)
    rf.fit(X_train, y_train)
    candidates["Random Forest"] = (rf, False)

    if XGBOOST_AVAILABLE:
        xgb = XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            use_label_encoder=False, eval_metric="logloss",
            random_state=RANDOM_SEED,
        )
        xgb.fit(X_train, y_train)
        candidates["XGBoost"] = (xgb, False)
    else:
        print("XGBoost not installed - skipping (optional model).")

    results = {}
    for name, (model, needs_scaling) in candidates.items():
        eval_X = X_test_scaled if needs_scaling else X_test
        metrics = evaluate(model, eval_X, y_test, needs_scaling)
        results[name] = metrics
        print(f"\n{name}:")
        for metric_name, value in metrics.items():
            print(f"  {metric_name:10s}: {value:.4f}")

    # Select best model by ROC-AUC
    best_name = max(results, key=lambda n: results[n]["roc_auc"])
    best_model, best_needs_scaling = candidates[best_name]
    print(f"\nBest model selected: {best_name} (ROC-AUC = {results[best_name]['roc_auc']:.4f})")

    # Persist model + scaler + metadata with Joblib
    joblib.dump(
        {
            "model": best_model,
            "scaler": scaler,
            "needs_scaling": best_needs_scaling,
            "feature_columns": FEATURE_COLUMNS,
        },
        MODEL_PATH,
    )
    joblib.dump(
        {
            "model_name": best_name,
            "all_results": results,
            "xgboost_available": XGBOOST_AVAILABLE,
        },
        MODEL_METADATA_PATH,
    )
    print(f"\nModel saved to {MODEL_PATH}")
    print(f"Metadata saved to {MODEL_METADATA_PATH}")


if __name__ == "__main__":
    main()
