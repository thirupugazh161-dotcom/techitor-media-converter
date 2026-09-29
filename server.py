import os
import subprocess
import tempfile

from flask import Flask, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
import imageio_ffmpeg


# =========================================================
# APP CONFIG
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=None)

# 500 MB maximum upload
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


# =========================================================
# FFMPEG
# =========================================================

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


# =========================================================
# INPUT FORMATS
# =========================================================
# Keep this separate from output formats.
# FFmpeg can read many more video formats than the
# formats offered in the output dropdown.

ALLOWED_INPUT_EXTENSIONS = {
    # Common video
    "mp4",
    "mov",
    "mkv",
    "webm",
    "avi",
    "flv",
    "wmv",
    "m4v",
    "mpeg",
    "mpg",
    "m2v",
    "3gp",
    "3g2",
    "ts",
    "mts",
    "m2ts",
    "vob",
    "ogv",

    # Common audio
    "mp3",
    "wav",
    "m4a",
    "aac",
    "flac",
    "ogg",
    "opus",
}


# =========================================================
# OUTPUT FORMATS
# =========================================================

ALLOWED_OUTPUT_FORMATS = {
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

def get_extension(filename):

    if not filename or "." not in filename:
        return ""

    return filename.rsplit(".", 1)[1].lower()


def allowed_input_file(filename):

    extension = get_extension(filename)

    return extension in ALLOWED_INPUT_EXTENSIONS


# =========================================================
# MIME TYPES
# =========================================================

def get_mimetype(extension):

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
# BUILD VIDEO COMMAND
# =========================================================

def build_video_command(
    input_path,
    output_path,
    output_format
):

    command = [
        FFMPEG_PATH,

        "-y",

        "-hide_banner",

        "-loglevel",
        "error",

        # Reduce CPU/RAM pressure on Render
        "-threads",
        "1",

        "-i",
        input_path,

        # First video stream
        "-map",
        "0:v:0",

        # Audio is optional.
        # This allows silent videos to convert.
        "-map",
        "0:a:0?",

        # Make dimensions compatible with yuv420p.
        # Prevents errors such as:
        # "width not divisible by 2"
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
    ]


    # =====================================================
    # MP4
    # =====================================================

    if output_format == "mp4":

        command += [

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

            "-f",
            "mp4",
        ]


    # =====================================================
    # MOV
    # =====================================================

    elif output_format == "mov":

        command += [

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

            "-f",
            "mov",
        ]


    # =====================================================
    # MKV
    # =====================================================

    elif output_format == "mkv":

        command += [

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

            "-f",
            "matroska",
        ]


    # =====================================================
    # WEBM
    # =====================================================

    elif output_format == "webm":

        command += [

            # VP8 instead of VP9.
            # Much lighter for the Render instance.
            "-c:v",
            "libvpx",

            "-b:v",
            "1M",

            "-crf",
            "32",

            "-deadline",
            "realtime",

            "-cpu-used",
            "8",

            "-pix_fmt",
            "yuv420p",

            "-c:a",
            "libopus",

            "-b:a",
            "96k",

            "-f",
            "webm",
        ]


    else:

        raise ValueError(
            "Unsupported video output format."
        )


    command.append(output_path)

    return command


# =========================================================
# BUILD AUDIO COMMAND
# =========================================================

def build_audio_command(
    input_path,
    output_path,
    output_format
):

    command = [

        FFMPEG_PATH,

        "-y",

        "-hide_banner",

        "-loglevel",
        "error",

        "-threads",
        "1",

        "-i",
        input_path,

        # First audio stream
        "-map",
        "0:a:0",

        "-vn",
    ]


    if output_format == "mp3":

        command += [

            "-c:a",
            "libmp3lame",

            "-b:a",
            "192k",

            "-f",
            "mp3",
        ]


    elif output_format == "wav":

        command += [

            "-c:a",
            "pcm_s16le",

            "-f",
            "wav",
        ]


    elif output_format == "m4a":

        command += [

            "-c:a",
            "aac",

            "-b:a",
            "192k",

            "-f",
            "ipod",
        ]


    else:

        raise ValueError(
            "Unsupported audio output format."
        )


    command.append(output_path)

    return command


# =========================================================
# RUN FFMPEG
# =========================================================

def run_ffmpeg(command):

    result = subprocess.run(

        command,

        stdout=subprocess.PIPE,

        stderr=subprocess.PIPE,

        text=True,

        timeout=900
    )

    return result


# =========================================================
# CONVERSION
# =========================================================

@app.route("/api/convert", methods=["POST"])
def convert_media():

    temp_dir = None

    try:

        # -------------------------------------------------
        # FILE
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


        # -------------------------------------------------
        # INPUT FORMAT
        # -------------------------------------------------

        if not allowed_input_file(
            uploaded_file.filename
        ):

            return jsonify({

                "success": False,

                "error":
                    "Unsupported input file format."
            }), 400


        # -------------------------------------------------
        # OUTPUT FORMAT
        # -------------------------------------------------

        output_format = (
            request.form.get("format")
            or request.form.get("output_format")
            or ""
        ).strip().lower()


        if output_format not in ALLOWED_OUTPUT_FORMATS:

            return jsonify({

                "success": False,

                "error":
                    "Unsupported output format."
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

        uploaded_file.save(
            input_path
        )


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
        # AUDIO
        # =================================================

        if output_format in {
            "mp3",
            "wav",
            "m4a"
        }:

            command = build_audio_command(

                input_path,

                output_path,

                output_format
            )


        # =================================================
        # VIDEO
        # =================================================

        else:

            command = build_video_command(

                input_path,

                output_path,

                output_format
            )


        # -------------------------------------------------
        # RUN
        # -------------------------------------------------

        result = run_ffmpeg(
            command
        )


        # -------------------------------------------------
        # FAILED
        # -------------------------------------------------

        if result.returncode != 0:

            error_text = (
                result.stderr.strip()
                or "FFmpeg conversion failed."
            )


            return jsonify({

                "success": False,

                "error":
                    "Conversion failed.",

                "details":
                    error_text[-8000:]
            }), 500


        # -------------------------------------------------
        # OUTPUT CHECK
        # -------------------------------------------------

        if not os.path.isfile(
            output_path
        ):

            return jsonify({

                "success": False,

                "error":
                    "FFmpeg completed but output file was not created."
            }), 500


        if os.path.getsize(
            output_path
        ) == 0:

            return jsonify({

                "success": False,

                "error":
                    "The converted file is empty."
            }), 500


        # -------------------------------------------------
        # SEND FILE
        # -------------------------------------------------

        response = send_file(

            output_path,

            mimetype=get_mimetype(
                output_format
            ),

            as_attachment=True,

            download_name=output_filename,

            conditional=False
        )


        response.headers[
            "Cache-Control"
        ] = "no-store"

        response.headers[
            "Pragma"
        ] = "no-cache"

        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"


        return response


    # =====================================================
    # TIMEOUT
    # =====================================================

    except subprocess.TimeoutExpired:

        return jsonify({

            "success": False,

            "error":
                "Conversion timed out. Try a smaller or shorter video."
        }), 500


    # =====================================================
    # OTHER ERROR
    # =====================================================

    except Exception as e:

        return jsonify({

            "success": False,

            "error":
                str(e)
        }), 500


    # =====================================================
    # CLEANUP
    # =====================================================

    finally:

        # Do not delete the temporary directory here.
        #
        # send_file() may still be reading the output.
        #
        # Render will clean temporary files when the
        # instance restarts. The files are also isolated
        # per request.

        pass


# =========================================================
# FILE TOO LARGE
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({

        "success": False,

        "error":
            "File is too large. Maximum allowed size is 500 MB."
    }), 413


# =========================================================
# NOT FOUND
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return jsonify({

        "success": False,

        "error":
            "Page not found."
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
