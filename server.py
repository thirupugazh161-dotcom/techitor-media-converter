import os
import uuid
import threading
import subprocess

from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    send_from_directory
)

import imageio_ffmpeg


# =========================================================
# APP SETUP
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(TEMP_DIR, exist_ok=True)

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

jobs = {}


# =========================================================
# SUPPORTED FORMATS
# =========================================================

ALLOWED_INPUTS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm",
    "aac",
    "flac",
    "ogg"
}

ALLOWED_OUTPUTS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm"
}


# =========================================================
# FRONTEND
# =========================================================

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<path:filename>")
def frontend_files(filename):
    file_path = os.path.join(BASE_DIR, filename)

    if os.path.isfile(file_path):
        return send_from_directory(BASE_DIR, filename)

    return jsonify({
        "error": "File not found"
    }), 404


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "ffmpeg": os.path.exists(FFMPEG)
    })


# =========================================================
# CONVERSION
# =========================================================

def convert_file(job_id, input_path, output_path, output_format):

    jobs[job_id] = {
        "status": "converting",
        "progress": 10,
        "message": "Preparing conversion...",
        "output": None,
        "error": None
    }

    try:

        # -------------------------------------------------
        # MP3
        # -------------------------------------------------

        if output_format == "mp3":

            command = [
                FFMPEG,
                "-y",
                "-i", input_path,
                "-vn",
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                output_path
            ]

        # -------------------------------------------------
        # WAV
        # -------------------------------------------------

        elif output_format == "wav":

            command = [
                FFMPEG,
                "-y",
                "-i", input_path,
                "-vn",
                "-c:a", "pcm_s16le",
                output_path
            ]

        # -------------------------------------------------
        # M4A
        # -------------------------------------------------

        elif output_format == "m4a":

            command = [
                FFMPEG,
                "-y",
                "-i", input_path,
                "-vn",
                "-c:a", "aac",
                "-b:a", "192k",
                output_path
            ]

        # -------------------------------------------------
        # MP4
        # -------------------------------------------------

        elif output_format == "mp4":

            command = [
                FFMPEG,
                "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_path
            ]

        # -------------------------------------------------
        # MOV
        # -------------------------------------------------

        elif output_format == "mov":

            command = [
                FFMPEG,
                "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                output_path
            ]

        # -------------------------------------------------
        # MKV
        # -------------------------------------------------

        elif output_format == "mkv":

            command = [
                FFMPEG,
                "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                output_path
            ]

        # -------------------------------------------------
        # WEBM
        # -------------------------------------------------

        elif output_format == "webm":

            command = [
                FFMPEG,
                "-y",
                "-i", input_path,
                "-c:v", "libvpx-vp9",
                "-c:a", "libopus",
                output_path
            ]

        else:

            raise Exception(
                "Unsupported output format: " + output_format
            )


        # -------------------------------------------------
        # RUN FFMPEG
        # -------------------------------------------------

        jobs[job_id]["progress"] = 20
        jobs[job_id]["message"] = "Converting..."


        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )


        # -------------------------------------------------
        # FFmpeg ERROR
        # -------------------------------------------------

        if process.returncode != 0:

            error_message = process.stderr[-4000:]

            jobs[job_id] = {
                "status": "failed",
                "progress": 0,
                "message": "Conversion failed.",
                "output": None,
                "error": error_message
            }

            return


        # -------------------------------------------------
        # CHECK OUTPUT
        # -------------------------------------------------

        if not os.path.exists(output_path):

            jobs[job_id] = {
                "status": "failed",
                "progress": 0,
                "message": "Output file was not created.",
                "output": None,
                "error": "FFmpeg finished but output file does not exist."
            }

            return


        if os.path.getsize(output_path) == 0:

            jobs[job_id] = {
                "status": "failed",
                "progress": 0,
                "message": "Output file is empty.",
                "output": None,
                "error": "Generated file is 0 bytes."
            }

            return


        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        jobs[job_id] = {
            "status": "completed",
            "progress": 100,
            "message": "Conversion completed successfully!",
            "output": output_path,
            "error": None
        }


    except Exception as e:

        jobs[job_id] = {
            "status": "failed",
            "progress": 0,
            "message": "Conversion failed.",
            "output": None,
            "error": str(e)
        }


# =========================================================
# CONVERT API
# =========================================================

