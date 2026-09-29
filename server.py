import os
import re
import uuid
import threading
import subprocess
import json
import shutil
import time

from flask import Flask, request, jsonify, send_file
import imageio_ffmpeg


# ============================================================
# APP SETUP
# ============================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# In-memory cache + file-backed job state
jobs = {}
jobs_lock = threading.Lock()


# ============================================================
# SUPPORTED FORMATS
# ============================================================

ALLOWED_FORMATS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm"
}


# ============================================================
# JOB HELPERS
# ============================================================

def job_directory(job_id):
    path = os.path.join(TEMP_DIR, job_id)
    os.makedirs(path, exist_ok=True)
    return path


def job_state_file(job_id):
    return os.path.join(
        job_directory(job_id),
        "job.json"
    )


def save_job(job_id, data):
    """
    Save job status both in memory and on disk.
    This makes progress work more reliably with Render/Gunicorn.
    """

    with jobs_lock:
        jobs[job_id] = dict(data)

    try:
        path = job_state_file(job_id)

        temp_path = path + ".tmp"

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        os.replace(temp_path, path)

    except Exception:
        pass


def load_job(job_id):
    """
    Load job from memory first, then disk.
    """

    with jobs_lock:
        if job_id in jobs:
            return dict(jobs[job_id])

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


# ============================================================
# MEDIA DURATION
# ============================================================

def get_duration(input_file):

    try:

        result = subprocess.run(
            [
                FFMPEG,
                "-hide_banner",
                "-i",
                input_file
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        match = re.search(
            r"Duration:\s*(\d+):(\d+):([\d.]+)",
            result.stderr
        )

        if match:

            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))

            return (
                hours * 3600
                + minutes * 60
                + seconds
            )

    except Exception:
        pass

    return 0


# ============================================================
# CHECK MEDIA STREAMS
# ============================================================

