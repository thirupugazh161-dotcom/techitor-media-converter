@app.route("/progress")
def progress():

    try:

        job_id = request.args.get("id")

        if not job_id:

            return jsonify({
                "status": "error",
                "error": "Job ID is missing"
            }), 400


        if job_id not in jobs:

            return jsonify({
                "status": "error",
                "error": "Job not found"
            }), 404


        job = jobs.get(job_id)


        if not isinstance(job, dict):

            return jsonify({
                "status": "error",
                "error": "Invalid job data"
            }), 500


        return jsonify({
            "status": job.get(
                "status",
                "starting"
            ),

            "progress": float(
                job.get("progress", 0)
            ),

            "message": job.get(
                "message",
                ""
            ),

            "error": job.get(
                "error",
                ""
            ),

            "download_url": job.get(
                "download_url",
                ""
            )
        })


    except Exception as e:

        print(
            "PROGRESS ERROR:",
            str(e)
        )


        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
