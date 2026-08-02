"""
Recording Chunker — Flask Application Entry Point

Serves:
  - REST API at /api/recordings/*
  - Frontend static files from ../client/
  - SQLite database (zero external DB dependencies)
"""
import os
import sys
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from config import Config
from database import init_db
from routes.recordings import bp as recordings_bp

# Fix Windows console encoding for Unicode
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# --- Create Flask App -----------------------------------------------------

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "..", "client"),
    static_url_path="",
)

app.config["MAX_CONTENT_LENGTH"] = Config.MAX_FILE_SIZE

# Enable CORS for all routes
CORS(app)

# --- Ensure required directories exist ------------------------------------

for folder in [Config.UPLOAD_FOLDER, Config.CHUNKING_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
        print(f"[DIR] Created directory: {folder}")

# --- Initialize SQLite database -------------------------------------------

init_db()

# --- Register Blueprints -------------------------------------------------

app.register_blueprint(recordings_bp)

# --- Health Check ---------------------------------------------------------

@app.route("/api/health")
def health():
    from datetime import datetime, timezone
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})

# --- Serve Frontend -------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": f"File too large. Maximum size is {Config.MAX_FILE_SIZE // (1024*1024)}MB."}), 413


@app.errorhandler(404)
def not_found(error):
    # SPA fallback
    try:
        return send_from_directory(app.static_folder, "index.html")
    except Exception:
        return jsonify({"error": "Not found"}), 404


# --- Run ------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n=== Recording Chunker ===")
    print(f"  URL:     http://localhost:{Config.PORT}")
    print(f"  DB:      {Config.DB_PATH}")
    print(f"  Chunks:  {Config.CHUNK_DURATION}s ({Config.CHUNK_DURATION // 60} min)")
    print(f"  Overlap: {Config.OVERLAP_DURATION}s ({Config.OVERLAP_DURATION // 60} min)")
    print(f"  Stride:  {Config.STRIDE}s ({Config.STRIDE // 60} min)\n")

    app.run(host="0.0.0.0", port=Config.PORT, debug=True)
