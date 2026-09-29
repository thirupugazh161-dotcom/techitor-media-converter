import os
import re
import uuid
import json
import time
import shutil
import threading
import subprocess

from flask import Flask, request, jsonify, send_file
import imageio_ffmpeg


# ============================================================
# APP SETUP
# ============================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)

# 500 MB maximum upload
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

# Use the FFmpeg bundled with imageio-ffmpeg.
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ALLOWED_FORMATS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm",
}

jobs = {}
jobs_lock = threading.Lock()


# ============================================================
# JOB / FILE HELPERS
# ============================================================

def job_directory(job_id):
    path = os.path.join(TEMP_DIR, job_id)
    os.makedirs(path, exist_ok=True)
    return path


def job_state_file(job_id):
    return os.path.join(job_directory(job_id), "job.json")


def save_job(job_id, **updates):
    """Persist job state to disk so every Render worker can read it."""
    path = job_state_file(job_id)

    with jobs_lock:
        current = dict(jobs.get(job_id, {}))
        current.update(updates)
        jobs[job_id] = current

    tmp_path = path + ".tmp"

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False)

        os.replace(tmp_path, path)
    except Exception:
        # Keep the in-memory copy even if disk persistence fails.
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    return current


def load_job(job_id):
    """Load job from memory first, then from disk."""
    with jobs_lock:
        job = jobs.get(job_id)

    if job is not None:
        return dict(job)

    path = job_state_file(job_id)

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with jobs_lock:
            jobs[job_id] = dict(data)

        return data
    except Exception:
        return None


def safe_download_name(filename, output_format):
    base = os.path.splitext(os.path.basename(filename))[0]
    base = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip()

    if not base:
        base = "converted_file"

    return f"{base}.{output_format}"


# ============================================================
# MEDIA INFORMATION
# ============================================================

def ffmpeg_probe(input_file):
    """Return FFmpeg stderr for the input file."""
    result = subprocess.run(
        [
            FFMPEG,
            "-hide_banner",
            "-i",
            input_file,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stderr


def get_duration(input_file):
    try:
        output = ffmpeg_probe(input_file)

        match = re.search(
            r"Duration:\s*(\d+):(\d+):([\d.]+)",
            output,
            re.IGNORECASE,
        )

        if not match:
            return 0.0

        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))

        return hours * 3600 + minutes * 60 + seconds

    except Exception:
        return 0.0


def has_audio(input_file):
    try:
        output = ffmpeg_probe(input_file)
        return bool(re.search(r"Stream .*Audio:", output, re.IGNORECASE))
    except Exception:
        return False


def has_video(input_file):
    try:
        output = ffmpeg_probe(input_file)
        return bool(re.search(r"Stream .*Video:", output, re.IGNORECASE))
    except Exception:
        return False


# ============================================================
# FFMPEG COMMAND
# ============================================================

def build_command(input_file, output_file, output_format):
    """
    Build a reliable FFmpeg command for each supported output.
    """

    command = [
        FFMPEG,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_file,
    ]

    # -------------------------
    # MP3
    # -------------------------
    if output_format == "mp3":
        command += [
            "-map", "0:a:0",
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            "-ar", "44100",
            output_file,
        ]

    # -------------------------
    # WAV
    # -------------------------
    elif output_format == "wav":
        command += [
            "-map", "0:a:0",
            "-vn",
            "-c:a", "pcm_s16le",
            "-ar", "44100",
            output_file,
        ]

    # -------------------------
    # M4A
    # -------------------------
    elif output_format == "m4a":
        command += [
            "-map", "0:a:0",
            "-vn",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-movflags", "+faststart",
            output_file,
        ]

    # -------------------------
    # MP4
    # -------------------------
    elif output_format == "mp4":
        command += [
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_file,
        ]

    # -------------------------
    # MOV
    # -------------------------
    elif output_format == "mov":
        # MPEG-4 Part 2 is used instead of libx264 for better
        # compatibility with restricted FFmpeg builds.
        command += [
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:v", "mpeg4",
            "-q:v", "3",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            output_file,
        ]

    # -------------------------
    # MKV
    # -------------------------
    elif output_format == "mkv":
        command += [
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            output_file,
        ]

    # -------------------------
    # WEBM
    # -------------------------
    elif output_format == "webm":
        command += [
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:v", "libvpx-vp9",
            "-crf", "30",
            "-b:v", "0",
            "-c:a", "libopus",
            "-b:a", "128k",
            output_file,
        ]

    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    return command


