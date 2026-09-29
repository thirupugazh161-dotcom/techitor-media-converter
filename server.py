import os
import re
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
# APP
# =========================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

TEMP_DIR = os.path.join(
    BASE_DIR,
    "temp"
)

os.makedirs(
    TEMP_DIR,
    exist_ok=True
)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

jobs = {}


# =========================================================
# STATIC FILES
# =========================================================

@app.route("/style.css")
def style_css():

    return send_from_directory(
        BASE_DIR,
        "style.css"
    )


@app.route("/script.js")
def script_js():

    return send_from_directory(
        BASE_DIR,
        "script.js"
    )


@app.route("/techitor-logo.png")
def techitor_logo():

    return send_from_directory(
        BASE_DIR,
        "techitor-logo.png"
    )


@app.route("/support-qr.png")
def support_qr():

    return send_from_directory(
        BASE_DIR,
        "support-qr.png"
    )


# =========================================================
# GET MEDIA DURATION
# =========================================================

def get_duration(input_file):

    try:

        result = subprocess.run(
            [
                FFMPEG,
                "-hide_banner",
                "-i",
                input_file
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )

        match = re.search(
            r"Duration:\s*(\d+):(\d+):([\d.]+)",
            result.stderr
        )

        if match:

            hours = int(
                match.group(1)
            )

            minutes = int(
                match.group(2)
            )

            seconds = float(
                match.group(3)
            )

            return (
                hours * 3600
                + minutes * 60
                + seconds
            )

    except Exception:

        pass

    return 0


# =========================================================
# CONVERSION
# =========================================================

def run_conversion(
    job_id,
    input_file,
    output_file,
    output_format
):

    jobs[job_id].update({
        "status": "converting",
        "progress": 0,
        "message": "Starting conversion..."
    })


    # -----------------------------------------------------
    # GET DURATION
    # -----------------------------------------------------

    duration = get_duration(
        input_file
    )


    # -----------------------------------------------------
    # BASE FFMPEG COMMAND
    # -----------------------------------------------------

    command = [
        FFMPEG,
        "-y",
        "-hide_banner",
        "-i",
        input_file
    ]


    # -----------------------------------------------------
    # OUTPUT SETTINGS
    # -----------------------------------------------------

    if output_format == "mp3":

        command += [
            "-vn",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k"
        ]


    elif output_format == "wav":

        command += [
            "-vn",
            "-c:a",
            "pcm_s16le"
        ]


    elif output_format == "m4a":

        command += [
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "192k"
        ]


    elif output_format == "mp4":

        command += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart"
        ]


    elif output_format == "mov":

        command += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k"
        ]


    elif output_format == "mkv":

        command += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k"
        ]


    elif output_format == "webm":

        command += [
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "30",
            "-b:v",
            "0",
            "-c:a",
            "libopus"
        ]


    # -----------------------------------------------------
    # PROGRESS OUTPUT
    # -----------------------------------------------------

    command += [
        "-progress",
        "pipe:1",
        "-nostats",
        output_file
    ]


    try:

        process = subprocess.Popen(

            command,

            stdout=subprocess.PIPE,

            stderr=subprocess.PIPE,

            text=True,

            bufsize=1
        )


        # -------------------------------------------------
        # READ STDERR IN SEPARATE THREAD
        # -------------------------------------------------

        stderr_lines = []


        def read_stderr():

            try:

                for line in process.stderr:

                    line = line.strip()

                    if line:

                        stderr_lines.append(
                            line
                        )

            except Exception:

                pass


        stderr_thread = threading.Thread(
            target=read_stderr,
            daemon=True
        )

        stderr_thread.start()


        # -------------------------------------------------
        # READ FFMPEG PROGRESS
        # -------------------------------------------------

        for line in process.stdout:

            line = line.strip()


            # FFmpeg progress time
            if line.startswith(
                "out_time_ms="
            ):

                try:

                    value = line.split(
                        "=",
                        1
                    )[1]

                    current_time = (
                        int(value)
                        / 1_000_000
                    )


                    if duration > 0:

                        progress = (
                            current_time
                            / duration
                        ) * 100


                        progress = max(
                            0,
                            min(
                                99.5,
                                progress
                            )
                        )


                        jobs[job_id][
                            "progress"
                        ] = round(
                            progress,
                            1
                        )


                        jobs[job_id][
                            "message"
                        ] = (
                            "Converting... "
                            + str(
                                round(
                                    progress,
                                    1
                                )
                            )
                            + "%"
                        )


                except Exception:

                    pass


            # FFmpeg reports end
            elif line == "progress=end":

                if duration > 0:

                    jobs[job_id][
                        "progress"
                    ] = 99.5


        # -------------------------------------------------
        # WAIT FOR FFMPEG
        # -------------------------------------------------

        process.wait()


        stderr_thread.join(
            timeout=2
        )


        # -------------------------------------------------
        # CHECK FAILURE
        # -------------------------------------------------

        if process.returncode != 0:

            error_text = "\n".join(
                stderr_lines
            )


            jobs[job_id].update({

                "status": "failed",

                "progress": 0,

                "message":
                    "Conversion failed.",

                "error":
                    error_text[-3000:]
            })

            return


        # -------------------------------------------------
        # CHECK OUTPUT
        # -------------------------------------------------

        if not os.path.exists(
            output_file
        ):

            jobs[job_id].update({

                "status": "failed",

                "progress": 0,

                "message":
                    "Output file was not created.",

                "error":
                    "FFmpeg finished but output file is missing."
            })

            return


        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        jobs[job_id].update({

            "status": "completed",

            "progress": 100,

            "message":
                "Conversion completed successfully!",

            "download_url":
                f"/download?id={job_id}"
        })


    except Exception as e:

        jobs[job_id].update({

            "status": "failed",

            "progress": 0,

            "message":
                "Conversion failed.",

            "error":
                str(e)
        })


    finally:

        # -------------------------------------------------
        # DELETE INPUT FILE
        # -------------------------------------------------

        if os.path.exists(
            input_file
        ):

            try:

                os.remove(
                    input_file
                )

            except Exception:

                pass


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return send_file(
        os.path.join(
            BASE_DIR,
            "index.html"
        )
    )


