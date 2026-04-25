"""
Flask App — Job Search AI Agent
Routes:
  GET  /                    -> Main UI
  POST /api/global          -> Global search (single turn)
  POST /api/keychain/start  -> Start keychain session
  POST /api/keychain/chat   -> Keychain multi-turn chat
  POST /api/keychain/reset  -> Reset keychain session
  POST /api/resume          -> Resume analyser (file upload)
  GET  /api/health          -> Health check
"""

import os
import uuid
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB max upload

CORS(app)

keychain_sessions = {}
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/global", methods=["POST"])
def global_search():
    try:
        data = request.json
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        from agents.global_agent import run_global_agent
        result = run_global_agent(user_message)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@app.route("/api/keychain/start", methods=["POST"])
def keychain_start():
    session_id = str(uuid.uuid4())
    keychain_sessions[session_id] = {
        "state": "init", "role": None, "country": None,
        "experience": None, "city": None, "history": [],
    }
    return jsonify({"success": True, "session_id": session_id})


@app.route("/api/keychain/chat", methods=["POST"])
def keychain_chat():
    try:
        data = request.json
        session_id = data.get("session_id")
        user_message = data.get("message", "").strip()
        if not session_id or session_id not in keychain_sessions:
            return jsonify({"error": "Invalid or expired session."}), 400
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        from agents.keychain_agent import process_keychain_turn
        result = process_keychain_turn(keychain_sessions[session_id], user_message)
        keychain_sessions[session_id] = result["session"]
        response = {
            "success": True,
            "response": result["response"],
            "is_complete": result["is_complete"],
            "state": result["session"]["state"],
        }
        if result["is_complete"] and result["search_results"]:
            response["search_results"] = result["search_results"]
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@app.route("/api/keychain/reset", methods=["POST"])
def keychain_reset():
    data = request.json
    session_id = data.get("session_id")
    if session_id and session_id in keychain_sessions:
        del keychain_sessions[session_id]
    return jsonify({"success": True})


@app.route("/api/resume", methods=["POST"])
def resume_analyse():
    try:
        if "resume" not in request.files:
            return jsonify({"error": "No file uploaded. Use field name 'resume'."}), 400
        file = request.files["resume"]
        if file.filename == "":
            return jsonify({"error": "No file selected."}), 400
        if not _allowed_file(file.filename):
            return jsonify({"error": "Unsupported file type. Upload PDF, DOCX, or TXT."}), 400
        file_bytes = file.read()
        if len(file_bytes) == 0:
            return jsonify({"error": "Uploaded file is empty."}), 400
        from agents.resume_agent import run_resume_agent
        result = run_resume_agent(file_bytes, file.filename)
        return jsonify({"success": True, "data": result})
    except ValueError as e:
        return jsonify({"error": str(e), "success": False}), 400
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "nvidia_model": os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"),
        "google_cse_configured": bool(os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_CSE_ID")),
        "resume_analyser": "enabled",
    })


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "True").lower() == "true",
        host="0.0.0.0", port=5000
    )