def has_audio(input_file):

    try:

        result = subprocess.run(
            [
                FFMPEG,
                "-hide_banner",
                "-i",
                input_file
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        return bool(
            re.search(
                r"Stream .*Audio:",
                result.stderr,
                re.IGNORECASE
            )
        )

    except Exception:
        return False


def has_video(input_file):

    try:

        result = subprocess.run(
            [
                FFMPEG,
                "-hide_banner",
                "-i",
                input_file
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        return bool(
            re.search(
                r"Stream .*Video:",
                result.stderr,
                re.IGNORECASE
            )
        )

    except Exception:
        return False


# ============================================================
# BUILD FFMPEG COMMAND
# ============================================================

def build_command(
    input_file,
    output_file,
    output_format
):

    command = [
        FFMPEG,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_file
    ]


    # ========================================================
    # MP3
    # ========================================================

    if output_format == "mp3":

        command += [
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            output_file
        ]


    # ========================================================
    # WAV
    # ========================================================

    elif output_format == "wav":

        command += [
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "44100",
            output_file
        ]


    # ========================================================
    # M4A
    # ========================================================

    elif output_format == "m4a":

        command += [
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "44100",
            "-movflags",
            "+faststart",
            output_file
        ]


    # ========================================================
    # MP4
    # ========================================================

    elif output_format == "mp4":

        command += [
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            output_file
        ]


    # ========================================================
    # MOV
    # ========================================================

    elif output_format == "mov":

        # Use MPEG-4 Part 2 instead of relying on libx264.
        # This is more compatible with restricted FFmpeg builds.

        command += [
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "mpeg4",
            "-q:v",
            "3",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            output_file
        ]


    # ========================================================
    # MKV
    # ========================================================

    elif output_format == "mkv":

        command += [
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            output_file
        ]


    # ========================================================
    # WEBM
    # ========================================================

    elif output_format == "webm":

        command += [
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "30",
            "-b:v",
            "0",
            "-c:a",
            "libopus",
            "-b:a",
            "128k",
            output_file
        ]


    else:

        raise ValueError(
            f"Unsupported output format: {output_format}"
        )


    return command


# ============================================================
# RUN CONVERSION
# ============================================================

def run_conversion(
    job_id,
    input_file,
    output_file,
    output_format,
    original_filename
):

    try:

        save_job(
            job_id,
            {
                "status": "converting",
                "progress": 0,
                "message": "Preparing conversion...",
                "filename": (
                    os.path.splitext(original_filename)[0]
                    + "."
                    + output_format
                )
            }
        )


        # ----------------------------------------------------
        # Validate input
        # ----------------------------------------------------

        if not os.path.exists(input_file):

            raise RuntimeError(
                "Uploaded input file was not found."
            )


        input_size = os.path.getsize(input_file)

        if input_size == 0:

            raise RuntimeError(
                "Uploaded file is empty."
            )


        # ----------------------------------------------------
        # Check required streams
        # ----------------------------------------------------

        audio_formats = {
            "mp3",
            "wav",
            "m4a"
        }

        video_formats = {
            "mp4",
            "mov",
            "mkv",
            "webm"
        }


        if output_format in audio_formats:

            if not has_audio(input_file):

                raise RuntimeError(
                    "This video/file does not contain an audio stream."
                )


        if output_format in video_formats:

            if not has_video(input_file):

                raise RuntimeError(
                    "This file does not contain a video stream."
                )


        # ----------------------------------------------------
        # Duration
        # ----------------------------------------------------

        duration = get_duration(input_file)


        # ----------------------------------------------------
        # Build command
        # ----------------------------------------------------

        command = build_command(
            input_file,
            output_file,
            output_format
        )


        save_job(
            job_id,
            {
                "status": "converting",
                "progress": 1,
                "message": "FFmpeg conversion started...",
                "filename": (
                    os.path.splitext(original_filename)[0]
                    + "."
                    + output_format
                )
            }
        )


        # ----------------------------------------------------
        # Start FFmpeg
        # ----------------------------------------------------

        command_with_progress = command[:-1] + [
            "-progress",
            "pipe:1",
            "-nostats",
            command[-1]
        ]


        process = subprocess.Popen(
            command_with_progress,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1
        )


        stderr_lines = []


        # ----------------------------------------------------
        # STDERR READER
        # ----------------------------------------------------

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
            daemon=True
        )

        stderr_thread.start()


        # ----------------------------------------------------
        # READ PROGRESS
        # ----------------------------------------------------

        for line in process.stdout:

            line = line.strip()

            if line.startswith("out_time_ms="):

                try:

                    value = line.split(
                        "=",
                        1
                    )[1]

                    current_time = (
                        int(value)
                        / 1_000_000
                    )


                    if duration > 0:

                        progress = (
                            current_time
                            / duration
                        ) * 100

                        progress = max(
                            0,
                            min(
                                99,
                                progress
                            )
                        )


                        save_job(
                            job_id,
                            {
                                "status": "converting",
                                "progress": round(
                                    progress,
                                    1
                                ),
                                "message": (
                                    "Converting... "
                                    + str(
                                        round(
                                            progress,
                                            1
                                        )
                                    )
                                    + "%"
                                ),
                                "filename": (
                                    os.path.splitext(
                                        original_filename
                                    )[0]
                                    + "."
                                    + output_format
                                )
                            }
                        )

                except Exception:
                    pass


        process.wait()

        stderr_thread.join(
            timeout=3
        )


        # ----------------------------------------------------
        # FFmpeg FAILED
        # ----------------------------------------------------

        if process.returncode != 0:

            error_text = "\n".join(
                stderr_lines
            )

            if not error_text:

                error_text = (
                    "FFmpeg exited with code "
                    + str(
                        process.returncode
                    )
                )


            save_job(
                job_id,
                {
                    "status": "error",
                    "progress": 0,
                    "message": "Conversion failed.",
                    "error": error_text[-5000:],
                    "filename": (
                        os.path.splitext(
                            original_filename
                        )[0]
                        + "."
                        + output_format
                    )
                }
            )

            return


        # ----------------------------------------------------
        # OUTPUT VALIDATION
        # ----------------------------------------------------

        if not os.path.exists(output_file):

            raise RuntimeError(
                "FFmpeg completed, but output file was not created."
            )


        output_size = os.path.getsize(
            output_file
        )


        if output_size == 0:

            raise RuntimeError(
                "FFmpeg created an empty output file."
            )


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        final_filename = (
            os.path.splitext(
                original_filename
            )[0]
            + "."
            + output_format
        )


        save_job(
            job_id,
            {
                "status": "completed",
                "progress": 100,
                "message": (
                    "Conversion completed successfully!"
                ),
                "filename": final_filename,
                "download_url": (
                    "/download?id="
                    + job_id
                )
            }
        )


    except Exception as e:

        save_job(
            job_id,
            {
                "status": "error",
                "progress": 0,
                "message": "Conversion failed.",
                "error": str(e),
                "filename": (
                    os.path.splitext(
                        original_filename
                    )[0]
                    + "."
                    + output_format
                )
            }
        )


    finally:

        # Keep output file.
        # Remove input file only.

        try:

            if os.path.exists(input_file):
                os.remove(input_file)

        except Exception:
            pass


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return send_file(
        os.path.join(
            BASE_DIR,
            "index.html"
        )
    )


# ============================================================
# START CONVERSION
# ============================================================

@app.route(
    "/convert",
    methods=["POST"]
)
def convert():

    if "file" not in request.files:

        return jsonify({
            "error": "No file uploaded."
        }), 400


    file = request.files["file"]


    if not file or file.filename == "":

        return jsonify({
            "error": "No file selected."
        }), 400


    output_format = (
        request.form.get(
            "format",
            "mp3"
        )
        .strip()
        .lower()
    )


    if output_format not in ALLOWED_FORMATS:

        return jsonify({
            "error": (
                "Unsupported format: "
                + output_format
            )
        }), 400


    job_id = uuid.uuid4().hex

    folder = job_directory(
        job_id
    )


    # --------------------------------------------------------
    # Preserve original extension internally.
    # --------------------------------------------------------

    original_filename = (
        os.path.basename(
            file.filename
        )
    )


    input_extension = (
        os.path.splitext(
            original_filename
        )[1]
        .lower()
    )


    if not input_extension:
        input_extension = ".bin"


    input_file = os.path.join(
        folder,
        "input" + input_extension
    )


    output_file = os.path.join(
        folder,
        "output." + output_format
    )


    # --------------------------------------------------------
    # Save uploaded file
    # --------------------------------------------------------

    try:

        file.save(
            input_file
        )

    except Exception as e:

        shutil.rmtree(
            folder,
            ignore_errors=True
        )

        return jsonify({
            "error": (
                "Upload failed: "
                + str(e)
            )
        }), 500


    # --------------------------------------------------------
    # Initial job state
    # --------------------------------------------------------

    final_filename = (
        os.path.splitext(
            original_filename
        )[0]
        + "."
        + output_format
    )


    save_job(
        job_id,
        {
            "status": "starting",
            "progress": 0,
            "message": "Preparing conversion...",
            "filename": final_filename
        }
    )


    # --------------------------------------------------------
    # Background conversion
    # --------------------------------------------------------

    thread = threading.Thread(
        target=run_conversion,
        args=(
            job_id,
            input_file,
            output_file,
            output_format,
            original_filename
        ),
        daemon=True
    )


    thread.start()


    return jsonify({
        "job_id": job_id,
        "status": "starting"
    })


# ============================================================
# PROGRESS
# ============================================================

@app.route("/progress")
def progress():

    job_id = request.args.get(
        "id",
        ""
    ).strip()


    if not job_id:

        return jsonify({
            "status": "error",
            "error": "Missing job ID."
        }), 400


    job = load_job(
        job_id
    )


    if not job:

        return jsonify({
            "status": "error",
            "error": "Job not found."
        }), 404


    return jsonify(job)


# ============================================================
# DOWNLOAD
# ============================================================

@app.route("/download")
def download():

    job_id = request.args.get(
        "id",
        ""
    ).strip()


    if not job_id:

        return jsonify({
            "error": "Missing job ID."
        }), 400


    job = load_job(
        job_id
    )


    if not job:

        return jsonify({
            "error": "Job not found."
        }), 404


    if job.get("status") != "completed":

        return jsonify({
            "error": "Conversion not completed."
        }), 400


    folder = job_directory(
        job_id
    )


    filename = job.get(
        "filename"
    )


    if not filename:

        return jsonify({
            "error": "Output filename missing."
        }), 404


    output_file = os.path.join(
        folder,
        "output."
        + os.path.splitext(
            filename
        )[1].lstrip(".")
    )


    if not os.path.exists(
        output_file
    ):

        return jsonify({
            "error": "Output file not found."
        }), 404


    return send_file(
        output_file,
        as_attachment=True,
        download_name=filename
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "ffmpeg": FFMPEG
    })


# ============================================================
# SERVER
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )


    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )
