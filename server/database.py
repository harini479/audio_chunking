"""
Database module — SQLite connection and schema initialization.
Pure Python, zero external dependencies.
"""
import sqlite3
import threading
from config import Config

# Thread-local storage for connections (SQLite connections aren't thread-safe)
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "connection") or _local.connection is None:
        _local.connection = sqlite3.connect(Config.DB_PATH)
        _local.connection.row_factory = sqlite3.Row  # Access columns by name
        _local.connection.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        _local.connection.execute("PRAGMA foreign_keys=ON")
    return _local.connection


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS recordings (
            id              TEXT PRIMARY KEY,
            original_name   TEXT NOT NULL,
            filename        TEXT NOT NULL UNIQUE,
            filepath        TEXT NOT NULL,
            mimetype        TEXT NOT NULL,
            size            INTEGER NOT NULL,
            duration        REAL DEFAULT 0,
            status          TEXT DEFAULT 'processing',
            chunk_count     INTEGER DEFAULT 0,
            error_message   TEXT,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id              TEXT PRIMARY KEY,
            recording_id    TEXT NOT NULL,
            chunk_index     INTEGER NOT NULL,
            filename        TEXT NOT NULL,
            filepath        TEXT NOT NULL,
            start_time      REAL NOT NULL,
            end_time        REAL NOT NULL,
            duration        REAL NOT NULL,
            size            INTEGER DEFAULT 0,
            created_at      TEXT NOT NULL,
            FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE CASCADE,
            UNIQUE (recording_id, chunk_index)
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_recording ON chunks(recording_id);
    """)
    conn.commit()
    print("[OK] SQLite database initialized at:", Config.DB_PATH)
