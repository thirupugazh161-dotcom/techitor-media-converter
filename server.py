import os
import re
import uuid
import time
import shutil
import threading
import subprocess

from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename

import imageio_ffmpeg


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


# =========================================================
# DIRECTORIES
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

TEMP_DIR = os.path.join(
    BASE_DIR,
    "temp"
)

os.makedirs(
    TEMP_DIR,
    exist_ok=True
)


# =========================================================
# FFMPEG
# =========================================================

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


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
    "webm"
}


# =========================================================
# HEALTH
# =========================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "ffmpeg": bool(FFMPEG)
    }), 200


# =========================================================
# HOME
# =========================================================

@app.route("/", methods=["GET"])
def home():

    index_file = os.path.join(
        BASE_DIR,
        "index.html"
    )

    if not os.path.exists(index_file):

        return jsonify({
            "error": "index.html not found"
        }), 404

    return send_file(index_file)


# =========================================================
# DURATION
# =========================================================

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
            text=True
        )

        match = re.search(
            r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
            result.stderr
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
# FFMPEG COMMAND
# =========================================================

def build_command(
    input_file,
    output_file,
    output_format
):

    # -----------------------------------------------
    # MP3
    # -----------------------------------------------

    if output_format == "mp3":

        return [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-i",
            input_file,

            "-vn",

            "-c:a",
            "libmp3lame",

            "-b:a",
            "192k",

            "-progress",
            "pipe:1",

            "-nostats",

            output_file
        ]


    # -----------------------------------------------
    # WAV
    # -----------------------------------------------

    if output_format == "wav":

        return [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-i",
            input_file,

            "-vn",

            "-c:a",
            "pcm_s16le",

            "-progress",
            "pipe:1",

            "-nostats",

            output_file
        ]


    # -----------------------------------------------
    # M4A
    # -----------------------------------------------

    if output_format == "m4a":

        return [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-i",
            input_file,

            "-vn",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            "-progress",
            "pipe:1",

            "-nostats",

            output_file
        ]


    # -----------------------------------------------
    # MP4
    # -----------------------------------------------

    if output_format == "mp4":

        return [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-i",
            input_file,

            "-c:v",
            "libx264",

            "-preset",
            "veryfast",

            "-crf",
            "23",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            "-movflags",
            "+faststart",

            "-progress",
            "pipe:1",

            "-nostats",

            output_file
        ]


    # -----------------------------------------------
    # MOV
    # -----------------------------------------------

    if output_format == "mov":

        return [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-i",
            input_file,

            "-c:v",
            "libx264",

            "-preset",
            "veryfast",

            "-crf",
            "23",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            "-progress",
            "pipe:1",

            "-nostats",

            output_file
        ]


    # -----------------------------------------------
    # MKV
    # -----------------------------------------------

    if output_format == "mkv":

        return [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-i",
            input_file,

            "-c:v",
            "libx264",

            "-preset",
            "veryfast",

            "-crf",
            "23",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            "-progress",
            "pipe:1",

            "-nostats",

            output_file
        ]


    # -----------------------------------------------
    # WEBM
    # -----------------------------------------------

    if output_format == "webm":

        return [
            FFMPEG,
            "-y",
            "-hide_banner",
            "-i",
            input_file,

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

            "-progress",
            "pipe:1",

            "-nostats",

            output_file
        ]


    raise ValueError(
        f"Unsupported format: {output_format}"
    )


# =========================================================
# CONVERSION WORKER
# =========================================================

def run_conversion(
    job_id,
    input_file,
    output_file,
    output_format,
    original_filename
):

    stderr_lines = []

    try:

        with jobs_lock:

            jobs[job_id].update({
                "status": "converting",
                "progress": 0,
                "message": "Starting conversion..."
            })


        # ---------------------------------------------
        # CHECK INPUT
        # ---------------------------------------------

        if not os.path.exists(input_file):

            raise RuntimeError(
                "Uploaded input file was not found."
            )


        # ---------------------------------------------
        # GET DURATION
        # ---------------------------------------------

        duration = get_duration(
            input_file
        )

        with jobs_lock:

            jobs[job_id]["duration"] = duration


        # ---------------------------------------------
        # BUILD COMMAND
        # ---------------------------------------------

        command = build_command(
            input_file,
            output_file,
            output_format
        )


        # ---------------------------------------------
        # START FFMPEG
        # ---------------------------------------------

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )


        # ---------------------------------------------
        # READ STDERR IN SEPARATE THREAD
        # ---------------------------------------------

        def read_errors():

            for line in process.stderr:

                line = line.strip()

                if line:

                    stderr_lines.append(
                        line
                    )


        error_thread = threading.Thread(
            target=read_errors,
            daemon=True
        )

        error_thread.start()


        # ---------------------------------------------
        # READ PROGRESS
        # ---------------------------------------------

        for line in process.stdout:

            line = line.strip()

            if not line:
                continue


            if line.startswith(
                "out_time_ms="
            ):

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

                        progress = round(
                            progress,
                            1
                        )

                        with jobs_lock:

                            jobs[job_id][
                                "progress"
                            ] = progress

                            jobs[job_id][
                                "message"
                            ] = (
                                f"Converting... "
                                f"{progress}%"
                            )

                except Exception:

                    pass


        # ---------------------------------------------
        # WAIT
        # ---------------------------------------------

        return_code = process.wait()

        error_thread.join(
            timeout=2
        )


        # ---------------------------------------------
        # FAILED
        # ---------------------------------------------

        if return_code != 0:

            error_text = "\n".join(
                stderr_lines
            )

            if not error_text:

                error_text = (
                    "FFmpeg conversion failed."
                )

            raise RuntimeError(
                error_text[-4000:]
            )


        # ---------------------------------------------
        # CHECK OUTPUT
        # ---------------------------------------------

        if not os.path.exists(
            output_file
        ):

            raise RuntimeError(
                "FFmpeg finished but output file "
                "was not created."
            )


        output_size = os.path.getsize(
            output_file
        )


        if output_size <= 0:

            raise RuntimeError(
                "FFmpeg created an empty output file."
            )


        # ---------------------------------------------
        # DOWNLOAD NAME
        # ---------------------------------------------

        base_name = os.path.splitext(
            secure_filename(
                original_filename
            )
        )[0]

        if not base_name:

            base_name = "converted_file"

        download_name = (
            base_name
            + "."
            + output_format
        )


        # ---------------------------------------------
        # SUCCESS
        # ---------------------------------------------

        with jobs_lock:

            jobs[job_id].update({

                "status": "completed",

                "progress": 100,

                "message":
                    "Conversion completed successfully!",

                "filename":
                    download_name,

                "output_file":
                    output_file
            })


    except Exception as error:

        error_message = str(error)

        print(
            f"[JOB {job_id}] ERROR:"
        )

        print(
            error_message
        )

        with jobs_lock:

            jobs[job_id].update({

                "status": "error",

                "progress": 0,

                "message":
                    "Conversion failed.",

                "error":
                    error_message
            })


        # Delete failed output

        try:

            if os.path.exists(
                output_file
            ):

                os.remove(
                    output_file
                )

        except Exception:

            pass


    finally:

        # ---------------------------------------------
        # DELETE INPUT
        # ---------------------------------------------

        try:

            if os.path.exists(
                input_file
            ):

                os.remove(
                    input_file
                )

        except Exception:

            pass


