import os
import subprocess
import tempfile
import shutil
import uuid

from flask import Flask, request, jsonify, send_file, send_from_directory
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

ALLOWED_EXTENSIONS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm",
}


# =========================================================
# FILE CHECK
# =========================================================

def allowed_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()

    return extension in ALLOWED_EXTENSIONS


# =========================================================
# MIME TYPES
# =========================================================

def get_mimetype(extension):

    mimetypes = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "mkv": "video/x-matroska",
        "webm": "video/webm",
    }

    return mimetypes.get(
        extension,
        "application/octet-stream"
    )


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

    path = os.path.join(
        BASE_DIR,
        filename
    )

    if os.path.isfile(path):

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
    })


# =========================================================
# CONVERSION
# =========================================================

@app.route("/api/convert", methods=["POST"])
def convert_media():

    temp_dir = None

    try:

        # -------------------------------------------------
        # CHECK UPLOAD
        # -------------------------------------------------

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


        if not allowed_file(uploaded_file.filename):

            return jsonify({
                "success": False,
                "error": "Unsupported input file format."
            }), 400


        # -------------------------------------------------
        # GET OUTPUT FORMAT
        # -------------------------------------------------

        output_format = request.form.get(
            "format",
            ""
        ).strip().lower()


        # Also support output_format if frontend uses it
        if not output_format:

            output_format = request.form.get(
                "output_format",
                ""
            ).strip().lower()


        if output_format not in ALLOWED_EXTENSIONS:

            return jsonify({
                "success": False,
                "error": "Unsupported output format."
            }), 400


        # -------------------------------------------------
        # CREATE TEMP DIRECTORY
        # -------------------------------------------------

        temp_dir = tempfile.mkdtemp(
            prefix="techitor_"
        )


        # -------------------------------------------------
        # INPUT
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
        # OUTPUT
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
        # BASE FFMPEG COMMAND
        # =================================================

        command = [
            FFMPEG_PATH,

            "-y",

            "-hide_banner",

            "-loglevel",
            "error",

            # Important for Render memory usage
            "-threads",
            "1",

            "-i",
            input_path,
        ]


        # =================================================
        # AUDIO OUTPUT
        # =================================================

        if output_format == "mp3":

            command += [

                "-map",
                "0:a:0",

                "-vn",

                "-c:a",
                "libmp3lame",

                "-b:a",
                "192k",
            ]


        elif output_format == "wav":

            command += [

                "-map",
                "0:a:0",

                "-vn",

                "-c:a",
                "pcm_s16le",
            ]


        elif output_format == "m4a":

            command += [

                "-map",
                "0:a:0",

                "-vn",

                "-c:a",
                "aac",

                "-b:a",
                "192k",
            ]


        # =================================================
        # MP4
        # =================================================

        elif output_format == "mp4":

            command += [

                "-map",
                "0:v:0",

                "-map",
                "0:a:0?",

                "-c:v",
                "libx264",

                "-preset",
                "ultrafast",

                "-crf",
                "28",

                "-pix_fmt",
                "yuv420p",

                "-c:a",
                "aac",

                "-b:a",
                "128k",

                "-movflags",
                "+faststart",
            ]


        # =================================================
        # MOV
        # =================================================

        elif output_format == "mov":

            command += [

                "-map",
                "0:v:0",

                "-map",
                "0:a:0?",

                "-c:v",
                "libx264",

                "-preset",
                "ultrafast",

                "-crf",
                "28",

                "-pix_fmt",
                "yuv420p",

                "-c:a",
                "aac",

                "-b:a",
                "128k",
            ]


        # =================================================
        # MKV
        # =================================================

        elif output_format == "mkv":

            command += [

                "-map",
                "0:v:0",

                "-map",
                "0:a:0?",

                "-c:v",
                "libx264",

                "-preset",
                "ultrafast",

                "-crf",
                "28",

                "-pix_fmt",
                "yuv420p",

                "-c:a",
                "aac",

                "-b:a",
                "128k",
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

                # VP8 is lighter than VP9
                "-c:v",
                "libvpx",

                "-b:v",
                "1M",

                "-crf",
                "32",

                # Faster VP8 encoding
                "-deadline",
                "realtime",

                "-cpu-used",
                "8",

                "-c:a",
                "libopus",

                "-b:a",
                "96k",
            ]


        # =================================================
        # OUTPUT FILE
        # =================================================

        command.append(
            output_path
        )


        # =================================================
        # RUN FFMPEG
        # =================================================

        result = subprocess.run(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            timeout=900
        )


        # =================================================
        # FFMPEG FAILED
        # =================================================

        if result.returncode != 0:

            error_message = result.stderr.strip()

            if not error_message:

                error_message = (
                    "FFmpeg conversion failed."
                )

            return jsonify({

                "success": False,

                "error": error_message[-5000:]
            }), 500


        # =================================================
        # CHECK OUTPUT
        # =================================================

        if not os.path.exists(output_path):

            return jsonify({

                "success": False,

                "error":
                    "FFmpeg completed but output file was not created."
            }), 500


        if os.path.getsize(output_path) == 0:

            return jsonify({

                "success": False,

                "error":
                    "FFmpeg created an empty output file."
            }), 500


        # =================================================
        # SEND RESULT
        # =================================================

        return send_file(

            output_path,

            mimetype=get_mimetype(
                output_format
            ),

            as_attachment=True,

            download_name=output_filename
        )


    except subprocess.TimeoutExpired:

        return jsonify({

            "success": False,

            "error":
                "Conversion timed out. Try a shorter or smaller video."
        }), 500


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)
        }), 500


    finally:

        # -------------------------------------------------
        # Cleanup is intentionally delayed by a small
        # background process so send_file can finish.
        # -------------------------------------------------

        if temp_dir:

            try:

                cleanup_script = f"""
import shutil
import time

time.sleep(10)

try:
    shutil.rmtree({temp_dir!r})
except:
    pass
"""

                subprocess.Popen([
                    "python",
                    "-c",
                    cleanup_script
                ])

            except Exception:

                pass


# =========================================================
# 413
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({

        "success": False,

        "error":
            "File is too large. Maximum size is 500 MB."
    }), 413


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
