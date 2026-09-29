import os
import sys
import uuid
import shutil
import subprocess
import tempfile
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from email.parser import BytesParser
from email.policy import default

# =========================================================
# TECHITOR'S MEDIA CONVERTER
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FFMPEG = os.path.join(BASE_DIR, "ffmpeg.exe")

HOST = "127.0.0.1"
PORT = 8000

WEBSITE_PATH = "/techitor-media-encoder"

ALLOWED_FORMATS = {
    "mp3",
    "wav",
    "m4a",
    "mp4",
    "mov",
    "mkv",
    "webm",
}


def send_bytes(handler, data, content_type="text/plain; charset=utf-8", status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def get_extension(filename):
    return os.path.splitext(filename)[1].lower().lstrip(".")


class MediaConverterHandler(BaseHTTPRequestHandler):

    server_version = "TechitorMediaConverter/1.0"

    def log_message(self, format, *args):
        print("%s - %s" % (self.client_address[0], format % args))

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    def do_GET(self):

        parsed = urlparse(self.path)
        path = parsed.path

        # Main website
        if path in ("/", WEBSITE_PATH, WEBSITE_PATH + "/"):
            self.serve_file("index.html", "text/html; charset=utf-8")
            return

        # CSS
        if path == "/style.css":
            self.serve_file("style.css", "text/css; charset=utf-8")
            return

        # JavaScript
        if path == "/script.js":
            self.serve_file("script.js", "application/javascript; charset=utf-8")
            return

        # Techitor logo
        if path == "/techitor-logo.png":
            self.serve_file("techitor-logo.png", "image/png")
            return

        # Support QR
        if path == "/support-qr.png":
            self.serve_file("support-qr.png", "image/png")
            return

        # Favicon - don't show unnecessary 404
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        self.send_error(404, "File not found")

    # -----------------------------------------------------
    # POST /convert
    # -----------------------------------------------------

    def do_POST(self):

        parsed = urlparse(self.path)

        if parsed.path != "/convert":
            self.send_error(404, "Endpoint not found")
            return

        try:
            content_type = self.headers.get("Content-Type", "")

            if "multipart/form-data" not in content_type:
                self.send_error(400, "Expected multipart/form-data")
                return

            content_length = int(self.headers.get("Content-Length", "0"))

            if content_length <= 0:
                self.send_error(400, "No file received")
                return

            print()
            print("=" * 55)
            print("NEW CONVERSION")
            print("=" * 55)

            # Read uploaded form
            body = self.rfile.read(content_length)

            # Build a MIME message so Python can parse FormData
            header = (
                "Content-Type: "
                + content_type
                + "\r\nMIME-Version: 1.0\r\n\r\n"
            ).encode("utf-8")

            message = BytesParser(policy=default).parsebytes(header + body)

            uploaded_file = None
            output_format = None

            if message.is_multipart():

                for part in message.iter_parts():

                    disposition = part.get("Content-Disposition", "")

                    filename = part.get_filename()

                    if filename:
                        uploaded_file = (
                            filename,
                            part.get_payload(decode=True)
                        )

                    if "name=\"format\"" in disposition:
                        payload = part.get_payload(decode=True)

                        if payload:
                            output_format = payload.decode(
                                "utf-8",
                                errors="ignore"
                            ).strip().lower()

                    if "name=\"outputFormat\"" in disposition:
                        payload = part.get_payload(decode=True)

                        if payload:
                            output_format = payload.decode(
                                "utf-8",
                                errors="ignore"
                            ).strip().lower()

            if not uploaded_file:
                self.send_error(400, "No media file received")
                return

            original_name, file_data = uploaded_file

            if not file_data:
                self.send_error(400, "Uploaded file is empty")
                return

            # Default output format
            if not output_format:
                output_format = "mp4"

            output_format = output_format.lower().replace(".", "")

            if output_format not in ALLOWED_FORMATS:
                self.send_error(
                    400,
                    "Unsupported output format: " + output_format
                )
                return

            # -------------------------------------------------
            # Temporary working directory
            # -------------------------------------------------

            work_dir = tempfile.mkdtemp(prefix="techitor_converter_")

            try:

                safe_input_name = os.path.basename(original_name)

                input_path = os.path.join(
                    work_dir,
                    safe_input_name
                )

                output_name = (
                    os.path.splitext(safe_input_name)[0]
                    + "_converted."
                    + output_format
                )

                output_path = os.path.join(
                    work_dir,
                    output_name
                )

                with open(input_path, "wb") as f:
                    f.write(file_data)

                print("Input file :", original_name)
                print("Input size :", round(len(file_data) / (1024 * 1024), 2), "MB")
                print("Output     :", output_format.upper())
                print()
                print("Converting...")

                # -------------------------------------------------
                # FFmpeg
                # -------------------------------------------------

                command = [
                    FFMPEG,
                    "-y",
                    "-i",
                    input_path,
                    output_path
                ]

                process = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )

                if process.returncode != 0:

                    print()
                    print("FFmpeg ERROR:")
                    print(process.stderr)

                    self.send_error(
                        500,
                        "FFmpeg conversion failed"
                    )
                    return

                if not os.path.exists(output_path):
                    self.send_error(
                        500,
                        "Output file was not created"
                    )
                    return

                output_size = os.path.getsize(output_path)

                print()
                print("Conversion completed successfully!")
                print(
                    "Output size :",
                    round(output_size / (1024 * 1024), 2),
                    "MB"
                )
                print("=" * 55)
                print()

                # -------------------------------------------------
                # Send converted file
                # -------------------------------------------------

                mime_type = (
                    mimetypes.guess_type(output_path)[0]
                    or "application/octet-stream"
                )

                with open(output_path, "rb") as f:
                    converted_data = f.read()

                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    mime_type
                )

                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="' + output_name + '"'
                )

                self.send_header(
                    "Content-Length",
                    str(len(converted_data))
                )

                self.send_header(
                    "Cache-Control",
                    "no-cache"
                )

                self.end_headers()

                self.wfile.write(converted_data)

            finally:

                try:
                    shutil.rmtree(work_dir)
                except Exception:
                    pass

        except Exception as e:

            print()
            print("SERVER ERROR:")
            print(str(e))
            print()

            try:
                self.send_error(
                    500,
                    "Conversion server error"
                )
            except Exception:
                pass

    # -----------------------------------------------------
    # Serve static files
    # -----------------------------------------------------

    def serve_file(self, filename, content_type):

        file_path = os.path.join(BASE_DIR, filename)

        if not os.path.isfile(file_path):
            self.send_error(404, filename + " not found")
            return

        try:

            with open(file_path, "rb") as f:
                data = f.read()

            self.send_response(200)

            self.send_header(
                "Content-Type",
                content_type
            )

            self.send_header(
                "Content-Length",
                str(len(data))
            )

            self.send_header(
                "Cache-Control",
                "no-cache"
            )

            self.end_headers()

            self.wfile.write(data)

        except Exception as e:

            self.send_error(
                500,
                "Unable to read file"
            )


# =========================================================
# START SERVER
# =========================================================

def main():

    print()
    print("=" * 55)
    print("          TECHITOR'S MEDIA CONVERTER")
    print("=" * 55)
    print()
    print("Website:")
    print("http://localhost:8000/techitor-media-encoder")
    print()
    print("Server is running...")
    print("Keep this window open while using the converter.")
    print()
    print("=" * 55)
    print()

    if not os.path.exists(FFMPEG):

        print("ERROR: ffmpeg.exe not found!")
        print()
        print("Make sure ffmpeg.exe is inside this folder:")
        print(BASE_DIR)
        print()

        input("Press Enter to exit...")
        return

    server = ThreadingHTTPServer(
        (HOST, PORT),
        MediaConverterHandler
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print("Server stopped.")

    finally:
        server.server_close()


if __name__ == "__main__":
    main()