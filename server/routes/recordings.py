"""
API Routes — /api/recordings/*

Endpoints:
  POST   /api/recordings/upload           Upload a recording -> triggers chunking
  GET    /api/recordings                   List all recordings
  GET    /api/recordings/<id>              Get recording + its chunks
  GET    /api/recordings/<id>/chunks       Get chunks for a recording
  GET    /api/recordings/chunks/file/<fn>  Stream/download a chunk file
  DELETE /api/recordings/<id>              Delete recording + chunks
"""
import os
import uuid
from flask import Blueprint, request, jsonify, Response, send_file
from config import Config
from models import recording as recording_model
from models import chunk as chunk_model
from services.chunking_service import chunk_recording_async, cleanup_chunks

bp = Blueprint("recordings", __name__, url_prefix="/api/recordings")


def _allowed_file(filename: str) -> bool:
    """Check if file extension is in the allow-list."""
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


# --- Upload ----------------------------------------------------------------

@bp.route("/upload", methods=["POST"])
def upload_recording():
    """Upload a recording file and start async chunking."""
    if "recording" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["recording"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "File type not supported. Use audio or video files."}), 415

    # Generate unique filename
    original_name = file.filename
    ext = os.path.splitext(original_name)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(Config.UPLOAD_FOLDER, unique_name)

    # Ensure upload dir exists
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    # Save file to disk
    file.save(filepath)
    file_size = os.path.getsize(filepath)

    # Determine mimetype
    mimetype = file.content_type or Config.MIME_MAP.get(ext, "application/octet-stream")

    # Create recording in DB
    rec = recording_model.create_recording(
        original_name=original_name,
        filename=unique_name,
        filepath=filepath,
        mimetype=mimetype,
        size=file_size,
    )

    recording_id = rec["_id"]

    # Fire off chunking in background thread
    chunk_recording_async(recording_id)

    return jsonify({
        "message": "Recording uploaded successfully. Chunking in progress...",
        "recording": {
            "_id": recording_id,
            "originalName": original_name,
            "size": file_size,
            "status": "processing",
        },
    }), 201


# --- List All Recordings ---------------------------------------------------

@bp.route("/", methods=["GET"])
def list_recordings():
    """Return all recordings sorted by newest first."""
    recordings = recording_model.get_all_recordings()
    return jsonify(recordings)


# --- Get Single Recording + Chunks -----------------------------------------

@bp.route("/<recording_id>", methods=["GET"])
def get_recording(recording_id):
    """Return a single recording with its chunks."""
    rec = recording_model.get_recording_by_id(recording_id)
    if not rec:
        return jsonify({"error": "Recording not found"}), 404

    chunks = chunk_model.get_chunks_for_recording(recording_id)
    rec["chunks"] = chunks
    return jsonify(rec)


# --- Get Chunks for a Recording --------------------------------------------

@bp.route("/<recording_id>/chunks", methods=["GET"])
def get_chunks(recording_id):
    """Return all chunks for a recording, sorted by index."""
    chunks = chunk_model.get_chunks_for_recording(recording_id)
    return jsonify(chunks)


# --- Stream / Download a Chunk File ----------------------------------------

@bp.route("/chunks/file/<filename>", methods=["GET"])
def stream_chunk(filename):
    """Stream or download a specific chunk file with range-request support."""
    chunk = chunk_model.get_chunk_by_filename(filename)
    if not chunk:
        return jsonify({"error": "Chunk not found"}), 404

    filepath = chunk["filepath"]
    if not os.path.exists(filepath):
        return jsonify({"error": "Chunk file not found on disk"}), 404

    ext = os.path.splitext(filename)[1].lower()
    content_type = Config.MIME_MAP.get(ext, "application/octet-stream")
    file_size = os.path.getsize(filepath)

    # Handle range requests for seeking in audio/video players
    range_header = request.headers.get("Range")
    if range_header:
        byte_range = range_header.replace("bytes=", "").split("-")
        start = int(byte_range[0])
        end = int(byte_range[1]) if byte_range[1] else file_size - 1
        length = end - start + 1

        def generate():
            with open(filepath, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return Response(
            generate(),
            status=206,
            mimetype=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    # Full file response
    return send_file(
        filepath,
        mimetype=content_type,
        as_attachment=False,
        download_name=filename,
    )


# --- Delete Recording + Chunks ---------------------------------------------

@bp.route("/<recording_id>", methods=["DELETE"])
def delete_recording(recording_id):
    """Delete a recording and all its chunks (files + DB)."""
    rec = recording_model.get_recording_by_id(recording_id)
    if not rec:
        return jsonify({"error": "Recording not found"}), 404

    # Delete chunk files + DB records
    cleanup_chunks(recording_id)

    # Delete original uploaded file
    if os.path.exists(rec["filepath"]):
        try:
            os.remove(rec["filepath"])
        except OSError:
            pass

    # Delete recording document
    recording_model.delete_recording(recording_id)

    return jsonify({"message": "Recording and all chunks deleted"})
