"""
Recording model — CRUD operations using SQLite.
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
        "originalName": row["original_name"],
        "filename": row["filename"],
        "filepath": row["filepath"],
        "mimetype": row["mimetype"],
        "size": row["size"],
        "duration": row["duration"],
        "status": row["status"],
        "chunkCount": row["chunk_count"],
        "errorMessage": row["error_message"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def create_recording(original_name: str, filename: str, filepath: str,
                     mimetype: str, size: int) -> dict:
    """Insert a new recording and return it as a dict."""
    conn = get_connection()
    rec_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO recordings
           (id, original_name, filename, filepath, mimetype, size, duration,
            status, chunk_count, error_message, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, 'processing', 0, NULL, ?, ?)""",
        (rec_id, original_name, filename, filepath, mimetype, size, now, now),
    )
    conn.commit()

    return {
        "_id": rec_id,
        "originalName": original_name,
        "filename": filename,
        "filepath": filepath,
        "mimetype": mimetype,
        "size": size,
        "duration": 0,
        "status": "processing",
        "chunkCount": 0,
        "errorMessage": None,
        "createdAt": now,
        "updatedAt": now,
    }


def get_all_recordings() -> list:
    """Return all recordings sorted by newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recordings ORDER BY created_at DESC"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_recording_by_id(recording_id: str) -> dict | None:
    """Find a single recording by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM recordings WHERE id = ?", (recording_id,)
    ).fetchone()
    return _row_to_dict(row)


def update_recording(recording_id: str, updates: dict) -> bool:
    """Partially update a recording. Accepts camelCase or snake_case keys."""
    conn = get_connection()

    # Map camelCase keys to DB column names
    key_map = {
        "status": "status",
        "duration": "duration",
        "chunkCount": "chunk_count",
        "chunk_count": "chunk_count",
        "errorMessage": "error_message",
        "error_message": "error_message",
    }

    set_clauses = []
    values = []
    for key, value in updates.items():
        col = key_map.get(key)
        if col:
            set_clauses.append(f"{col} = ?")
            values.append(value)

    if not set_clauses:
        return False

    set_clauses.append("updated_at = ?")
    values.append(datetime.now(timezone.utc).isoformat())
    values.append(recording_id)

    sql = f"UPDATE recordings SET {', '.join(set_clauses)} WHERE id = ?"
    result = conn.execute(sql, values)
    conn.commit()
    return result.rowcount > 0


def delete_recording(recording_id: str) -> bool:
    """Delete a recording. Returns True on success."""
    conn = get_connection()
    result = conn.execute("DELETE FROM recordings WHERE id = ?", (recording_id,))
    conn.commit()
    return result.rowcount > 0