# =========================================================
# START CONVERSION
# =========================================================

@app.route(
    "/convert",
    methods=["POST"]
)
def convert():

    try:

        # -------------------------------------------------
        # CHECK FILE
        # -------------------------------------------------

        if "file" not in request.files:

            return jsonify({
                "error":
                    "No file uploaded"
            }), 400


        file = request.files["file"]


        if file.filename == "":

            return jsonify({
                "error":
                    "No file selected"
            }), 400


        # -------------------------------------------------
        # FORMAT
        # -------------------------------------------------

        output_format = request.form.get(
            "format",
            "mp3"
        ).lower()


        allowed_formats = [

            "mp3",
            "wav",
            "m4a",
            "mp4",
            "mov",
            "mkv",
            "webm"

        ]


        if output_format not in allowed_formats:

            return jsonify({
                "error":
                    "Unsupported format"
            }), 400


        # -------------------------------------------------
        # JOB ID
        # -------------------------------------------------

        job_id = uuid.uuid4().hex


        # -------------------------------------------------
        # FILE PATHS
        # -------------------------------------------------

        input_file = os.path.join(

            TEMP_DIR,

            f"{job_id}_input"
        )


        output_file = os.path.join(

            TEMP_DIR,

            f"{job_id}.{output_format}"
        )


        # -------------------------------------------------
        # SAVE UPLOADED FILE
        # -------------------------------------------------

        file.save(
            input_file
        )


        # -------------------------------------------------
        # CREATE JOB
        # -------------------------------------------------

        jobs[job_id] = {

            "status":
                "starting",

            "progress":
                0,

            "message":
                "Preparing conversion..."

        }


        # -------------------------------------------------
        # START BACKGROUND THREAD
        # -------------------------------------------------

        thread = threading.Thread(

            target=run_conversion,

            args=(

                job_id,

                input_file,

                output_file,

                output_format

            ),

            daemon=True

        )


        thread.start()


        # -------------------------------------------------
        # RETURN JSON
        # -------------------------------------------------

        return jsonify({

            "job_id":
                job_id,

            "status":
                "starting"

        })


    except Exception as e:

        return jsonify({

            "error":
                str(e)

        }), 500


# =========================================================
# PROGRESS
# =========================================================

@app.route(
    "/progress"
)
def progress():

    try:

        job_id = request.args.get(
            "id"
        )


        if not job_id:

            return jsonify({

                "error":
                    "Job ID missing"

            }), 400


        if job_id not in jobs:

            return jsonify({

                "error":
                    "Job not found"

            }), 404


        return jsonify(
            jobs[job_id]
        )


    except Exception as e:

        return jsonify({

            "error":
                str(e)

        }), 500


# =========================================================
# DOWNLOAD
# =========================================================

@app.route(
    "/download"
)
def download():

    try:

        job_id = request.args.get(
            "id"
        )


        if not job_id:

            return jsonify({

                "error":
                    "Job ID missing"

            }), 400


        if job_id not in jobs:

            return jsonify({

                "error":
                    "Job not found"

            }), 404


        job = jobs[job_id]


        # -------------------------------------------------
        # CHECK COMPLETION
        # -------------------------------------------------

        if job.get(
            "status"
        ) != "completed":

            return jsonify({

                "error":
                    "Conversion not completed"

            }), 400


        # -------------------------------------------------
        # FIND OUTPUT FILE
        # -------------------------------------------------

        matching_files = [

            filename

            for filename in os.listdir(
                TEMP_DIR
            )

            if filename.startswith(
                job_id + "."
            )

        ]


        if not matching_files:

            return jsonify({

                "error":
                    "Output file not found"

            }), 404


        filename = matching_files[0]


        output_file = os.path.join(

            TEMP_DIR,

            filename

        )


        # -------------------------------------------------
        # SEND FILE
        # -------------------------------------------------

        return send_file(

            output_file,

            as_attachment=True,

            download_name=filename

        )


    except Exception as e:

        return jsonify({

            "error":
                str(e)

        }), 500


# =========================================================
# SERVER
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

        threaded=True

    )
