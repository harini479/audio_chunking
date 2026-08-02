"""
Chunking Service — Splits recordings into overlapping chunks using FFmpeg.

Chunking logic (20-min chunks, 2-min overlap):
  Stride = chunk_duration - overlap = 20 - 2 = 18 min
  Chunk 0:  0:00 → 20:00
  Chunk 1: 18:00 → 38:00
  Chunk 2: 36:00 → 56:00
  Chunk 3: 54:00 → 60:00  (remainder)

Uses `ffmpeg -ss <start> -t <duration> -c copy` for lossless, fast splitting.
"""
import os
import json
import subprocess
import threading
from config import Config
from models import recording as recording_model
from models import chunk as chunk_model
import static_ffmpeg

# Automatically downloads (if needed) and adds ffmpeg/ffprobe to PATH
static_ffmpeg.add_paths()


def get_media_duration(filepath: str) -> float:
    """Get media duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        filepath,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        duration = float(metadata["format"]["duration"])
        if duration <= 0:
            raise ValueError("Duration is zero or negative")
        return duration
    except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f"FFprobe failed: {e}")


def extract_chunk(input_path: str, output_path: str,
                  start_time: float, duration: float) -> None:
    """Extract a single chunk using FFmpeg with re-encoding to ensure clean headers for transcription."""
    cmd = [
        "ffmpeg",
        "-y",                       # overwrite output
        "-ss", str(start_time),     # seek to start
        "-i", input_path,           # input file
        "-t", str(duration),        # chunk duration
        # Re-encoding guarantees accurate timestamps and clean headers,
        # which AI transcription parsers strictly require.
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg error: {e.stderr}")


def format_time(seconds: float) -> str:
    """Format seconds to HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def chunk_recording(recording_id: str) -> list:
    """
    Main chunking function.
    Runs in a background thread — reads the recording, splits with FFmpeg,
    saves chunk files to CHUNKING_FOLDER, and writes chunk docs to MongoDB.
    """
    rec = recording_model.get_recording_by_id(recording_id)
    if not rec:
        raise ValueError(f"Recording not found: {recording_id}")

    try:
        # Mark as processing
        recording_model.update_recording(recording_id, {"status": "processing"})

        # Get duration via ffprobe
        total_duration = get_media_duration(rec["filepath"])
        recording_model.update_recording(recording_id, {"duration": total_duration})

        chunk_duration = Config.CHUNK_DURATION   # 1200s = 20 min
        overlap = Config.OVERLAP_DURATION        # 120s = 2 min
        stride = Config.STRIDE                   # 1080s = 18 min

        # Ensure chunking directory exists
        os.makedirs(Config.CHUNKING_FOLDER, exist_ok=True)

        # Calculate chunk boundaries
        chunks_plan = []
        start_time = 0.0
        chunk_index = 0

        while start_time < total_duration:
            end_time = min(start_time + chunk_duration, total_duration)
            actual_duration = end_time - start_time

            # Skip tiny remnants (< 5 seconds)
            if actual_duration < 5 and chunk_index > 0:
                break

            chunks_plan.append({
                "chunkIndex": chunk_index,
                "startTime": start_time,
                "endTime": end_time,
                "duration": actual_duration,
            })

            chunk_index += 1
            start_time += stride

        print(f"[SPLIT] Splitting \"{rec['originalName']}\" into {len(chunks_plan)} chunks...")

        # Extract each chunk
        ext = os.path.splitext(rec["filename"])[1]
        created_chunks = []

        for plan in chunks_plan:
            chunk_filename = f"{recording_id}_chunk_{plan['chunkIndex']:03d}{ext}"
            chunk_path = os.path.join(Config.CHUNKING_FOLDER, chunk_filename)

            print(f"  [CUT] Chunk {plan['chunkIndex'] + 1}/{len(chunks_plan)}: "
                  f"{format_time(plan['startTime'])} -> {format_time(plan['endTime'])}")

            extract_chunk(
                rec["filepath"],
                chunk_path,
                plan["startTime"],
                plan["duration"],
            )

            # Get file size
            file_size = os.path.getsize(chunk_path)

            # Save chunk to MongoDB
            chunk_doc = chunk_model.create_chunk(
                recording_id=recording_id,
                chunk_index=plan["chunkIndex"],
                filename=chunk_filename,
                filepath=chunk_path,
                start_time=plan["startTime"],
                end_time=plan["endTime"],
                duration=plan["duration"],
                size=file_size,
            )
            created_chunks.append(chunk_doc)

        # Update recording as completed
        recording_model.update_recording(recording_id, {
            "status": "completed",
            "chunkCount": len(created_chunks),
        })

        print(f"[OK] Chunking complete: {len(created_chunks)} chunks created")
        return created_chunks

    except Exception as e:
        print(f"[ERROR] Chunking failed for {rec.get('originalName', recording_id)}: {e}")

        # Mark as failed
        recording_model.update_recording(recording_id, {
            "status": "failed",
            "errorMessage": str(e),
        })

        # Clean up any partial chunks
        cleanup_chunks(recording_id)
        raise


def cleanup_chunks(recording_id: str) -> None:
    """Remove all chunk files and DB records for a recording."""
    chunks = chunk_model.get_chunks_for_recording(recording_id)
    for c in chunks:
        try:
            if os.path.exists(c["filepath"]):
                os.remove(c["filepath"])
        except OSError:
            print(f"  [WARN] Could not delete {c['filepath']}")
    chunk_model.delete_chunks_for_recording(recording_id)


def chunk_recording_async(recording_id: str) -> None:
    """Fire-and-forget: run chunking in a background thread."""
    thread = threading.Thread(
        target=chunk_recording,
        args=(recording_id,),
        daemon=True,
    )
    thread.start()
