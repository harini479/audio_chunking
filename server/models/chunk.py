"""
Chunk model — CRUD operations using SQLite.
"""
import uuid
from datetime import datetime, timezone
from database import get_connection


def _row_to_dict(row) -> dict | None:
    """Convert sqlite3.Row to a JSON-friendly dict with camelCase keys."""
    if row is None:
        return None
    return {
        "_id": row["id"],
        "recordingId": row["recording_id"],
        "chunkIndex": row["chunk_index"],
        "filename": row["filename"],
        "filepath": row["filepath"],
        "startTime": row["start_time"],
        "endTime": row["end_time"],
        "duration": row["duration"],
        "size": row["size"],
        "createdAt": row["created_at"],
    }


def create_chunk(recording_id: str, chunk_index: int, filename: str,
                 filepath: str, start_time: float, end_time: float,
                 duration: float, size: int) -> dict:
    """Insert a new chunk and return it as a dict."""
    conn = get_connection()
    chunk_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO chunks
           (id, recording_id, chunk_index, filename, filepath,
            start_time, end_time, duration, size, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (chunk_id, recording_id, chunk_index, filename, filepath,
         start_time, end_time, duration, size, now),
    )
    conn.commit()

    return {
        "_id": chunk_id,
        "recordingId": recording_id,
        "chunkIndex": chunk_index,
        "filename": filename,
        "filepath": filepath,
        "startTime": start_time,
        "endTime": end_time,
        "duration": duration,
        "size": size,
        "createdAt": now,
    }


def get_chunks_for_recording(recording_id: str) -> list:
    """Return all chunks for a recording, ordered by index."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM chunks WHERE recording_id = ? ORDER BY chunk_index ASC",
        (recording_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_chunk_by_filename(filename: str) -> dict | None:
    """Find a single chunk by its filename."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM chunks WHERE filename = ?", (filename,)
    ).fetchone()
    return _row_to_dict(row)


def delete_chunks_for_recording(recording_id: str) -> int:
    """Delete all chunks belonging to a recording. Returns count deleted."""
    conn = get_connection()
    result = conn.execute(
        "DELETE FROM chunks WHERE recording_id = ?", (recording_id,)
    )
    conn.commit()
    return result.rowcount
