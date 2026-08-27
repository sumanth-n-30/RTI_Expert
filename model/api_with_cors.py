"""
RTI Rejection Prediction Model — REST API
==========================================
Endpoint : POST /analyze
Request  : { "query": "..." }
Response : { "prediction": "...", "confidence": ..., "risk_level": "..." }

Usage:
    pip install flask scikit-learn numpy
    python api.py
"""

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from model import load_model, predict, train

app = Flask(__name__)
CORS(app)  # Allow all origins — needed for the HTML tester page

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH   = os.path.join(BASE_DIR, "rti_model.pkl")
DATASET_PATH = os.path.join(BASE_DIR, "dataset.json")

# Load (or train if not found) on startup
if not os.path.exists(MODEL_PATH):
    print("[startup] No saved model found — training now …")
    pipeline = train(DATASET_PATH, MODEL_PATH)
else:
    print(f"[startup] Loading model from {MODEL_PATH}")
    pipeline = load_model(MODEL_PATH)


# ─── Health check ──────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": "RTI Rejection Predictor v1.0"})


# ─── Main prediction endpoint ──────────────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    POST /analyze
    Body: { "query": "<RTI query text>" }
    Returns prediction JSON as per spec.
    """
    body = request.get_json(silent=True)

    if not body or "query" not in body:
        return jsonify({
            "error": "Missing 'query' field in request body."
        }), 400

    query = str(body["query"]).strip()
    if not query:
        return jsonify({
            "error": "Query cannot be empty."
        }), 400

    result = predict(query, pipeline)
    return jsonify(result), 200


# ─── Retrain endpoint (optional) ──────────────────────────────────────────────

@app.route("/retrain", methods=["POST"])
def retrain():
    """
    POST /retrain
    Retrains the model with the current dataset.json.
    Useful after adding new labeled samples.
    """
    global pipeline
    try:
        pipeline = train(DATASET_PATH, MODEL_PATH)
        return jsonify({"status": "retrained successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Batch endpoint ────────────────────────────────────────────────────────────

@app.route("/analyze/batch", methods=["POST"])
def analyze_batch():
    """
    POST /analyze/batch
    Body: { "queries": ["query1", "query2", ...] }
    Returns: { "results": [ {...}, {...} ] }
    """
    body = request.get_json(silent=True)

    if not body or "queries" not in body:
        return jsonify({"error": "Missing 'queries' field."}), 400

    queries = body["queries"]
    if not isinstance(queries, list) or len(queries) == 0:
        return jsonify({"error": "'queries' must be a non-empty list."}), 400

    results = []
    for q in queries:
        if not isinstance(q, str) or not q.strip():
            results.append({"error": "Invalid query"})
        else:
            results.append(predict(q.strip(), pipeline))

    return jsonify({"results": results}), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)