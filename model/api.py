"""
RTI Rejection Prediction Model — REST API (Ollama Edition)
===========================================================
Uses your local Ollama model instead of any cloud API.
No API key needed — runs 100% offline.

Setup:
    1. Make sure Ollama is running  →  ollama serve
    2. Pull a model if needed       →  ollama pull llama3
    3. Install dependencies         →  pip install flask flask-cors requests scikit-learn numpy
    4. Run this file                →  python api.py

Endpoints:
    GET  /health          → server status + ollama connection check
    POST /analyze         → predict single RTI query
    POST /analyze/batch   → predict multiple queries
    POST /retrain         → retrain the sklearn model
    GET  /models          → list available ollama models
"""

import os
import json
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from model import load_model, predict, train
import sys
import os

# Add rag directory to path so we can import vector_db
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag"))
from vector_db import db

app = Flask(__name__)
CORS(app)

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH   = os.path.join(BASE_DIR, "rti_model.pkl")
DATASET_PATH = os.path.join(BASE_DIR, "dataset.json")

# ── Ollama config ──────────────────────────────────────────────────────────────
OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3")   # change to your model


# ── Load sklearn model on startup ─────────────────────────────────────────────
if not os.path.exists(MODEL_PATH):
    print("[startup] No saved model found — training now …")
    pipeline = train(DATASET_PATH, MODEL_PATH)
else:
    print(f"[startup] Loading sklearn model from {MODEL_PATH}")
    pipeline = load_model(MODEL_PATH)

print(f"[startup] Ollama URL   : {OLLAMA_URL}")
print(f"[startup] Ollama Model : {OLLAMA_MODEL}")


# ── Ollama helpers ─────────────────────────────────────────────────────────────

def ollama_is_running():
    """Check if Ollama server is up."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_ollama_models():
    """Return list of locally installed Ollama models."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def ask_ollama(prompt: str, model: str = None) -> str:
    """Send a prompt to Ollama and return the text response."""
    model = model or OLLAMA_MODEL
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=60
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def parse_json_from_text(text: str) -> dict:
    """Safely extract JSON from Ollama response (handles extra text)."""
    # Try direct parse first
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try extracting JSON block with regex
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    raise ValueError(f"Could not parse JSON from Ollama response: {text[:200]}")


def analyze_with_ollama(query: str, model: str = None) -> dict:
    """
    Use Ollama LLM to analyze an RTI query.
    Returns same format as the sklearn model:
    { prediction, confidence, risk_level }
    """
    prompt = f"""You are a helpful assistant checking RTI (Right to Information) queries for common issues.
Analyze the following RTI query and predict if it will be accepted or rejected by a Public Information Officer.

Rejection signals to check:
- Requests for personal/private info (salary, address, phone, Aadhaar, PAN of individuals)
- Requests for third-party private information
- Queries related to national security, defense, intelligence
- Cabinet deliberations and confidential government notes
- Ongoing investigation or court case details
- Identity of informers or whistleblowers
- Vague, unclear, or meaningless queries

RTI Query: "{query}"

Respond ONLY with a valid JSON object. No explanation, no extra text, just JSON:
{{
  "prediction": "accepted" or "rejected",
  "confidence": a float between 0.0 and 1.0,
  "risk_level": "low" or "medium" or "high"
}}"""

    raw = ask_ollama(prompt, model)
    result = parse_json_from_text(raw)

    # Validate and normalize
    prediction = str(result.get("prediction", "")).lower()
    if prediction not in ("accepted", "rejected"):
        prediction = "rejected"

    confidence = float(result.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, round(confidence, 4)))

    risk_level = str(result.get("risk_level", "")).lower()
    if risk_level not in ("low", "medium", "high"):
        # derive from confidence
        rejection_prob = confidence if prediction == "rejected" else 1 - confidence
        if rejection_prob < 0.4:
            risk_level = "low"
        elif rejection_prob < 0.7:
            risk_level = "medium"
        else:
            risk_level = "high"

    return {
        "prediction": prediction,
        "confidence": confidence,
        "risk_level": risk_level,
        "source": "ollama"
    }


def analyze_with_sklearn(query: str) -> dict:
    """Fallback to sklearn model if Ollama is unavailable."""
    result = predict(query, pipeline)
    result["source"] = "sklearn"
    return result


def smart_analyze(query: str, model: str = None) -> dict:
    """
    Try Ollama first. Fall back to sklearn model if Ollama fails.
    """
    if ollama_is_running():
        try:
            return analyze_with_ollama(query, model)
        except Exception as e:
            print(f"[ollama] Error: {e} — falling back to sklearn")
    return analyze_with_sklearn(query)

def is_rti_query(q):
    keywords = [
        "rti", "information", "beneficiary", "salary",
        "government record", "scheme", "details of employees",
        "job card", "wages", "pension"
    ]
    return any(k in q.lower() for k in keywords)


def is_greeting(q):
    return q.lower() in ["hi", "hello", "hey"]


def is_smalltalk(q):
    smalltalk = [
        "how are you", "who are you",
        "what can you do", "good morning"
    ]
    return any(x in q.lower() for x in smalltalk)

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    ollama_up = ollama_is_running()
    return jsonify({
        "status"       : "ok",
        "model"        : "RTI Rejection Predictor v2.0 (Ollama)",
        "ollama"       : "connected" if ollama_up else "offline",
        "ollama_url"   : OLLAMA_URL,
        "ollama_model" : OLLAMA_MODEL,
        "sklearn_model": "loaded"
    })


