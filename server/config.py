import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    PORT = int(os.getenv("PORT", 3000))
    CHUNK_DURATION = int(os.getenv("CHUNK_DURATION", 1200))       # 20 min in seconds
    OVERLAP_DURATION = int(os.getenv("OVERLAP_DURATION", 120))    # 2 min in seconds
    STRIDE = CHUNK_DURATION - OVERLAP_DURATION                     # 18 min

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, os.getenv("UPLOAD_FOLDER", "uploads"))
    CHUNKING_FOLDER = os.path.join(BASE_DIR, os.getenv("CHUNKING_FOLDER", "chunking"))
    DB_PATH = os.path.join(BASE_DIR, "recorder.db")
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", 2048)) * 1024 * 1024  # bytes

    ALLOWED_EXTENSIONS = {
        "mp3", "wav", "m4a", "aac", "ogg", "flac", "wma",
        "mp4", "webm", "mkv", "avi", "mov", "wmv", "flv",
    }

    MIME_MAP = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
    }