# =========================================================
# CONVERT
# =========================================================

@app.route(
    "/convert",
    methods=["POST"]
)
def convert():

    # ---------------------------------------------
    # FFMPEG CHECK
    # ---------------------------------------------

    if not FFMPEG:

        return jsonify({
            "error":
                "FFmpeg is not available."
        }), 500


    # ---------------------------------------------
    # FILE CHECK
    # ---------------------------------------------

    if "file" not in request.files:

        return jsonify({
            "error":
                "No file uploaded."
        }), 400


    file = request.files["file"]


    if not file or not file.filename:

        return jsonify({
            "error":
                "No file selected."
        }), 400


    # ---------------------------------------------
    # FORMAT
    # ---------------------------------------------

    output_format = (
        request.form
        .get(
            "format",
            "mp3"
        )
        .lower()
        .strip()
        .replace(
            ".",
            ""
        )
    )


    if output_format not in SUPPORTED_FORMATS:

        return jsonify({
            "error":
                "Unsupported format."
        }), 400


    # ---------------------------------------------
    # JOB ID
    # ---------------------------------------------

    job_id = uuid.uuid4().hex


    # ---------------------------------------------
    # JOB DIRECTORY
    # ---------------------------------------------

    job_dir = os.path.join(
        TEMP_DIR,
        job_id
    )

    os.makedirs(
        job_dir,
        exist_ok=True
    )


    # ---------------------------------------------
    # SAFE ORIGINAL NAME
    # ---------------------------------------------

    original_filename = secure_filename(
        file.filename
    )

    if not original_filename:

        original_filename = (
            "uploaded_media"
        )


    extension = os.path.splitext(
        original_filename
    )[1]


    # ---------------------------------------------
    # INPUT / OUTPUT PATHS
    # ---------------------------------------------

    input_file = os.path.join(
        job_dir,
        "input" + extension
    )

    output_file = os.path.join(
        job_dir,
        "output." + output_format
    )


    # ---------------------------------------------
    # SAVE FILE
    # ---------------------------------------------

    try:

        file.save(
            input_file
        )

    except Exception as error:

        shutil.rmtree(
            job_dir,
            ignore_errors=True
        )

        return jsonify({
            "error":
                f"Upload failed: {error}"
        }), 500


    # ---------------------------------------------
    # VERIFY INPUT
    # ---------------------------------------------

    if not os.path.exists(
        input_file
    ):

        shutil.rmtree(
            job_dir,
            ignore_errors=True
        )

        return jsonify({
            "error":
                "Uploaded file could not be saved."
        }), 500


    # ---------------------------------------------
    # CREATE JOB
    # ---------------------------------------------

    with jobs_lock:

        jobs[job_id] = {

            "status":
                "starting",

            "progress":
                0,

            "message":
                "Preparing conversion...",

            "filename":
                None,

            "output_file":
                None,

            "error":
                None,

            "created":
                time.time(),

            "duration":
                0
        }


    # ---------------------------------------------
    # START THREAD
    # ---------------------------------------------

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

        "job_id":
            job_id,

        "status":
            "starting"

    }), 200


