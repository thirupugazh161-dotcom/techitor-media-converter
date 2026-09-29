import os
import subprocess
from flask import Flask, request, send_file, send_from_directory, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)


# =========================
# HOME PAGE
# =========================
@app.route("/")
def home():
    return send_file(os.path.join(BASE_DIR, "index.html"))


# =========================
# FRONTEND FILES
# CSS / JS / PNG / IMAGES
# =========================
@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(BASE_DIR, filename)


# =========================
# MEDIA CONVERTER
# =========================
@app.route("/convert", methods=["POST"])
def convert():

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    input_file = os.path.join(BASE_DIR, "input_media")
    output_file = os.path.join(BASE_DIR, "output.mp4")

    file.save(input_file)

    try:

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                input_file,
                "-y",
                output_file
            ],
            check=True
        )

        return send_file(
            output_file,
            as_attachment=True,
            download_name="converted.mp4"
        )

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

    finally:

        if os.path.exists(input_file):
            os.remove(input_file)


# =========================
# START SERVER
# =========================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