# ============================================================
# CONVERSION WORKER
# ============================================================

def convert_worker(
    job_id,
    input_file,
    output_file,
    output_format,
    original_name,
):
    try:
        # -------------------------
        # Validate input
        # -------------------------
        if not os.path.exists(input_file):
            raise FileNotFoundError(
                "Uploaded input file was not found."
            )

        input_size = os.path.getsize(input_file)

        if input_size <= 0:
            raise RuntimeError("Uploaded file is empty.")

        save_job(
            job_id,
            status="starting",
            progress=1,
            message="Preparing conversion...",
            error=None,
        )

        # -------------------------
        # Validate media streams
        # -------------------------
        audio_outputs = {"mp3", "wav", "m4a"}
        video_outputs = {"mp4", "mov", "mkv", "webm"}

        if output_format in audio_outputs and not has_audio(input_file):
            raise RuntimeError(
                "This file does not contain an audio stream."
            )

        if output_format in video_outputs and not has_video(input_file):
            raise RuntimeError(
                "This file does not contain a video stream."
            )

        duration = get_duration(input_file)

        # -------------------------
        # Build FFmpeg command
        # -------------------------
        command = build_command(
            input_file,
            output_file,
            output_format,
        )

        # Put progress output before the input/output arguments.
        command = (
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-progress", "pipe:1", "-nostats", "-i", input_file]
            + command[command.index("-map"):]
        )

        save_job(
            job_id,
            status="converting",
            progress=2,
            message="Converting...",
        )

        # -------------------------
        # Run FFmpeg
        # -------------------------
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        stderr_lines = []

        def read_stderr():
            try:
                for line in process.stderr:
                    line = line.strip()
                    if line:
                        stderr_lines.append(line)
            except Exception:
                pass

        stderr_thread = threading.Thread(
            target=read_stderr,
            daemon=True,
        )
        stderr_thread.start()

        # -------------------------
        # Read progress
        # -------------------------
        while True:
            line = process.stdout.readline()

            if not line:
                if process.poll() is not None:
                    break
                continue

            line = line.strip()

            if line.startswith("out_time_ms="):
                try:
                    time_ms = int(line.split("=", 1)[1])
                    current_seconds = time_ms / 1_000_000

                    if duration > 0:
                        progress = (current_seconds / duration) * 100
                        progress = max(2, min(99, progress))

                        save_job(
                            job_id,
                            status="converting",
                            progress=round(progress, 1),
                            message=f"Converting... {round(progress, 1)}%",
                        )
                except Exception:
                    pass

        process.wait()
        stderr_thread.join(timeout=3)

        # -------------------------
        # FFmpeg error
        # -------------------------
        if process.returncode != 0:
            error_text = "\n".join(stderr_lines).strip()

            if not error_text:
                error_text = (
                    f"FFmpeg exited with code {process.returncode}."
                )

            raise RuntimeError(error_text[-5000:])

        # -------------------------
        # Output validation
        # -------------------------
        if not os.path.exists(output_file):
            raise FileNotFoundError(
                "FFmpeg completed, but the output file was not created."
            )

        output_size = os.path.getsize(output_file)

        if output_size <= 0:
            raise RuntimeError(
                "FFmpeg created an empty output file."
            )

        download_name = safe_download_name(
            original_name,
            output_format,
        )

        # -------------------------
        # SUCCESS
        # -------------------------
        save_job(
            job_id,
            status="completed",
            progress=100,
            message="Conversion completed successfully!",
            filename=download_name,
            output_file=output_file,
            error=None,
        )

    except Exception as e:
        save_job(
            job_id,
            status="error",
            progress=0,
            message="Conversion failed.",
            error=str(e),
        )

    finally:
        # Delete only the input.
        # Keep output until the user downloads it.
        try:
            if os.path.exists(input_file):
                os.remove(input_file)
        except Exception:
            pass


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET"])
def home():
    index_file = os.path.join(BASE_DIR, "index.html")

    if not os.path.exists(index_file):
        return jsonify({
            "error": "index.html not found"
        }), 404

    return send_file(index_file)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Techitor Media Converter",
        "ffmpeg": bool(FFMPEG),
    }), 200


# ============================================================
# START CONVERSION
# ============================================================

