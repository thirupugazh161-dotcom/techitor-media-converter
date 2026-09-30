import os
import shutil
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

# Maximum upload size: 500 MB
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


# =========================================================
# FFMPEG
# =========================================================

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


# =========================================================
# OUTPUT FORMATS
# =========================================================
# Input extensions are deliberately NOT restricted.
# FFmpeg identifies the real input format from the file itself.
# This allows many video formats/codecs to be converted even
# when the extension is not in a fixed whitelist.

ALLOWED_OUTPUT_FORMATS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm",
}

AUDIO_OUTPUT_FORMATS = {"mp3", "wav", "m4a"}
VIDEO_OUTPUT_FORMATS = {"mp4", "mov", "mkv", "webm"}


# =========================================================
# HELPERS
# =========================================================

def get_extension(filename):
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


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
    return mimetypes.get(extension, "application/octet-stream")


def cleanup_directory(path):
    if path and os.path.isdir(path):
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


# =========================================================
# STATIC FILES
# =========================================================

@app.route("/<path:filename>")
def static_files(filename):
    requested_path = os.path.join(BASE_DIR, filename)

    if os.path.isfile(requested_path):
        return send_from_directory(BASE_DIR, filename)

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

def build_video_command(input_path, output_path, output_format):

    # Common input/output setup.
    #
    # IMPORTANT:
    # - We do NOT rely on the input extension.
    # - We map the first video stream.
    # - Audio is optional, so silent videos also work.
    # - Subtitles/data streams are ignored.
    command = [
        FFMPEG_PATH,
        "-y",
        "-hide_banner",
        "-loglevel", "error",

        # Keep Render memory/CPU usage under control.
        "-threads", "1",

        "-i", input_path,

        "-map", "0:v:0",
        "-map", "0:a:0?",

        "-sn",
        "-dn",

        # Make dimensions even for broad codec compatibility.
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",

        # Avoid muxing queue problems on difficult inputs.
        "-max_muxing_queue_size", "1024",
    ]

    # =====================================================
    # MP4
    # =====================================================

    if output_format == "mp4":
        command += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-pix_fmt", "yuv420p",

            # MP4-compatible audio
            "-c:a", "aac",
            "-b:a", "128k",

            "-movflags", "+faststart",
            "-f", "mp4",
        ]

    # =====================================================
    # MOV
    # =====================================================

    elif output_format == "mov":
        command += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-pix_fmt", "yuv420p",

            "-c:a", "aac",
            "-b:a", "128k",

            "-f", "mov",
        ]

    # =====================================================
    # MKV
    # =====================================================

    elif output_format == "mkv":
        command += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-pix_fmt", "yuv420p",

            # AAC is supported inside Matroska.
            "-c:a", "aac",
            "-b:a", "128k",

            "-f", "matroska",
        ]

    # =====================================================
    # WEBM
    # =====================================================

    elif output_format == "webm":
        # THIS IS THE IMPORTANT FIX.
        #
        # WebM must use a WebM-compatible audio codec.
        # AAC is NOT a valid WebM audio codec.
        #
        # Use VP8 + Opus for maximum compatibility and
        # relatively low CPU usage on Render.
        command += [
            "-c:v", "libvpx",
            "-deadline", "realtime",
            "-cpu-used", "8",
            "-crf", "32",
            "-b:v", "1M",
            "-pix_fmt", "yuv420p",

            # WebM-compatible audio
            "-c:a", "libopus",
            "-b:a", "96k",
            "-ar", "48000",

            "-f", "webm",
        ]

    else:
        raise ValueError("Unsupported video output format.")

    command.append(output_path)
    return command


# =========================================================
# BUILD AUDIO COMMAND
# =========================================================

def build_audio_command(input_path, output_path, output_format):

    command = [
        FFMPEG_PATH,
        "-y",
        "-hide_banner",
        "-loglevel", "error",

        "-threads", "1",

        "-i", input_path,

        # First audio stream. If there is no audio stream,
        # FFmpeg will return a clear conversion error.
        "-map", "0:a:0",

        "-vn",
        "-sn",
        "-dn",
    ]

    if output_format == "mp3":
        command += [
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            "-f", "mp3",
        ]

    elif output_format == "wav":
        command += [
            "-c:a", "pcm_s16le",
            "-f", "wav",
        ]

    elif output_format == "m4a":
        command += [
            "-c:a", "aac",
            "-b:a", "192k",
            "-f", "ipod",
        ]

    else:
        raise ValueError("Unsupported audio output format.")

    command.append(output_path)
    return command


# =========================================================
# RUN FFMPEG
# =========================================================