# =========================================================
# PROGRESS
# =========================================================

@app.route(
    "/progress",
    methods=["GET"]
)
def progress():

    job_id = request.args.get(
        "id",
        ""
    ).strip()


    if not job_id:

        return jsonify({

            "status":
                "error",

            "progress":
                0,

            "error":
                "Missing job ID."

        }), 400


    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            return jsonify({

                "status":
                    "error",

                "progress":
                    0,

                "error":
                    "Job not found."

            }), 404


        response = {

            "status":
                job.get(
                    "status",
                    "starting"
                ),

            "progress":
                job.get(
                    "progress",
                    0
                ),

            "message":
                job.get(
                    "message",
                    ""
                )
        }


        if job.get(
            "status"
        ) == "completed":

            response["filename"] = (
                job.get(
                    "filename"
                )
            )


        if job.get(
            "status"
        ) == "error":

            response["error"] = (
                job.get(
                    "error",
                    "Conversion failed."
                )
            )


        return jsonify(
            response
        ), 200


# =========================================================
# DOWNLOAD
# =========================================================

@app.route(
    "/download",
    methods=["GET"]
)
def download():

    job_id = request.args.get(
        "id",
        ""
    ).strip()


    if not job_id:

        return jsonify({
            "error":
                "Missing job ID."
        }), 400


    with jobs_lock:

        job = jobs.get(
            job_id
        )


        if not job:

            return jsonify({
                "error":
                    "Job not found."
            }), 404


        if job.get(
            "status"
        ) != "completed":

            return jsonify({
                "error":
                    "Conversion not completed."
            }), 400


        output_file = job.get(
            "output_file"
        )

        filename = job.get(
            "filename",
            "converted_file"
        )


    # ---------------------------------------------
    # OUTPUT CHECK
    # ---------------------------------------------

    if not output_file:

        return jsonify({
            "error":
                "Output file path is missing."
        }), 404


    if not os.path.exists(
        output_file
    ):

        return jsonify({
            "error":
                "Output file not found."
        }), 404


    # ---------------------------------------------
    # SEND FILE
    # ---------------------------------------------

    return send_file(

        output_file,

        as_attachment=True,

        download_name=filename

    )


# =========================================================
# FILE TOO LARGE
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({

        "error":
            "File too large. Maximum size is 500 MB."

    }), 413


# =========================================================
# GENERAL ERROR
# =========================================================

@app.errorhandler(500)
def internal_error(error):

    return jsonify({

        "error":
            "Internal server error."

    }), 500


# =========================================================
# CLEANUP
# =========================================================

def cleanup_old_jobs():

    while True:

        time.sleep(
            1800
        )

        cutoff = (
            time.time()
            - 3600
        )

        old_job_ids = []


        with jobs_lock:

            for job_id, job in jobs.items():

                if job.get(
                    "created",
                    time.time()
                ) < cutoff:

                    old_job_ids.append(
                        job_id
                    )


        for job_id in old_job_ids:

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
            10000
        )
    )

    app.run(

        host="0.0.0.0",

        port=port,

        debug=False,

        threaded=True

    )
