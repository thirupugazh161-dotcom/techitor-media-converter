elif output_format == "webm":
    command += [
        "-c:v", "libvpx-vp9",
        "-b:v", "0",
        "-crf", "32",
        "-c:a", "libopus",
        "-b:a", "128k",
    ]

elif output_format == "mp4":
    command += [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
    ]

elif output_format == "mov":
    command += [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
    ]

elif output_format == "mkv":
    command += [
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
    ]