@app.route("/convert", methods=["POST"])
@app.route("/api/convert", methods=["POST"])
def convert():

    try:

        if "file" not in request.files:

            return jsonify({
                "success": False,
                "error": "No file uploaded."
            }), 400


        uploaded_file = request.files["file"]


        if uploaded_file.filename == "":

            return jsonify({
                "success": False,
                "error": "No file selected."
            }), 400


        # -------------------------------------------------
        # OUTPUT FORMAT
        # -------------------------------------------------

        output_format = (
            request.form.get("format")
            or request.form.get("output_format")
            or request.form.get("targetFormat")
            or "mp3"
        )

        output_format = output_format.lower().strip()


        if output_format not in ALLOWED_OUTPUTS:

            return jsonify({
                "success": False,
                "error": "Unsupported output format: " + output_format
            }), 400


        # -------------------------------------------------
        # INPUT FORMAT
        # -------------------------------------------------

        original_name = uploaded_file.filename

        input_extension = os.path.splitext(
            original_name
        )[1].lower().replace(".", "")


        if input_extension not in ALLOWED_INPUTS:

            return jsonify({
                "success": False,
                "error": "Unsupported input format: " + input_extension
            }), 400


        # -------------------------------------------------
        # JOB ID
        # -------------------------------------------------

        job_id = str(uuid.uuid4())


        input_filename = (
            job_id + "." + input_extension
        )

        output_filename = (
            job_id + "." + output_format
        )


        input_path = os.path.join(
            TEMP_DIR,
            input_filename
        )

        output_path = os.path.join(
            TEMP_DIR,
            output_filename
        )


        # -------------------------------------------------
        # SAVE FILE
        # -------------------------------------------------

        uploaded_file.save(input_path)


        # -------------------------------------------------
        # INITIAL JOB
        # -------------------------------------------------

        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "message": "Preparing conversion...",
            "output": None,
            "error": None
        }


        # -------------------------------------------------
        # BACKGROUND CONVERSION
        # -------------------------------------------------

        thread = threading.Thread(
            target=convert_file,
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
            "job_id": job_id,
            "status": "queued",
            "message": "Conversion started."
        })


    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# PROGRESS API
# =========================================================

@app.route("/progress/<job_id>")
@app.route("/api/progress/<job_id>")
def progress(job_id):

    job = jobs.get(job_id)


    if not job:

        return jsonify({
            "status": "failed",
            "progress": 0,
            "message": "Job not found.",
            "error": "Invalid job ID."
        }), 404


    response = {
        "status": job.get("status"),
        "progress": job.get("progress", 0),
        "message": job.get("message"),
        "error": job.get("error")
    }


    if job.get("status") == "completed":

        response["download"] = (
            "/download/" + job_id
        )

        response["download_url"] = (
            "/download/" + job_id
        )


    return jsonify(response)


# =========================================================
# DOWNLOAD API
# =========================================================

@app.route("/download/<job_id>")
@app.route("/api/download/<job_id>")
def download(job_id):

    job = jobs.get(job_id)


    if not job:

        return jsonify({
            "error": "Job not found."
        }), 404


    if job.get("status") != "completed":

        return jsonify({
            "error": "Conversion is not completed."
        }), 400


    output_path = job.get("output")


    if not output_path:

        return jsonify({
            "error": "Output path missing."
        }), 404


    if not os.path.exists(output_path):

        return jsonify({
            "error": "Output file not found."
        }), 404


    return send_file(
        output_path,
        as_attachment=True,
        download_name=os.path.basename(output_path)
    )


# =========================================================
# CLEANUP
# =========================================================

@app.route("/cleanup/<job_id>", methods=["DELETE"])
@app.route("/api/cleanup/<job_id>", methods=["DELETE"])
def cleanup(job_id):

    job = jobs.get(job_id)


    if not job:

        return jsonify({
            "error": "Job not found."
        }), 404


    try:

        for filename in os.listdir(TEMP_DIR):

            if filename.startswith(job_id):

                path = os.path.join(
                    TEMP_DIR,
                    filename
                )

                if os.path.isfile(path):

                    os.remove(path)


        if job_id in jobs:

            del jobs[job_id]


        return jsonify({
            "success": True,
            "message": "Cleanup completed."
        })


    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "success": False,
        "error": "File is too large. Maximum size is 1 GB."
    }), 413


@app.errorhandler(500)
def internal_error(error):

    return jsonify({
        "success": False,
        "error": "Internal server error."
    }), 500


# =========================================================
# START
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
