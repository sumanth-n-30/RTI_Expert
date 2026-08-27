"""
RTI Rejection Prediction Model
================================
Algorithm  : Logistic Regression
Features   : TF-IDF Vectorization
Pipeline   : Text → TF-IDF → LogReg → Prediction + Confidence
"""

import json
import os
import pickle
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score,
    recall_score, f1_score, classification_report
)
from sklearn.pipeline import Pipeline
import re


# ─── Preprocessing ─────────────────────────────────────────────────────────────

def preprocess_text(text: str) -> str:
    """Clean and normalize raw RTI query text."""
    text = text.lower().strip()
    # Remove special characters but keep spaces and alphanumerics
    text = re.sub(r'[^\w\s]', ' ', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


# ─── Risk Level Mapper ──────────────────────────────────────────────────────────

def map_risk_level(prediction: str, confidence: float) -> str:
    """
    Map prediction + confidence to risk level.

    Risk is always from the perspective of REJECTION:
        0.0–0.4  → Low    (likely accepted)
        0.4–0.7  → Medium
        0.7–1.0  → High   (likely rejected)
    """
    if prediction == "rejected":
        rejection_prob = confidence
    else:
        rejection_prob = 1.0 - confidence

    if rejection_prob < 0.4:
        return "low"
    elif rejection_prob < 0.7:
        return "medium"
    else:
        return "high"


# ─── Model Training ─────────────────────────────────────────────────────────────

def load_dataset(path: str):
    """Load labeled dataset from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    queries = [preprocess_text(item["query"]) for item in data]
    labels  = [item["status"] for item in data]           # "accepted" | "rejected"
    return queries, labels


def build_pipeline() -> Pipeline:
    """Build TF-IDF + Logistic Regression pipeline."""
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),   # unigrams + bigrams
            max_features=5000,
            sublinear_tf=True,
            stop_words="english"
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",  # handles class imbalance
            solver="lbfgs"
        ))
    ])


def train(dataset_path: str, model_save_path: str = "rti_model.pkl"):
    """Full training run: load → split → train → evaluate → save."""

    print("=" * 55)
    print("  RTI Rejection Prediction Model — Training")
    print("=" * 55)

    # 1. Load data
    queries, labels = load_dataset(dataset_path)
    print(f"\n[1/4] Dataset loaded  : {len(queries)} samples")
    accepted_count = labels.count("accepted")
    rejected_count = labels.count("rejected")
    print(f"       Accepted       : {accepted_count}")
    print(f"       Rejected       : {rejected_count}")

    # 2. Train / Test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        queries, labels,
        test_size=0.2,
        random_state=42,
        stratify=labels
    )
    print(f"\n[2/4] Split           : {len(X_train)} train / {len(X_test)} test")

    # 3. Train
    print("\n[3/4] Training pipeline …")
    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)
    print("       Done.")

    # 4. Evaluate
    print("\n[4/4] Evaluation on test set:")
    y_pred = pipeline.predict(X_test)
    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, pos_label="rejected")
    rec  = recall_score(y_test, y_pred, pos_label="rejected")
    f1   = f1_score(y_test, y_pred, pos_label="rejected")

    print(f"\n       Accuracy  : {acc:.2%}")
    print(f"       Precision : {prec:.2%}  (rejected class)")
    print(f"       Recall    : {rec:.2%}  (rejected class)")
    print(f"       F1 Score  : {f1:.2%}  (rejected class)")
    print("\n       Full classification report:")
    print(classification_report(y_test, y_pred))

    # 5. Save model
    with open(model_save_path, "wb") as f:
        pickle.dump(pipeline, f)
    print(f"       Model saved → {model_save_path}")
    print("=" * 55)

    return pipeline


# ─── Inference ─────────────────────────────────────────────────────────────────

def load_model(model_path: str = "rti_model.pkl") -> Pipeline:
    """Load a saved model from disk."""
    with open(model_path, "rb") as f:
        return pickle.load(f)


def predict(query: str, pipeline: Pipeline) -> dict:
    """
    Analyze a single RTI query and return prediction JSON.

    Returns:
        {
            "prediction" : "accepted" | "rejected",
            "confidence" : float (0–100),
            "risk_level" : "low" | "medium" | "high"
        }
    """
    cleaned   = preprocess_text(query)
    proba     = pipeline.predict_proba([cleaned])[0]         # [p_accepted, p_rejected]
    classes   = list(pipeline.classes_)                       # e.g. ["accepted","rejected"]

    pred_idx  = int(np.argmax(proba))
    prediction = classes[pred_idx]
    conf_score = float(proba[pred_idx])
    risk_level = map_risk_level(prediction, conf_score)

    return {
        "prediction" : prediction,
        "confidence" : round(conf_score * 100, 2),
        "risk_level" : risk_level
    }


# ─── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
    DATASET_PATH = os.path.join(BASE_DIR, "dataset.json")
    MODEL_PATH   = os.path.join(BASE_DIR, "rti_model.pkl")

    # Train
    pipeline = train(DATASET_PATH, MODEL_PATH)

    # Quick demo
    demo_queries = [
        "What is the total budget allocated for road construction in 2023-24?",
        "Please provide the personal home address of government officer Ramesh Kumar.",
        "I want to know details.",
        "How many RTI applications were filed and disposed in the department last year?",
        "Give me all confidential cabinet meeting notes on the new land policy.",
    ]

    print("\n  Demo Predictions")
    print("-" * 55)
    for q in demo_queries:
        result = predict(q, pipeline)
        print(f"\nQuery     : {q[:65]}{'…' if len(q)>65 else ''}")
        print(f"Prediction: {result['prediction'].upper():10}  "
              f"Confidence: {result['confidence']:.2f}% "
              f"Risk: {result['risk_level'].upper()}")