@app.route("/convert", methods=["POST"])
def convert():
    try:
        if "file" not in request.files:
            return jsonify({
                "error": "No file uploaded."
            }), 400

        uploaded_file = request.files["file"]

        if not uploaded_file or not uploaded_file.filename:
            return jsonify({
                "error": "No file selected."
            }), 400

        output_format = (
            request.form.get("format", "mp3")
            .strip()
            .lower()
        )

        if output_format not in ALLOWED_FORMATS:
            return jsonify({
                "error": f"Unsupported output format: {output_format}"
            }), 400

        job_id = uuid.uuid4().hex
        folder = job_directory(job_id)

        original_name = os.path.basename(
            uploaded_file.filename
        )

        extension = os.path.splitext(original_name)[1].lower()

        if not extension:
            extension = ".bin"

        input_file = os.path.join(
            folder,
            "input" + extension,
        )

        output_file = os.path.join(
            folder,
            "output." + output_format,
        )

        download_name = safe_download_name(
            original_name,
            output_format,
        )

        # -------------------------
        # Save upload
        # -------------------------
        uploaded_file.save(input_file)

        if not os.path.exists(input_file):
            raise RuntimeError(
                "Uploaded file could not be saved."
            )

        if os.path.getsize(input_file) <= 0:
            raise RuntimeError(
                "Uploaded file is empty."
            )

        # -------------------------
        # Save initial job
        # -------------------------
        save_job(
            job_id,
            status="starting",
            progress=0,
            message="Preparing conversion...",
            filename=download_name,
            output_file=output_file,
            original_name=original_name,
            error=None,
            created=time.time(),
        )

        # -------------------------
        # Start worker
        # -------------------------
        worker = threading.Thread(
            target=convert_worker,
            args=(
                job_id,
                input_file,
                output_file,
                output_format,
                original_name,
            ),
            daemon=True,
        )

        worker.start()

        return jsonify({
            "job_id": job_id,
            "status": "starting",
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# PROGRESS
# ============================================================

@app.route("/progress", methods=["GET"])
def progress():
    job_id = request.args.get("id", "").strip()

    if not job_id:
        return jsonify({
            "status": "error",
            "progress": 0,
            "error": "Missing job ID.",
        }), 400

    job = load_job(job_id)

    if not job:
        return jsonify({
            "status": "error",
            "progress": 0,
            "error": "Job not found.",
        }), 404

    return jsonify({
        "status": job.get("status", "starting"),
        "progress": job.get("progress", 0),
        "message": job.get("message", ""),
        "filename": job.get("filename", ""),
        "error": job.get("error"),
    }), 200


# ============================================================
# DOWNLOAD
# ============================================================

@app.route("/download", methods=["GET"])
def download():
    job_id = request.args.get("id", "").strip()

    if not job_id:
        return jsonify({
            "error": "Missing job ID."
        }), 400

    job = load_job(job_id)

    if not job:
        return jsonify({
            "error": "Job not found."
        }), 404

    if job.get("status") != "completed":
        return jsonify({
            "error": job.get(
                "error",
                "Conversion is not completed yet.",
            )
        }), 400

    output_file = job.get("output_file")

    if not output_file:
        return jsonify({
            "error": "Output file path is missing."
        }), 404

    if not os.path.exists(output_file):
        return jsonify({
            "error": "Converted file was not found."
        }), 404

    download_name = job.get(
        "filename",
        "converted_file",
    )

    return send_file(
        output_file,
        as_attachment=True,
        download_name=download_name,
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "error": "File is too large. Maximum size is 500 MB."
    }), 413


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error."
    }), 500


# ============================================================
# CLEAN OLD JOBS
# ============================================================

def cleanup_old_jobs():
    while True:
        time.sleep(1800)

        cutoff = time.time() - 3600

        try:
            for job_id in os.listdir(TEMP_DIR):
                job_dir = os.path.join(TEMP_DIR, job_id)

                if not os.path.isdir(job_dir):
                    continue

                try:
                    modified = os.path.getmtime(job_dir)

                    if modified < cutoff:
                        shutil.rmtree(
                            job_dir,
                            ignore_errors=True,
                        )

                        with jobs_lock:
                            jobs.pop(job_id, None)

                except Exception:
                    pass

        except Exception:
            pass


cleanup_thread = threading.Thread(
    target=cleanup_old_jobs,
    daemon=True,
)
cleanup_thread.start()


# ============================================================
# LOCAL RUN
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
    )
