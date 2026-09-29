import os
import re
import uuid
import time
import shutil
import threading
import subprocess

from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None


# =========================================================
# APP SETUP
# =========================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)

# Maximum upload size: 500 MB
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


# =========================================================
# FFMPEG
# =========================================================

def get_ffmpeg():
    """
    First try normal system ffmpeg.
    If unavailable, use imageio-ffmpeg bundled executable.
    """

    system_ffmpeg = shutil.which("ffmpeg")

    if system_ffmpeg:
        return system_ffmpeg

    if imageio_ffmpeg:
        return imageio_ffmpeg.get_ffmpeg_exe()

    return None


FFMPEG = get_ffmpeg()


# =========================================================
# JOB STORAGE
# =========================================================

jobs = {}

jobs_lock = threading.Lock()


# =========================================================
# SUPPORTED FORMATS
# =========================================================

SUPPORTED_FORMATS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm",
}


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Techitor Media Converter"
    }), 200


# =========================================================
# HOME
# =========================================================

@app.route("/", methods=["GET"])
def home():
    index_file = os.path.join(BASE_DIR, "index.html")

    if not os.path.exists(index_file):
        return jsonify({
            "error": "index.html not found"
        }), 404

    return send_file(index_file)


# =========================================================
# GET MEDIA DURATION
# =========================================================

def get_duration(input_file):
    """
    Uses ffmpeg to read the media duration.
    Returns duration in seconds.
    """

    if not FFMPEG:
        return 0

    try:
        command = [
            FFMPEG,
            "-i",
            input_file
        ]

        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        output = process.stderr

        match = re.search(
            r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
            output
        )

        if not match:
            return 0

        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))

        return (
            hours * 3600
            + minutes * 60
            + seconds
        )

    except Exception:
        return 0


# =========================================================
# OUTPUT SETTINGS
# =========================================================

def get_ffmpeg_arguments(input_file, output_file, output_format):
    """
    Returns the correct FFmpeg arguments for each format.
    """

    output_format = output_format.lower()

    # -------------------------
    # MP3
    # -------------------------
    if output_format == "mp3":
        return [
            FFMPEG,
            "-y",
            "-i", input_file,
            "-vn",
            "-codec:a", "libmp3lame",
            "-q:a", "2",
            "-progress", "pipe:1",
            "-nostats",
            output_file
        ]

    # -------------------------
    # WAV
    # -------------------------
    if output_format == "wav":
        return [
            FFMPEG,
            "-y",
            "-i", input_file,
            "-vn",
            "-codec:a", "pcm_s16le",
            "-progress", "pipe:1",
            "-nostats",
            output_file
        ]

    # -------------------------
    # M4A
    # -------------------------
    if output_format == "m4a":
        return [
            FFMPEG,
            "-y",
            "-i", input_file,
            "-vn",
            "-codec:a", "aac",
            "-b:a", "192k",
            "-progress", "pipe:1",
            "-nostats",
            output_file
        ]

    # -------------------------
    # MP4
    # -------------------------
    if output_format == "mp4":
        return [
            FFMPEG,
            "-y",
            "-i", input_file,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-nostats",
            output_file
        ]

    # -------------------------
    # MOV
    # -------------------------
    if output_format == "mov":
        return [
            FFMPEG,
            "-y",
            "-i", input_file,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-progress", "pipe:1",
            "-nostats",
            output_file
        ]

    # -------------------------
    # MKV
    # -------------------------
    if output_format == "mkv":
        return [
            FFMPEG,
            "-y",
            "-i", input_file,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-progress", "pipe:1",
            "-nostats",
            output_file
        ]

    # -------------------------
    # WEBM
    # -------------------------
    if output_format == "webm":
        return [
            FFMPEG,
            "-y",
            "-i", input_file,
            "-c:v", "libvpx-vp9",
            "-crf", "30",
            "-b:v", "0",
            "-c:a", "libopus",
            "-b:a", "128k",
            "-progress", "pipe:1",
            "-nostats",
            output_file
        ]

    raise ValueError(
        f"Unsupported output format: {output_format}"
    )


