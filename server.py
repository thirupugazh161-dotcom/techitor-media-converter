import os
import uuid
import threading
import subprocess
from flask import Flask, request, jsonify, send_file
import imageio_ffmpeg


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
# HOME / HEALTH CHECK
# =========================================================

@app.route("/")
def home():
    return "Techitor Media Converter Server Running"


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "ffmpeg": os.path.exists(FFMPEG)
    })


# =========================================================
# FILE CONVERSION FUNCTION
# =========================================================

def convert_file(job_id, input_path, output_path, output_format):

    jobs[job_id] = {
        "status": "converting",
        "progress": 0,
        "message": "Preparing conversion...",
        "output": None,
        "error": None
    }

    try:

        # -------------------------------------------------
        # Determine conversion settings
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

        elif output_format == "wav":

            command = [
                FFMPEG,
                "-y",
                "-i", input_path,
                "-vn",
                "-c:a", "pcm_s16le",
                output_path
            ]

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
                f"Unsupported output format: {output_format}"
            )


        # -------------------------------------------------
        # Run FFmpeg
        # -------------------------------------------------

        jobs[job_id]["message"] = "Converting..."

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        stdout, stderr = process.communicate()


        # -------------------------------------------------
        # Check FFmpeg result
        # -------------------------------------------------

        if process.returncode != 0:

            error_text = stderr[-3000:] if stderr else "Unknown FFmpeg error"

            jobs[job_id]["status"] = "failed"
            jobs[job_id]["progress"] = 0
            jobs[job_id]["message"] = "Conversion failed."
            jobs[job_id]["error"] = error_text

            return


        # -------------------------------------------------
        # Check output file
        # -------------------------------------------------

        if not os.path.exists(output_path):

            jobs[job_id]["status"] = "failed"
            jobs[job_id]["message"] = "Output file was not created."
            jobs[job_id]["error"] = "FFmpeg completed but output file is missing."

            return


        if os.path.getsize(output_path) == 0:

            jobs[job_id]["status"] = "failed"
            jobs[job_id]["message"] = "Output file is empty."
            jobs[job_id]["error"] = "Generated file has 0 bytes."

            return


        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "Conversion completed successfully!"
        jobs[job_id]["output"] = output_path
        jobs[job_id]["error"] = None


    except Exception as e:

        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = "Conversion failed."
        jobs[job_id]["error"] = str(e)


# =========================================================
# UPLOAD + START CONVERSION
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


        # -------------------------------------------------
        # Get requested output format
        # -------------------------------------------------

        output_format = request.form.get(
            "format",
            request.form.get(
                "output_format",
                "mp3"
            )
        ).lower().strip()


        if output_format not in ALLOWED_OUTPUTS:

            return jsonify({
                "error": f"Unsupported output format: {output_format}"
            }), 400


        # -------------------------------------------------
        # Detect input extension
        # -------------------------------------------------

        original_name = uploaded_file.filename

        input_extension = os.path.splitext(
            original_name
        )[1].lower().replace(".", "")


        if input_extension not in ALLOWED_INPUTS:

            return jsonify({
                "error": f"Unsupported input format: {input_extension}"
            }), 400


        # -------------------------------------------------
        # Create unique job
        # -------------------------------------------------

        job_id = str(uuid.uuid4())

        safe_input_name = f"{job_id}.{input_extension}"

        safe_output_name = f"{job_id}.{output_format}"

        input_path = os.path.join(
            TEMP_DIR,
            safe_input_name
        )

        output_path = os.path.join(
            TEMP_DIR,
            safe_output_name
        )


        # -------------------------------------------------
        # Save uploaded file
        # -------------------------------------------------

        uploaded_file.save(input_path)


        # -------------------------------------------------
        # Initialize job
        # -------------------------------------------------

        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "message": "Preparing conversion...",
            "output": None,
            "error": None
        }


        # -------------------------------------------------
        # Start conversion in background
        # -------------------------------------------------

        thread = threading.Thread(
            target=convert_file,
            args=(
                job_id,
                input_path,
                output_path,
                output_format
            ),
            daemon=True
        )

        thread.start()


        return jsonify({
            "success": True,
            "job_id": job_id,
            "message": "Conversion started",
            "status": "queued"
        })


    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =========================================================
# PROGRESS
# =========================================================

@app.route("/progress/<job_id>", methods=["GET"])
def progress(job_id):

    job = jobs.get(job_id)

    if not job:

        return jsonify({
            "status": "failed",
            "progress": 0,
            "message": "Job not found.",
            "error": "Invalid job ID"
        }), 404


    return jsonify({
        "status": job.get("status"),
        "progress": job.get("progress", 0),
        "message": job.get("message"),
        "error": job.get("error"),
        "download": (
            f"/download/{job_id}"
            if job.get("status") == "completed"
            else None
        )
    })


# =========================================================
# DOWNLOAD
# =========================================================

@app.route("/download/<job_id>", methods=["GET"])
def download(job_id):

    job = jobs.get(job_id)

    if not job:

        return jsonify({
            "error": "Job not found"
        }), 404


    if job.get("status") != "completed":

        return jsonify({
            "error": "Conversion is not completed yet."
        }), 400


    output_path = job.get("output")


    if not output_path or not os.path.exists(output_path):

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
def cleanup(job_id):

    job = jobs.get(job_id)

    if not job:

        return jsonify({
            "error": "Job not found"
        }), 404


    try:

        output_path = job.get("output")

        if output_path and os.path.exists(output_path):
            os.remove(output_path)


        # Find input file

        for filename in os.listdir(TEMP_DIR):

            if filename.startswith(job_id):

                file_path = os.path.join(
                    TEMP_DIR,
                    filename
                )

                if os.path.exists(file_path):
                    os.remove(file_path)


        del jobs[job_id]


        return jsonify({
            "success": True,
            "message": "Files cleaned successfully."
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
        "error": "File is too large."
    }), 413


@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "error": "Endpoint not found."
    }), 404


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
