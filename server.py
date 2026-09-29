import os
import subprocess
import tempfile
import uuid

from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
import imageio_ffmpeg


# --------------------------------------------------
# APP CONFIG
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=None)

app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB


# --------------------------------------------------
# FFmpeg
# --------------------------------------------------

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


# --------------------------------------------------
# ALLOWED FORMATS
# --------------------------------------------------

ALLOWED_EXTENSIONS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm",
}


def allowed_file(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_EXTENSIONS


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


# --------------------------------------------------
# STATIC FILES
# --------------------------------------------------

@app.route("/<path:filename>")
def static_files(filename):
    """
    Serve CSS, JS, images and other frontend files
    from the same directory as server.py.
    """

    requested_path = os.path.join(BASE_DIR, filename)

    if os.path.isfile(requested_path):
        return send_from_directory(BASE_DIR, filename)

    return jsonify({
        "error": "File not found",
        "file": filename
    }), 404


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Techitor Media Converter",
        "ffmpeg": True
    }), 200


# --------------------------------------------------
# CONVERSION
# --------------------------------------------------

@app.route("/api/convert", methods=["POST"])
def convert_media():

    # Check file
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

    # Check extension
    if not allowed_file(uploaded_file.filename):
        return jsonify({
            "success": False,
            "error": "Unsupported input file format."
        }), 400

    # Requested output format
    output_format = request.form.get("format", "mp3").lower()

    if output_format not in ALLOWED_EXTENSIONS:
        return jsonify({
            "success": False,
            "error": "Unsupported output format."
        }), 400

    # --------------------------------------------------
    # TEMP DIRECTORY
    # --------------------------------------------------

    temp_dir = tempfile.mkdtemp(prefix="techitor_")

    original_name = secure_filename(uploaded_file.filename)

    input_path = os.path.join(
        temp_dir,
        original_name
    )

    uploaded_file.save(input_path)

    base_name = os.path.splitext(original_name)[0]

    output_filename = f"{base_name}_converted.{output_format}"

    output_path = os.path.join(
        temp_dir,
        output_filename
    )

    # --------------------------------------------------
    # FFMPEG COMMAND
    # --------------------------------------------------

    command = [
        FFMPEG_PATH,
        "-y",
        "-i",
        input_path,
    ]

    # Audio output
    if output_format == "mp3":

        command += [
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
        ]

    elif output_format == "wav":

        command += [
            "-vn",
            "-codec:a",
            "pcm_s16le",
        ]

    elif output_format == "m4a":

        command += [
            "-vn",
            "-codec:a",
            "aac",
            "-b:a",
            "192k",
        ]

    # Video outputs
    elif output_format in ["mp4", "mov", "mkv", "webm"]:

        if output_format == "webm":

            command += [
                "-c:v",
                "libvpx-vp9",
                "-c:a",
                "libopus",
            ]

        else:

            command += [
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
            ]

    command.append(output_path)

    # --------------------------------------------------
    # RUN FFMPEG
    # --------------------------------------------------

    try:

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600
        )

    except subprocess.TimeoutExpired:

        return jsonify({
            "success": False,
            "error": "Conversion timed out."
        }), 500

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    # --------------------------------------------------
    # CHECK RESULT
    # --------------------------------------------------

    if result.returncode != 0:

        return jsonify({
            "success": False,
            "error": "FFmpeg conversion failed.",
            "details": result.stderr[-3000:]
        }), 500

    if not os.path.exists(output_path):

        return jsonify({
            "success": False,
            "error": "Output file was not created."
        }), 500

    # --------------------------------------------------
    # RETURN FILE
    # --------------------------------------------------

    response = send_file(
        output_path,
        as_attachment=True,
        download_name=output_filename
    )

    # Prevent caching
    response.headers["Cache-Control"] = "no-store"

    return response


# --------------------------------------------------
# ERROR HANDLERS
# --------------------------------------------------

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "success": False,
        "error": "File is too large. Maximum size is 500 MB."
    }), 413


@app.errorhandler(404)
def page_not_found(error):

    return jsonify({
        "success": False,
        "error": "Page not found."
    }), 404


# --------------------------------------------------
# LOCAL RUN
# --------------------------------------------------

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