# =========================================================
# CONVERSION WORKER
# =========================================================

def conversion_worker(
    job_id,
    input_file,
    output_file,
    output_format,
    original_name
):

    try:

        with jobs_lock:
            jobs[job_id]["status"] = "starting"
            jobs[job_id]["progress"] = 0

        if not FFMPEG:
            raise RuntimeError(
                "FFmpeg is not available on the server."
            )

        # Get duration
        duration = get_duration(input_file)

        with jobs_lock:
            jobs[job_id]["duration"] = duration
            jobs[job_id]["status"] = "converting"

        command = get_ffmpeg_arguments(
            input_file,
            output_file,
            output_format
        )

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        last_progress = 0

        # Read FFmpeg progress
        while True:

            line = process.stdout.readline()

            if not line:
                if process.poll() is not None:
                    break
                continue

            line = line.strip()

            # FFmpeg reports:
            # out_time_ms=1234567
            if line.startswith("out_time_ms="):

                try:

                    out_time_ms = int(
                        line.split("=", 1)[1]
                    )

                    current_seconds = (
                        out_time_ms / 1_000_000
                    )

                    if duration > 0:

                        progress = int(
                            (
                                current_seconds
                                / duration
                            ) * 100
                        )

                        progress = max(
                            0,
                            min(99, progress)
                        )

                        if progress >= last_progress:
                            last_progress = progress

                            with jobs_lock:
                                jobs[job_id]["progress"] = progress

                except Exception:
                    pass

        # Read FFmpeg error output
        stderr_output = process.stderr.read()

        return_code = process.wait()

        # -------------------------
        # CONVERSION FAILED
        # -------------------------

        if return_code != 0:

            error_message = (
                stderr_output[-3000:]
                if stderr_output
                else "FFmpeg conversion failed."
            )

            raise RuntimeError(error_message)

        # Make sure output actually exists
        if not os.path.exists(output_file):
            raise RuntimeError(
                "FFmpeg finished but output file was not created."
            )

        # -------------------------
        # COMPLETE
        # -------------------------

        download_name = (
            os.path.splitext(
                secure_filename(original_name)
            )[0]
            + "."
            + output_format
        )

        with jobs_lock:

            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["filename"] = download_name
            jobs[job_id]["output_file"] = output_file

    except Exception as e:

        with jobs_lock:

            jobs[job_id]["status"] = "error"
            jobs[job_id]["progress"] = 0
            jobs[job_id]["error"] = str(e)

        # Delete failed output
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
        except Exception:
            pass

    finally:

        # Delete input file
        try:
            if os.path.exists(input_file):
                os.remove(input_file)
        except Exception:
            pass


# =========================================================
# START CONVERSION
# =========================================================

