import os
import subprocess
import tempfile
import shutil

from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
import imageio_ffmpeg


# =========================================================
# APP CONFIG
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=None)

app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


# =========================================================
# FFMPEG
# =========================================================

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


# =========================================================
# ALLOWED FORMATS
# =========================================================

ALLOWED_FORMATS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm",
}


# =========================================================
# FILE VALIDATION
# =========================================================

def allowed_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_FORMATS


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


# =========================================================
# STATIC FILES
# =========================================================

@app.route("/<path:filename>")
def static_files(filename):

    requested_path = os.path.join(
        BASE_DIR,
        filename
    )

    if os.path.isfile(requested_path):

        return send_from_directory(
            BASE_DIR,
            filename
        )

    return jsonify({
        "success": False,
        "error": "File not found"
    }), 404


# =========================================================
# HEALTH
# =========================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "success": True,
        "status": "ok",
        "service": "Techitor Media Converter",
        "ffmpeg": True
    }), 200


# =========================================================
# CONVERT
# =========================================================

@app.route("/api/convert", methods=["POST"])
def convert_media():

    temp_dir = None

    try:

        # -------------------------------------------------
        # CHECK FILE
        # -------------------------------------------------

        if "file" not in request.files:

            return jsonify({
                "success": False,
                "error": "No file uploaded."
            }), 400

        uploaded_file = request.files["file"]

        if not uploaded_file.filename:

            return jsonify({
                "success": False,
                "error": "No file selected."
            }), 400

        if not allowed_file(uploaded_file.filename):

            return jsonify({
                "success": False,
                "error": "Unsupported input file format."
            }), 400


        # -------------------------------------------------
        # GET OUTPUT FORMAT
        # -------------------------------------------------

        output_format = (
            request.form.get("format")
            or request.form.get("output_format")
            or ""
        ).strip().lower()


        if output_format not in ALLOWED_FORMATS:

            return jsonify({
                "success": False,
                "error": "Invalid output format."
            }), 400


        # -------------------------------------------------
        # TEMP DIRECTORY
        # -------------------------------------------------

        temp_dir = tempfile.mkdtemp(
            prefix="techitor_"
        )


        # -------------------------------------------------
        # INPUT FILE
        # -------------------------------------------------

        original_name = secure_filename(
            uploaded_file.filename
        )

        input_path = os.path.join(
            temp_dir,
            original_name
        )

        uploaded_file.save(input_path)


        # -------------------------------------------------
        # OUTPUT FILE
        # -------------------------------------------------

        base_name = os.path.splitext(
            original_name
        )[0]

        output_filename = (
            f"{base_name}_converted.{output_format}"
        )

        output_path = os.path.join(
            temp_dir,
            output_filename
        )


        # =================================================
        # FFMPEG BASE COMMAND
        # =================================================

        command = [
            FFMPEG_PATH,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            input_path
        ]


        # =================================================
        # AUDIO
        # =================================================

        if output_format == "mp3":

            command += [
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "192k"
            ]


        elif output_format == "wav":

            command += [
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "pcm_s16le"
            ]


        elif output_format == "m4a":

            command += [
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "192k"
            ]


        # =================================================
        # VIDEO
        # =================================================

        elif output_format in {
            "mp4",
            "mov",
            "mkv"
        }:

            command += [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k"
            ]


        # =================================================
        # WEBM
        # =================================================

        elif output_format == "webm":

            command += [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c:v",
                "libvpx",
                "-b:v",
                "1M",
                "-crf",
                "30",
                "-c:a",
                "libopus",
                "-b:a",
                "128k"
            ]


        # =================================================
        # OUTPUT
        # =================================================

        command.append(output_path)


        # =================================================
        # RUN FFMPEG
        # =================================================

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600
        )


        # =================================================
        # FFMPEG ERROR
        # =================================================

        if result.returncode != 0:

            return jsonify({
                "success": False,
                "error": "FFmpeg conversion failed.",
                "details": result.stderr[-5000:]
            }), 500


        # =================================================
        # OUTPUT CHECK
        # =================================================

        if not os.path.isfile(output_path):

            return jsonify({
                "success": False,
                "error": "Converted file was not created."
            }), 500


        output_size = os.path.getsize(
            output_path
        )


        if output_size == 0:

            return jsonify({
                "success": False,
                "error": "Converted file is empty."
            }), 500


        # =================================================
        # SEND FILE
        # =================================================

        response = send_file(
            output_path,
            mimetype=_get_mimetype(output_format),
            as_attachment=True,
            download_name=output_filename,
            conditional=False
        )

        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"


        return response


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


    finally:

        # NOTE:
        # Don't delete temp_dir here because send_file()
        # still needs the output file while the response
        # is being sent.

        pass


# =========================================================
# MIME TYPES
# =========================================================

def _get_mimetype(extension):

    mimetypes = {

        "mp3":
            "audio/mpeg",

        "wav":
            "audio/wav",

        "m4a":
            "audio/mp4",

        "mp4":
            "video/mp4",

        "mov":
            "video/quicktime",

        "mkv":
            "video/x-matroska",

        "webm":
            "video/webm",
    }

    return mimetypes.get(
        extension,
        "application/octet-stream"
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({
        "success": False,
        "error": "File is too large. Maximum allowed size is 500 MB."
    }), 413


@app.errorhandler(404)
def page_not_found(error):

    return jsonify({
        "success": False,
        "error": "Page not found."
    }), 404


# =========================================================
# RUN
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
