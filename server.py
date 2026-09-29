import os
import uuid
import threading
import subprocess
import re
from flask import Flask, request, send_file, send_from_directory, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

jobs = {}

ALLOWED_FORMATS = {
    "MP3": ".mp3",
    "WAV": ".wav",
    "M4A": ".m4a",
    "MP4": ".mp4",
    "MOV": ".mov",
    "MKV": ".mkv",
    "WEBM": ".webm"
}


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    return send_file(
        os.path.join(BASE_DIR, "index.html")
    )


# ==========================================
# FRONTEND FILES
# ==========================================

@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(
        BASE_DIR,
        filename
    )


# ==========================================
# START CONVERSION
# ==========================================

@app.route("/convert", methods=["POST"])
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

    requested_format = request.form.get(
        "format",
        "MP3"
    ).upper()

    if requested_format not in ALLOWED_FORMATS:
        return jsonify({
            "error": "Unsupported format"
        }), 400

    job_id = str(uuid.uuid4())

    input_name = os.path.basename(file.filename)

    input_path = os.path.join(
        BASE_DIR,
        f"{job_id}_input"
    )

    extension = ALLOWED_FORMATS[
        requested_format
    ]

    output_path = os.path.join(
        BASE_DIR,
        f"{job_id}_output{extension}"
    )

    file.save(input_path)

    jobs[job_id] = {
        "status": "starting",
        "progress": 0,
        "filename": f"converted{extension}",
        "input": input_path,
        "output": output_path,
        "error": None
    }

    thread = threading.Thread(
        target=run_conversion,
        args=(
            job_id,
            requested_format
        ),
        daemon=True
    )

    thread.start()

    return jsonify({
        "job_id": job_id
    })


# ==========================================
# CONVERSION WORKER
# ==========================================

def run_conversion(job_id, output_format):

    job = jobs[job_id]

    input_path = job["input"]
    output_path = job["output"]

    try:

        # --------------------------------------
        # Get video duration
        # --------------------------------------

        duration_result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                input_path
            ],
            capture_output=True,
            text=True
        )

        try:
            duration = float(
                duration_result.stdout.strip()
            )
        except:
            duration = 0

        # --------------------------------------
        # Build FFmpeg command
        # --------------------------------------

        command = [
            "ffmpeg",
            "-y",
            "-i",
            input_path
        ]

        if output_format == "MP3":

            command += [
                "-vn",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "2"
            ]

        elif output_format == "WAV":

            command += [
                "-vn",
                "-c:a",
                "pcm_s16le"
            ]

        elif output_format == "M4A":

            command += [
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "192k"
            ]

        elif output_format == "MP4":

            command += [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart"
            ]

        elif output_format == "MOV":

            command += [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac"
            ]

        elif output_format == "MKV":

            command += [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "aac"
            ]

        elif output_format == "WEBM":

            command += [
                "-c:v",
                "libvpx-vp9",
                "-crf",
                "30",
                "-b:v",
                "0",
                "-c:a",
                "libopus"
            ]

        command += [
            "-progress",
            "pipe:1",
            "-nostats",
            output_path
        ]

        jobs[job_id]["status"] = "converting"

        # --------------------------------------
        # Run FFmpeg
        # --------------------------------------

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )

        while True:

            line = process.stdout.readline()

            if not line:
                if process.poll() is not None:
                    break
                continue

            line = line.strip()

            # FFmpeg sends time in microseconds
            if line.startswith("out_time_ms="):

                try:

                    time_us = int(
                        line.split("=")[1]
                    )

                    current_seconds = (
                        time_us / 1000000
                    )

                    if duration > 0:

                        progress = (
                            current_seconds
                            / duration
                        ) * 100

                        progress = max(
                            0,
                            min(
                                99,
                                round(progress, 1)
                            )
                        )

                        jobs[job_id][
                            "progress"
                        ] = progress

                except:
                    pass

        return_code = process.wait()

        # --------------------------------------
        # Check result
        # --------------------------------------

        if (
            return_code == 0
            and os.path.exists(output_path)
        ):

            jobs[job_id]["progress"] = 100

            jobs[job_id]["status"] = "completed"

        else:

            jobs[job_id]["status"] = "error"

            jobs[job_id]["error"] = (
                "FFmpeg conversion failed."
            )

    except Exception as e:

        jobs[job_id]["status"] = "error"

        jobs[job_id]["error"] = str(e)

    finally:

        # Remove input file
        if os.path.exists(input_path):

            try:
                os.remove(input_path)
            except:
                pass


# ==========================================
# PROGRESS
# ==========================================

@app.route("/progress")
def progress():

    job_id = request.args.get("id")

    if not job_id:
        return jsonify({
            "error": "Missing job ID"
        }), 400

    if job_id not in jobs:
        return jsonify({
            "error": "Job not found"
        }), 404

    job = jobs[job_id]

    return jsonify({
        "status": job["status"],
        "progress": job["progress"],
        "filename": job["filename"],
        "error": job["error"]
    })


# ==========================================
# DOWNLOAD
# ==========================================

@app.route("/download")
def download():

    job_id = request.args.get("id")

    if not job_id:
        return jsonify({
            "error": "Missing job ID"
        }), 400

    if job_id not in jobs:
        return jsonify({
            "error": "Job not found"
        }), 404

    job = jobs[job_id]

    if job["status"] != "completed":
        return jsonify({
            "error": "Conversion not completed"
        }), 400

    if not os.path.exists(job["output"]):
        return jsonify({
            "error": "Output file not found"
        }), 404

    return send_file(
        job["output"],
        as_attachment=True,
        download_name=job["filename"]
    )


# ==========================================
# START SERVER
# ==========================================

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