@app.route("/convert", methods=["POST"])
def convert():

    if not FFMPEG:

        return jsonify({
            "error": (
                "FFmpeg is not installed. "
                "Please add imageio-ffmpeg to requirements.txt."
            )
        }), 500

    # -------------------------
    # CHECK FILE
    # -------------------------

    if "file" not in request.files:

        return jsonify({
            "error": "No file uploaded."
        }), 400

    file = request.files["file"]

    if not file or file.filename == "":

        return jsonify({
            "error": "No file selected."
        }), 400

    # -------------------------
    # GET FORMAT
    # -------------------------

    output_format = (
        request.form.get("format", "mp3")
        .lower()
        .strip()
        .replace(".", "")
    )

    if output_format not in SUPPORTED_FORMATS:

        return jsonify({
            "error": (
                f"Unsupported format: {output_format}"
            )
        }), 400

    # -------------------------
    # CREATE JOB
    # -------------------------

    job_id = str(uuid.uuid4())

    safe_name = secure_filename(
        file.filename
    )

    if not safe_name:
        safe_name = "input_media"

    job_dir = os.path.join(
        TEMP_DIR,
        job_id
    )

    os.makedirs(
        job_dir,
        exist_ok=True
    )

    input_file = os.path.join(
        job_dir,
        "input" + os.path.splitext(safe_name)[1]
    )

    output_file = os.path.join(
        job_dir,
        "output." + output_format
    )

    # -------------------------
    # SAVE UPLOAD
    # -------------------------

    try:

        file.save(input_file)

    except Exception as e:

        shutil.rmtree(
            job_dir,
            ignore_errors=True
        )

        return jsonify({
            "error": (
                f"Unable to save uploaded file: {e}"
            )
        }), 500

    # -------------------------
    # INITIAL JOB DATA
    # -------------------------

    with jobs_lock:

        jobs[job_id] = {
            "status": "starting",
            "progress": 0,
            "filename": None,
            "output_file": None,
            "error": None,
            "created": time.time(),
            "duration": 0
        }

    # -------------------------
    # START BACKGROUND JOB
    # -------------------------

    thread = threading.Thread(
        target=conversion_worker,
        args=(
            job_id,
            input_file,
            output_file,
            output_format,
            safe_name
        ),
        daemon=True
    )

    thread.start()

    # IMPORTANT:
    # Frontend expects job_id
    return jsonify({
        "job_id": job_id
    }), 200


# =========================================================
# PROGRESS
# =========================================================

@app.route("/progress", methods=["GET"])
def progress():

    job_id = request.args.get("id", "").strip()

    if not job_id:

        return jsonify({
            "status": "error",
            "progress": 0,
            "error": "Missing job id."
        }), 400

    with jobs_lock:

        job = jobs.get(job_id)

        if not job:

            return jsonify({
                "status": "error",
                "progress": 0,
                "error": "Job not found."
            }), 404

        response = {
            "status": job.get("status", "starting"),
            "progress": job.get("progress", 0)
        }

        if job.get("status") == "error":
            response["error"] = job.get(
                "error",
                "Conversion failed."
            )

        if job.get("status") == "completed":
            response["filename"] = job.get(
                "filename"
            )

        return jsonify(response), 200


# =========================================================
# DOWNLOAD
# =========================================================

@app.route("/download", methods=["GET"])
def download():

    job_id = request.args.get("id", "").strip()

    if not job_id:

        return jsonify({
            "error": "Missing job id."
        }), 400

    with jobs_lock:

        job = jobs.get(job_id)

        if not job:

            return jsonify({
                "error": "Job not found."
            }), 404

        if job.get("status") != "completed":

            return jsonify({
                "error": "Conversion is not completed yet."
            }), 400

        output_file = job.get(
            "output_file"
        )

        download_name = job.get(
            "filename",
            "converted_file"
        )

    if not output_file:

        return jsonify({
            "error": "Output file path is missing."
        }), 404

    if not os.path.exists(output_file):

        return jsonify({
            "error": "Output file not found."
        }), 404

    return send_file(
        output_file,
        as_attachment=True,
        download_name=download_name
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

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


# =========================================================
# CLEAN OLD JOBS
# =========================================================

def cleanup_old_jobs():

    while True:

        time.sleep(1800)  # 30 minutes

        current_time = time.time()

        old_jobs = []

        with jobs_lock:

            for job_id, job in list(jobs.items()):

                created = job.get(
                    "created",
                    current_time
                )

                if (
                    current_time - created
                    > 3600
                ):
                    old_jobs.append(job_id)

        for job_id in old_jobs:

            job_dir = os.path.join(
                TEMP_DIR,
                job_id
            )

            shutil.rmtree(
                job_dir,
                ignore_errors=True
            )

            with jobs_lock:
                jobs.pop(
                    job_id,
                    None
                )


cleanup_thread = threading.Thread(
    target=cleanup_old_jobs,
    daemon=True
)

cleanup_thread.start()


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            8000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
