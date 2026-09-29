import os
import re
import uuid
import threading
import subprocess

from flask import Flask, request, jsonify, send_file
import imageio_ffmpeg

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

jobs = {}


def get_duration(input_file):
    """Get media duration in seconds using FFmpeg."""

    try:
        result = subprocess.run(
            [
                FFMPEG,
                "-i",
                input_file
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        match = re.search(
            r"Duration:\s*(\d+):(\d+):([\d.]+)",
            result.stderr
        )

        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))

            return hours * 3600 + minutes * 60 + seconds

    except Exception:
        pass

    return 0


def run_conversion(job_id, input_file, output_file, output_format):

    jobs[job_id]["status"] = "converting"
    jobs[job_id]["progress"] = 0
    jobs[job_id]["message"] = "Converting..."


    duration = get_duration(input_file)

    command = [
        FFMPEG,
        "-y",
        "-i",
        input_file
    ]


    # -----------------------------
    # OUTPUT SETTINGS
    # -----------------------------

    if output_format == "mp3":

        command += [
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k"
        ]

    elif output_format == "wav":

        command += [
            "-vn",
            "-codec:a",
            "pcm_s16le"
        ]

    elif output_format == "m4a":

        command += [
            "-vn",
            "-codec:a",
            "aac",
            "-b:a",
            "192k"
        ]

    elif output_format == "webm":

        command += [
            "-c:v",
            "libvpx-vp9",
            "-c:a",
            "libopus"
        ]

    elif output_format == "mkv":

        command += [
            "-c:v",
            "libx264",
            "-c:a",
            "aac"
        ]

    elif output_format == "mov":

        command += [
            "-c:v",
            "libx264",
            "-c:a",
            "aac"
        ]

    else:

        command += [
            "-c:v",
            "libx264",
            "-c:a",
            "aac"
        ]


    command += [
        "-progress",
        "pipe:1",
        "-nostats",
        output_file
    ]


    try:

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )


        for line in process.stdout:

            line = line.strip()

            if line.startswith("out_time_ms="):

                try:

                    current_time = int(
                        line.split("=")[1]
                    ) / 1_000_000

                    if duration > 0:

                        progress = (
                            current_time / duration
                        ) * 100

                        progress = max(
                            0,
                            min(99, progress)
                        )

                        jobs[job_id]["progress"] = round(
                            progress,
                            1
                        )

                except Exception:
                    pass


        process.wait()


        if process.returncode != 0:

            error_output = process.stderr.read()

            jobs[job_id]["status"] = "failed"

            jobs[job_id]["message"] = (
                "Conversion failed."
            )

            jobs[job_id]["error"] = error_output[-2000:]

            return


        jobs[job_id]["progress"] = 100

        jobs[job_id]["status"] = "completed"

        jobs[job_id]["message"] = (
            "Conversion completed successfully!"
        )

        jobs[job_id]["download_url"] = (
            f"/download?id={job_id}"
        )


    except Exception as e:

        jobs[job_id]["status"] = "failed"

        jobs[job_id]["message"] = (
            "Conversion failed."
        )

        jobs[job_id]["error"] = str(e)


    finally:

        if os.path.exists(input_file):

            try:
                os.remove(input_file)
            except Exception:
                pass


# -----------------------------
# HOME
# -----------------------------

@app.route("/")
def home():

    return send_file(
        os.path.join(
            BASE_DIR,
            "index.html"
        )
    )


# -----------------------------
# START CONVERSION
# -----------------------------

@app.route(
    "/convert",
    methods=["POST"]
)
def convert():

    if "file" not in request.files:

        return jsonify({
            "error": "No file uploaded"
        }), 400


    file = request.files["file"]


    if file.filename == "":

        return jsonify({
            "error": "No file selected"
        }), 400


    output_format = request.form.get(
        "format",
        "mp3"
    ).lower()


    allowed_formats = [
        "mp3",
        "wav",
        "m4a",
        "mp4",
        "mov",
        "mkv",
        "webm"
    ]


    if output_format not in allowed_formats:

        return jsonify({
            "error": "Unsupported format"
        }), 400


    job_id = uuid.uuid4().hex


    input_file = os.path.join(
        TEMP_DIR,
        f"{job_id}_input"
    )


    output_file = os.path.join(
        TEMP_DIR,
        f"{job_id}.{output_format}"
    )


    file.save(input_file)


    jobs[job_id] = {

        "status": "starting",

        "progress": 0,

        "message": "Preparing conversion..."

    }


    thread = threading.Thread(

        target=run_conversion,

        args=(
            job_id,
            input_file,
            output_file,
            output_format
        ),

        daemon=True

    )


    thread.start()


    return jsonify({

        "job_id": job_id

    })


# -----------------------------
# PROGRESS
# -----------------------------

@app.route("/progress")
def progress():

    job_id = request.args.get("id")


    if not job_id or job_id not in jobs:

        return jsonify({
            "error": "Job not found"
        }), 404


    return jsonify(
        jobs[job_id]
    )


# -----------------------------
# DOWNLOAD
# -----------------------------

@app.route("/download")
def download():

    job_id = request.args.get("id")


    if not job_id or job_id not in jobs:

        return jsonify({
            "error": "Job not found"
        }), 404


    job = jobs[job_id]


    if job.get("status") != "completed":

        return jsonify({
            "error": "Conversion not completed"
        }), 400


    download_url = job.get(
        "download_url"
    )


    output_file = os.path.join(
        TEMP_DIR,
        job_id
    )


    # Find generated file
    matching_files = [

        f for f in os.listdir(TEMP_DIR)

        if f.startswith(job_id + ".")

    ]


    if not matching_files:

        return jsonify({
            "error": "Output file not found"
        }), 404


    output_file = os.path.join(
        TEMP_DIR,
        matching_files[0]
    )


    return send_file(
        output_file,
        as_attachment=True,
        download_name=matching_files[0]
    )


# -----------------------------
# SERVER
# -----------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
