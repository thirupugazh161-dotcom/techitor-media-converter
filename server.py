import os
import re
import uuid
import threading
import subprocess
from flask import Flask, request, jsonify, send_file

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

jobs = {}
jobs_lock = threading.Lock()


# =========================================================
# FFMPEG
# =========================================================

def get_ffmpeg():
    """
    Get FFmpeg executable.
    imageio-ffmpeg provides a portable FFmpeg binary.
    """

    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

    # Fallback: system FFmpeg
    return "ffmpeg"


FFMPEG = get_ffmpeg()


# =========================================================
# FORMAT SETTINGS
# =========================================================

ALLOWED_FORMATS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm"
}


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    index_path = os.path.join(BASE_DIR, "index.html")

    if not os.path.exists(index_path):
        return "Techi­tor Media Converter Server Running"

    return send_file(index_path)


# =========================================================
# GET VIDEO/AUDIO DURATION
# =========================================================

def get_duration(input_file):

    try:

        command = [
            FFMPEG,
            "-i",
            input_file
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        output = result.stderr

        match = re.search(
            r"Duration:\s*(\d+):(\d+):([\d.]+)",
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
# UPDATE JOB
# =========================================================

def update_job(job_id, **kwargs):

    with jobs_lock:

        if job_id in jobs:
            jobs[job_id].update(kwargs)


# =========================================================
# CONVERSION COMMAND
# =========================================================

def build_ffmpeg_command(
    input_file,
    output_file,
    output_format
):

    # -----------------------------------------------------
    # MP3
    # -----------------------------------------------------

    if output_format == "mp3":

        return [
            FFMPEG,
            "-y",
            "-i",
            input_file,

            "-vn",

            "-codec:a",
            "libmp3lame",

            "-b:a",
            "192k",

            output_file
        ]


    # -----------------------------------------------------
    # WAV
    # -----------------------------------------------------

    if output_format == "wav":

        return [
            FFMPEG,
            "-y",
            "-i",
            input_file,

            "-vn",

            "-c:a",
            "pcm_s16le",

            output_file
        ]


    # -----------------------------------------------------
    # M4A
    # -----------------------------------------------------

    if output_format == "m4a":

        return [
            FFMPEG,
            "-y",
            "-i",
            input_file,

            "-vn",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            "-movflags",
            "+faststart",

            output_file
        ]


    # -----------------------------------------------------
    # MP4
    # -----------------------------------------------------

    if output_format == "mp4":

        return [
            FFMPEG,
            "-y",
            "-i",
            input_file,

            "-c:v",
            "libx264",

            "-preset",
            "medium",

            "-crf",
            "23",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            "-movflags",
            "+faststart",

            output_file
        ]


    # -----------------------------------------------------
    # MOV
    # -----------------------------------------------------

    if output_format == "mov":

        return [
            FFMPEG,
            "-y",
            "-i",
            input_file,

            "-c:v",
            "libx264",

            "-preset",
            "medium",

            "-crf",
            "23",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            output_file
        ]


    # -----------------------------------------------------
    # MKV
    # -----------------------------------------------------

    if output_format == "mkv":

        return [
            FFMPEG,
            "-y",
            "-i",
            input_file,

            "-c:v",
            "libx264",

            "-preset",
            "medium",

            "-crf",
            "23",

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            output_file
        ]


    # -----------------------------------------------------
    # WEBM
    # -----------------------------------------------------

    if output_format == "webm":

        return [
            FFMPEG,
            "-y",
            "-i",
            input_file,

            "-c:v",
            "libvpx-vp9",

            "-crf",
            "32",

            "-b:v",
            "0",

            "-c:a",
            "libopus",

            "-b:a",
            "128k",

            output_file
        ]


    raise ValueError(
        "Unsupported output format: "
        + output_format
    )


# =========================================================
# CONVERSION WORKER
# =========================================================

def convert_worker(
    job_id,
    input_file,
    output_file,
    output_format
):

    try:

        # -------------------------------------------------
        # Check input file
        # -------------------------------------------------

        if not os.path.exists(input_file):

            raise FileNotFoundError(
                "Uploaded input file was not found."
            )


        # -------------------------------------------------
        # Starting
        # -------------------------------------------------

        update_job(
            job_id,

            status="starting",

            progress=5,

            error=None
        )


        # -------------------------------------------------
        # Get duration
        # -------------------------------------------------

        duration = get_duration(input_file)


        # -------------------------------------------------
        # Build FFmpeg command
        # -------------------------------------------------

        command = build_ffmpeg_command(
            input_file,
            output_file,
            output_format
        )


        # Add progress output

        command.insert(1, "-progress")
        command.insert(2, "pipe:1")

        command.insert(3, "-nostats")


        # -------------------------------------------------
        # Start FFmpeg
        # -------------------------------------------------

        update_job(
            job_id,

            status="converting",

            progress=10
        )


        process = subprocess.Popen(
            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            bufsize=1
        )


        # -------------------------------------------------
        # Read FFmpeg progress
        # -------------------------------------------------

        while True:

            line = process.stdout.readline()

            if not line:

                if process.poll() is not None:
                    break

                continue


            line = line.strip()


            # FFmpeg gives:
            # out_time_ms=1234567

            if line.startswith("out_time_ms="):

                try:

                    time_ms = int(
                        line.split(
                            "=",
                            1
                        )[1]
                    )

                    current_seconds = (
                        time_ms / 1_000_000
                    )


                    if duration > 0:

                        percentage = (
                            current_seconds
                            / duration
                        ) * 100

                        percentage = max(
                            10,
                            min(
                                99,
                                percentage
                            )
                        )

                        update_job(
                            job_id,

                            progress=round(
                                percentage,
                                1
                            )
                        )

                except Exception:
                    pass


        # -------------------------------------------------
        # Wait for FFmpeg
        # -------------------------------------------------

        stderr_output = process.stderr.read()

        return_code = process.wait()


        # -------------------------------------------------
        # Conversion failed
        # -------------------------------------------------

        if return_code != 0:

            error_message = (
                stderr_output.strip()
                if stderr_output.strip()
                else "FFmpeg conversion failed."
            )

            raise RuntimeError(
                error_message[-2000:]
            )


        # -------------------------------------------------
        # Check output file
        # -------------------------------------------------

        if not os.path.exists(output_file):

            raise FileNotFoundError(
                "FFmpeg completed but output file "
                "was not created."
            )


        if os.path.getsize(output_file) == 0:

            raise RuntimeError(
                "Output file was created but is empty."
            )


        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        original_name = jobs[job_id].get(
            "original_name",
            "converted"
        )

        base_name = os.path.splitext(
            original_name
        )[0]

        download_name = (
            base_name
            + "."
            + output_format
        )


        update_job(

            job_id,

            status="completed",

            progress=100,

            filename=download_name,

            output_file=output_file,

            error=None
        )


    except Exception as e:

        update_job(

            job_id,

            status="error",

            progress=0,

            error=str(e)
        )


    finally:

        # -------------------------------------------------
        # Remove input file
        # -------------------------------------------------

        try:

            if os.path.exists(input_file):
                os.remove(input_file)

        except Exception:
            pass


# =========================================================
# START CONVERSION
# =========================================================

@app.route(
    "/convert",
    methods=["POST"]
)
def convert():

    try:

        # -------------------------------------------------
        # Check uploaded file
        # -------------------------------------------------

        if "file" not in request.files:

            return jsonify({
                "error": "No file uploaded."
            }), 400


        uploaded_file = request.files["file"]


        if not uploaded_file:

            return jsonify({
                "error": "Invalid uploaded file."
            }), 400


        if uploaded_file.filename == "":

            return jsonify({
                "error": "No file selected."
            }), 400


        # -------------------------------------------------
        # Get requested format
        # -------------------------------------------------

        output_format = (
            request.form.get(
                "format",
                ""
            )
            .lower()
            .strip()
        )


        if output_format not in ALLOWED_FORMATS:

            return jsonify({
                "error":
                "Unsupported output format: "
                + output_format
            }), 400


        # -------------------------------------------------
        # Create unique job
        # -------------------------------------------------

        job_id = str(
            uuid.uuid4()
        )


        # -------------------------------------------------
        # Preserve original filename
        # -------------------------------------------------

        original_name = os.path.basename(
            uploaded_file.filename
        )


        # -------------------------------------------------
        # File extension
        # -------------------------------------------------

        original_ext = os.path.splitext(
            original_name
        )[1]


        if not original_ext:

            original_ext = ".bin"


        # -------------------------------------------------
        # Unique input path
        # -------------------------------------------------

        input_file = os.path.join(
            TEMP_DIR,
            job_id
            + "_input"
            + original_ext
        )


        # -------------------------------------------------
        # Output path
        # -------------------------------------------------

        output_file = os.path.join(
            TEMP_DIR,
            job_id
            + "_output."
            + output_format
        )


        # -------------------------------------------------
        # SAVE UPLOAD
        # -------------------------------------------------

        uploaded_file.save(
            input_file
        )


        # -------------------------------------------------
        # IMPORTANT FILE CHECK
        # -------------------------------------------------

        if not os.path.exists(
            input_file
        ):

            return jsonify({
                "error":
                "Uploaded file could not be saved."
            }), 500


        if os.path.getsize(
            input_file
        ) == 0:

            return jsonify({
                "error":
                "Uploaded file is empty."
            }), 400


        # -------------------------------------------------
        # CREATE JOB
        # -------------------------------------------------

        with jobs_lock:

            jobs[job_id] = {

                "status": "starting",

                "progress": 0,

                "filename": "",

                "output_file": output_file,

                "original_name":
                    original_name,

                "error": None
            }


        # -------------------------------------------------
        # START BACKGROUND THREAD
        # -------------------------------------------------

        worker = threading.Thread(

            target=convert_worker,

            args=(

                job_id,

                input_file,

                output_file,

                output_format
            ),

            daemon=True
        )


        worker.start()


        # -------------------------------------------------
        # RETURN JOB ID
        # -------------------------------------------------

        return jsonify({

            "job_id": job_id,

            "status": "starting"
        })


    except Exception as e:

        return jsonify({

            "error": str(e)

        }), 500


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
    )


    if not job_id:

        return jsonify({

            "status": "error",

            "progress": 0,

            "error": "Missing job ID."
        }), 400


    with jobs_lock:

        job = jobs.get(job_id)


    if not job:

        return jsonify({

            "status": "error",

            "progress": 0,

            "error": "Job not found."
        }), 404


    return jsonify({

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

        "filename":
            job.get(
                "filename",
                ""
            ),

        "error":
            job.get(
                "error",
                None
            )
    })


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
    )


    if not job_id:

        return jsonify({

            "error": "Missing job ID."
        }), 400


    with jobs_lock:

        job = jobs.get(job_id)


    if not job:

        return jsonify({

            "error": "Job not found."
        }), 404


    if job.get("status") != "completed":

        return jsonify({

            "error":
            "Conversion is not completed yet."
        }), 400


    output_file = job.get(
        "output_file"
    )


    if not output_file:

        return jsonify({

            "error":
            "Output file path is missing."
        }), 500


    if not os.path.exists(
        output_file
    ):

        return jsonify({

            "error":
            "Converted file was not found."
        }), 404


    download_name = job.get(
        "filename",
        "converted_file"
    )


    return send_file(

        output_file,

        as_attachment=True,

        download_name=download_name
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "status": "ok",

        "ffmpeg": FFMPEG
    })


# =========================================================
# RUN SERVER
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
