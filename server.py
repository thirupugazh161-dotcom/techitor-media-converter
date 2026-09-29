import os
import subprocess
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return send_file(os.path.join(os.path.dirname(__file__), "index.html"))

@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    input_file = "input_media"
    output_file = "output.mp4"

    file.save(input_file)

    try:
        subprocess.run([
            "ffmpeg",
            "-i", input_file,
            "-y",
            output_file
        ], check=True)

        return send_file(
            output_file,
            as_attachment=True,
            download_name="converted.mp4"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if os.path.exists(input_file):
            os.remove(input_file)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