def run_ffmpeg(command):
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=900
    )


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
        # OUTPUT FORMAT
        # -------------------------------------------------
        # Accept both names so the existing frontend can use
        # either "format" or "output_format".

        output_format = (
            request.form.get("format")
            or request.form.get("output_format")
            or ""
        ).strip().lower()

        if output_format not in ALLOWED_OUTPUT_FORMATS:
            return jsonify({
                "success": False,
                "error": "Unsupported output format."
            }), 400

        # -------------------------------------------------
        # TEMP DIRECTORY
        # -------------------------------------------------

        temp_dir = tempfile.mkdtemp(prefix="techitor_")

        # -------------------------------------------------
        # INPUT FILE
        # -------------------------------------------------

        original_name = secure_filename(uploaded_file.filename)

        if not original_name:
            cleanup_directory(temp_dir)
            temp_dir = None

            return jsonify({
                "success": False,
                "error": "Invalid file name."
            }), 400

        input_path = os.path.join(temp_dir, original_name)

        uploaded_file.save(input_path)

        if not os.path.isfile(input_path):
            cleanup_directory(temp_dir)
            temp_dir = None

            return jsonify({
                "success": False,
                "error": "Uploaded file could not be saved."
            }), 500

        if os.path.getsize(input_path) == 0:
            cleanup_directory(temp_dir)
            temp_dir = None

            return jsonify({
                "success": False,
                "error": "Uploaded file is empty."
            }), 400

        # -------------------------------------------------
        # OUTPUT FILE
        # -------------------------------------------------

        base_name = os.path.splitext(original_name)[0]

        output_filename = (
            f"{base_name}_converted.{output_format}"
        )

        output_path = os.path.join(
            temp_dir,
            output_filename
        )

        # -------------------------------------------------
        # BUILD COMMAND
        # -------------------------------------------------

        if output_format in AUDIO_OUTPUT_FORMATS:
            command = build_audio_command(
                input_path,
                output_path,
                output_format
            )

        elif output_format in VIDEO_OUTPUT_FORMATS:
            command = build_video_command(
                input_path,
                output_path,
                output_format
            )

        else:
            raise ValueError("Unsupported output format.")

        # -------------------------------------------------
        # RUN FFMPEG
        # -------------------------------------------------

        result = run_ffmpeg(command)

        # -------------------------------------------------
        # FAILED
        # -------------------------------------------------

        if result.returncode != 0:

            error_text = (
                result.stderr.strip()
                or result.stdout.strip()
                or "FFmpeg conversion failed."
            )

            cleanup_directory(temp_dir)
            temp_dir = None

            return jsonify({
                "success": False,
                "error": "Conversion failed.",
                "details": error_text[-8000:]
            }), 500

        # -------------------------------------------------
        # OUTPUT CHECK
        # -------------------------------------------------

        if not os.path.isfile(output_path):
            cleanup_directory(temp_dir)
            temp_dir = None

            return jsonify({
                "success": False,
                "error": "FFmpeg completed but output file was not created."
            }), 500

        output_size = os.path.getsize(output_path)

        if output_size == 0:
            cleanup_directory(temp_dir)
            temp_dir = None

            return jsonify({
                "success": False,
                "error": "The converted file is empty."
            }), 500

        # -------------------------------------------------
        # SEND FILE
        # -------------------------------------------------

        response = send_file(
            output_path,
            mimetype=get_mimetype(output_format),
            as_attachment=True,
            download_name=output_filename,
            conditional=False
        )

        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"

        # IMPORTANT:
        # Do not delete the output before send_file has finished
        # sending it to the browser.
        #
        # Flask executes this callback after the response is closed.
        response.call_on_close(
            lambda path=temp_dir: cleanup_directory(path)
        )

        # Ownership of temp_dir is now with the response callback.
        temp_dir = None

        return response

    # =====================================================
    # TIMEOUT
    # =====================================================

    except subprocess.TimeoutExpired:
        cleanup_directory(temp_dir)
        temp_dir = None

        return jsonify({
            "success": False,
            "error":
                "Conversion timed out. Try a smaller or shorter video."
        }), 500

    # =====================================================
    # OTHER ERROR
    # =====================================================

    except Exception as e:
        cleanup_directory(temp_dir)
        temp_dir = None

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    finally:
        # If an error occurred before send_file took ownership,
        # remove the temporary directory.
        if temp_dir:
            cleanup_directory(temp_dir)


# =========================================================
# FILE TOO LARGE
# =========================================================

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "success": False,
        "error": "File is too large. Maximum allowed size is 500 MB."
    }), 413


# =========================================================
# NOT FOUND
# =========================================================

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
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