@app.route("/models", methods=["GET"])
def list_models():
    """List all locally available Ollama models."""
    models = get_ollama_models()
    return jsonify({
        "ollama_models" : models,
        "current_model" : OLLAMA_MODEL,
        "ollama_url"    : OLLAMA_URL
    })


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    POST /analyze
    Body: { "query": "...", "model": "llama3" (optional) }
    Response: { "prediction": "...", "confidence": ..., "risk_level": "...", "source": "ollama|sklearn" }
    """
    body = request.get_json(silent=True)
    if not body or "query" not in body:
        return jsonify({"error": "Missing 'query' field."}), 400

    query = str(body["query"]).strip()
    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400

    model = body.get("model", None)

    try:
        result = smart_analyze(query, model)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze/ollama", methods=["POST"])
def analyze_ollama_only():
    """
    POST /analyze/ollama
    Force Ollama only — no sklearn fallback.
    Body: { "query": "...", "model": "llama3" (optional) }
    """
    body = request.get_json(silent=True)
    if not body or "query" not in body:
        return jsonify({"error": "Missing 'query' field."}), 400

    query = str(body["query"]).strip()
    model = body.get("model", None)

    if not ollama_is_running():
        return jsonify({"error": f"Ollama is not running at {OLLAMA_URL}. Run: ollama serve"}), 503

    try:
        result = analyze_with_ollama(query, model)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze/sklearn", methods=["POST"])
def analyze_sklearn_only():
    """
    POST /analyze/sklearn
    Force sklearn model only — no Ollama.
    """
    body = request.get_json(silent=True)
    if not body or "query" not in body:
        return jsonify({"error": "Missing 'query' field."}), 400

    query = str(body["query"]).strip()
    result = analyze_with_sklearn(query)
    return jsonify(result), 200


@app.route("/analyze/batch", methods=["POST"])
def analyze_batch():
    """
    POST /analyze/batch
    Body: { "queries": ["query1", "query2", ...], "model": "llama3" (optional) }
    Response: { "results": [...] }
    """
    body = request.get_json(silent=True)
    if not body or "queries" not in body:
        return jsonify({"error": "Missing 'queries' field."}), 400

    queries = body["queries"]
    if not isinstance(queries, list) or len(queries) == 0:
        return jsonify({"error": "'queries' must be a non-empty list."}), 400

    model = body.get("model", None)
    results = []
    for q in queries:
        if not isinstance(q, str) or not q.strip():
            results.append({"error": "Invalid query"})
        else:
            try:
                results.append(smart_analyze(q.strip(), model))
            except Exception as e:
                results.append({"error": str(e)})

    return jsonify({"results": results}), 200


@app.route("/retrain", methods=["POST"])
def retrain():
    """Retrain the sklearn model with current dataset.json."""
    global pipeline
    try:
        pipeline = train(DATASET_PATH, MODEL_PATH)
        return jsonify({"status": "retrained successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True)

    if not body or "query" not in body:
        return jsonify({"error": "Missing query"}), 400

    query = body["query"].strip()
    q = query.lower()

    # ── 1. FAST RULE-BASED INTENT (NO LLM) ──
    if q in ["hi", "hello", "hey"]:
        return jsonify({"reply": "Hey 👋 I'm your RTI assistant."})

    if q in ["bye", "goodbye"]:
        return jsonify({"reply": "Goodbye 👋"})

    if len(q.split()) < 3:
        return jsonify({"reply": "Please provide a proper RTI query."})

    # ── 2. ANALYSIS (FAST) ──
    result = smart_analyze(query)

    # ── 3. ONLY ONE LLM CALL (OPTIONAL) ──
    # Retrieve similar past cases from Vector DB
    try:
        similar_cases = db.search_cases(query, top_k=2)
        context = "Relevant Past Cases:\n"
        if similar_cases:
            for case in similar_cases:
                context += f"- Case Query: {case['query']}\n  Decision: {case['metadata'].get('decision')}\n"
        else:
            context += "None found.\n"
    except Exception as e:
        print(f"[RAG Error] {e}")
        context = "Relevant Past Cases: Error retrieving cases.\n"

    explanation = ask_ollama(
    f"""
You are a helpful assistant. Explain ONLY in 2-3 lines why the following RTI query might be accepted or rejected based on common rules.

{context}

Do NOT assume context like education or teaching unless given.

RTI Query:
{query}

Prediction: {result['prediction']}
"""
)

    if result["source"] == "ollama":
        try:
            # Conversational explanation with a helpful persona
            explanation = ask_ollama(
                f"""
                You are a helpful assistant. Explain simply in 2-3 lines why the following RTI query might be accepted or rejected based on common rules.
                
                {context}

                RTI Query:
                {query}

                Prediction: {result['prediction']}
                """
            )
        except:
            pass

    # ── 4. FINAL RESPONSE ──
    reply = explanation

    return jsonify({
        "reply": reply,
        "prediction": result["prediction"],
        "confidence": result["confidence"],
        "risk_level": result["risk_level"]
    })

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  RTI Expert API — Ollama Edition")
    print("="*55)
    print(f"  Ollama : {OLLAMA_URL}  ({'online' if ollama_is_running() else 'OFFLINE — run: ollama serve'})")
    print(f"  Model  : {OLLAMA_MODEL}")
    print("  Routes : /health  /analyze  /analyze/batch")
    print("         : /analyze/ollama  /analyze/sklearn  /models")
    print("="*55 + "\n")
    app.run(debug=True, port=5000)