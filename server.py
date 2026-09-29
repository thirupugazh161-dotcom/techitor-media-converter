import os
import uuid
import threading
import subprocess
import imageio_ffmpeg

from flask import Flask, request, jsonify, send_file

# =========================================================
# APP SETUP
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)

app = Flask(__name__)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

jobs = {}


# =========================================================
# FORMAT SETTINGS
# =========================================================

VIDEO_FORMATS = {
    "mp4": {
        "extension": "mp4",
        "args": [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart"
        ]
    },

    "mov": {
        "extension": "mov",
        "args": [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart"
        ]
    },

    "mkv": {
        "extension": "mkv",
        "args": [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k"
        ]
    },

    "webm": {
        "extension": "webm",
        "args": [
            "-c:v", "libvpx-vp9",
            "-crf", "30",
            "-b:v", "0",
            "-c:a", "libopus",
            "-b:a", "128k"
        ]
    }
}


AUDIO_FORMATS = {
    "mp3": {
        "extension": "mp3",
        "args": [
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "192k"
        ]
    },

    "wav": {
        "extension": "wav",
        "args": [
            "-vn",
            "-c:a", "pcm_s16le"
        ]
    },

    "m4a": {
        "extension": "m4a",
        "args": [
            "-vn",
            "-c:a", "aac",
            "-b:a", "192k"
        ]
    }
}


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/")
def home():
    return "Techitor Media Converter Server Running"


# =========================================================
# UPLOAD + CONVERSION
# =========================================================

@app.route("/convert", methods=["POST"])
def convert():

    try:

        if "file" not in request.files:
            return jsonify({
                "error": "No file uploaded"
            }), 400

        uploaded_file = request.files["file"]

        if uploaded_file.filename == "":
            return jsonify({
                "error": "No file selected"
            }), 400

        output_format = request.form.get("format", "").lower().strip()

        if not output_format:
            return jsonify({
                "error": "No output format selected"
            }), 400

        if (
            output_format not in VIDEO_FORMATS
            and output_format not in AUDIO_FORMATS
        ):
            return jsonify({
                "error": f"Unsupported format: {output_format}"
            }), 400

        # -------------------------------------------------
        # Create unique job
        # -------------------------------------------------

        job_id = str(uuid.uuid4())

        original_name = os.path.basename(uploaded_file.filename)

        name_without_ext = os.path.splitext(original_name)[0]

        input_path = os.path.join(
            TEMP_DIR,
            f"{job_id}_input{os.path.splitext(original_name)[1]}"
        )

        output_path = os.path.join(
            TEMP_DIR,
            f"{job_id}_{name_without_ext}.{output_format}"
        )

        uploaded_file.save(input_path)

        jobs[job_id] = {
            "status": "starting",
            "progress": 0,
            "message": "Preparing conversion...",
            "output": None,
            "error": None
        }

        # -------------------------------------------------
        # Start background conversion
        # -------------------------------------------------

        thread = threading.Thread(
            target=run_conversion,
            args=(
                job_id,
                input_path,
                output_path,
                output_format
            )
        )

        thread.daemon = True
        thread.start()

        return jsonify({
            "success": True,
            "job_id": job_id
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# =========================================================
# RUN FFMPEG CONVERSION
# =========================================================

def run_conversion(
    job_id,
    input_path,
    output_path,
    output_format
):

    try:

        jobs[job_id]["status"] = "converting"
        jobs[job_id]["progress"] = 5
        jobs[job_id]["message"] = "Converting..."

        # -------------------------------------------------
        # Select codec settings
        # -------------------------------------------------

        if output_format in VIDEO_FORMATS:

            format_config = VIDEO_FORMATS[output_format]

        else:

            format_config = AUDIO_FORMATS[output_format]

        command = [
            FFMPEG,

            "-y",

            "-i",
            input_path
        ]

        # -------------------------------------------------
        # Add conversion arguments
        # -------------------------------------------------

        command.extend(format_config["args"])

        command.append(output_path)

        # -------------------------------------------------
        # Execute FFmpeg
        # -------------------------------------------------

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )

        stdout, stderr = process.communicate()

        # -------------------------------------------------
        # Check result
        # -------------------------------------------------

        if process.returncode != 0:

            print("FFMPEG ERROR:")
            print(stderr)

            jobs[job_id]["status"] = "failed"
            jobs[job_id]["progress"] = 0
            jobs[job_id]["message"] = (
                "Conversion failed: "
                + get_ffmpeg_error(stderr)
            )
            jobs[job_id]["error"] = stderr

            cleanup_file(input_path)

            return

        # -------------------------------------------------
        # Verify output file
        # -------------------------------------------------

        if not os.path.exists(output_path):

            jobs[job_id]["status"] = "failed"
            jobs[job_id]["progress"] = 0
            jobs[job_id]["message"] = (
                "FFmpeg completed but output file was not created."
            )

            cleanup_file(input_path)

            return

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Conversion completed successfully!"
        jobs[job_id]["output"] = output_path

        cleanup_file(input_path)

    except Exception as e:

        print("CONVERSION EXCEPTION:")
        print(str(e))

        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = str(e)
        jobs[job_id]["error"] = str(e)

        cleanup_file(input_path)


# =========================================================
# PROGRESS
# =========================================================

@app.route("/progress/<job_id>", methods=["GET"])
def progress(job_id):

    if job_id not in jobs:

        return jsonify({
            "error": "Job not found"
        }), 404

    job = jobs[job_id]

    response = {
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"]
    }

    if job["status"] == "completed":

        response["download_url"] = (
            f"/download/{job_id}"
        )

    if job["status"] == "failed":

        response["error"] = job.get(
            "error",
            job["message"]
        )

    return jsonify(response)


# =========================================================
# DOWNLOAD
# =========================================================

@app.route("/download/<job_id>", methods=["GET"])
def download(job_id):

    if job_id not in jobs:

        return jsonify({
            "error": "Job not found"
        }), 404

    job = jobs[job_id]

    if job["status"] != "completed":

        return jsonify({
            "error": "Conversion is not completed"
        }), 400

    output_path = job["output"]

    if not output_path or not os.path.exists(output_path):

        return jsonify({
            "error": "Output file not found"
        }), 404

    return send_file(
        output_path,
        as_attachment=True,
        download_name=os.path.basename(output_path)
    )


# =========================================================
# ERROR EXTRACTION
# =========================================================

def get_ffmpeg_error(stderr):

    if not stderr:
        return "Unknown FFmpeg error."

    lines = stderr.strip().splitlines()

    useful_lines = []

    for line in reversed(lines):

        line = line.strip()

        if line:

            useful_lines.append(line)

        if len(useful_lines) >= 3:
            break

    useful_lines.reverse()

    return " | ".join(useful_lines)


# =========================================================
# CLEANUP
# =========================================================

def cleanup_file(path):

    try:

        if path and os.path.exists(path):
            os.remove(path)

    except Exception as e:

        print(
            "Cleanup error:",
            str(e)
        )


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
        debug=False
    )
