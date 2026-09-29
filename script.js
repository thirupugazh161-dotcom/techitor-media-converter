// ============================================================
// TECHITOR MEDIA CONVERTER - FRONTEND SCRIPT
// ============================================================


// ------------------------------------------------------------
// ELEMENTS
// ------------------------------------------------------------

const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const dropZone = document.getElementById("dropZone");

const fileSection = document.getElementById("fileSection");
const fileName = document.getElementById("fileName");
const fileSize = document.getElementById("fileSize");

const removeBtn = document.getElementById("removeBtn");
const formatSelect = document.getElementById("formatSelect");
const convertBtn = document.getElementById("convertBtn");

const progressSection = document.getElementById("progressSection");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const progressPercent = document.getElementById("progressPercent");
const timeRemaining = document.getElementById("timeRemaining");

const downloadSection = document.getElementById("downloadSection");
const downloadBtn = document.getElementById("downloadBtn");


// ------------------------------------------------------------
// VARIABLES
// ------------------------------------------------------------

let selectedFile = null;
let currentJobId = null;
let progressTimer = null;


// ------------------------------------------------------------
// SAFETY CHECK
// ------------------------------------------------------------

console.log("Techitor Media Converter JS loaded");


// ------------------------------------------------------------
// BROWSE FILE
// ------------------------------------------------------------

if (browseBtn && fileInput) {

    browseBtn.addEventListener("click", function () {

        fileInput.click();

    });

}


// ------------------------------------------------------------
// FILE INPUT CHANGE
// ------------------------------------------------------------

if (fileInput) {

    fileInput.addEventListener("change", function () {

        if (!fileInput.files || fileInput.files.length === 0) {
            return;
        }

        selectFile(fileInput.files[0]);

    });

}


// ------------------------------------------------------------
// SELECT FILE
// ------------------------------------------------------------

function selectFile(file) {

    if (!file) {
        return;
    }

    selectedFile = file;

    console.log("Selected file:", file.name);


    // File name

    if (fileName) {
        fileName.textContent = file.name;
    }


    // File size

    const sizeMB = file.size / (1024 * 1024);

    if (fileSize) {

        if (sizeMB < 1) {

            const sizeKB = file.size / 1024;

            fileSize.textContent =
                sizeKB.toFixed(2) + " KB";

        } else {

            fileSize.textContent =
                sizeMB.toFixed(2) + " MB";

        }

    }


    // Show file section

    if (fileSection) {
        fileSection.classList.remove("hidden");
    }


    // Hide old result

    if (progressSection) {
        progressSection.classList.add("hidden");
    }

    if (downloadSection) {
        downloadSection.classList.add("hidden");
    }


    // Reset progress

    resetProgress();

}


// ------------------------------------------------------------
// RESET PROGRESS
// ------------------------------------------------------------

function resetProgress() {

    if (progressFill) {
        progressFill.style.width = "0%";
    }

    if (progressPercent) {
        progressPercent.textContent = "0%";
    }

    if (progressText) {
        progressText.textContent = "Ready to convert";
    }

    if (timeRemaining) {
        timeRemaining.textContent = "Ready";
    }

}


// ------------------------------------------------------------
// DRAG OVER
// ------------------------------------------------------------

if (dropZone) {

    dropZone.addEventListener("dragover", function (event) {

        event.preventDefault();

        dropZone.style.borderColor = "#1677ff";

    });


    // --------------------------------------------------------
    // DRAG LEAVE
    // --------------------------------------------------------

    dropZone.addEventListener("dragleave", function () {

        dropZone.style.borderColor = "#46506a";

    });


    // --------------------------------------------------------
    // DROP
    // --------------------------------------------------------

    dropZone.addEventListener("drop", function (event) {

        event.preventDefault();

        dropZone.style.borderColor = "#46506a";


        const files = event.dataTransfer.files;


        if (!files || files.length === 0) {
            return;
        }


        selectFile(files[0]);

    });

}


// ------------------------------------------------------------
// REMOVE FILE
// ------------------------------------------------------------

if (removeBtn) {

    removeBtn.addEventListener("click", function () {

        selectedFile = null;
        currentJobId = null;


        // Stop progress polling

        if (progressTimer) {

            clearTimeout(progressTimer);

            progressTimer = null;

        }


        // Reset input

        if (fileInput) {
            fileInput.value = "";
        }


        // Hide sections

        if (fileSection) {
            fileSection.classList.add("hidden");
        }

        if (progressSection) {
            progressSection.classList.add("hidden");
        }

        if (downloadSection) {
            downloadSection.classList.add("hidden");
        }


        resetProgress();

    });

}


// ------------------------------------------------------------
// CONVERT BUTTON
// ------------------------------------------------------------

if (convertBtn) {

    convertBtn.addEventListener("click", async function () {

        // ----------------------------------------------------
        // CHECK FILE
        // ----------------------------------------------------

        if (!selectedFile) {

            alert("Please select a file first.");

            return;

        }


        // ----------------------------------------------------
        // GET FORMAT
        // ----------------------------------------------------

        const format =
            formatSelect
                ? formatSelect.value.toLowerCase()
                : "mp3";


        console.log("Starting conversion");
        console.log("File:", selectedFile.name);
        console.log("Format:", format);


        // ----------------------------------------------------
        // CREATE FORM DATA
        // ----------------------------------------------------

        const formData = new FormData();

        formData.append(
            "file",
            selectedFile
        );

        formData.append(
            "format",
            format
        );


        // ----------------------------------------------------
        // BUTTON STATE
        // ----------------------------------------------------

        convertBtn.disabled = true;

        convertBtn.textContent = "Starting...";


        // ----------------------------------------------------
        // SHOW PROGRESS
        // ----------------------------------------------------

        if (progressSection) {
            progressSection.classList.remove("hidden");
        }

        if (downloadSection) {
            downloadSection.classList.add("hidden");
        }


        if (progressFill) {
            progressFill.style.width = "0%";
        }

        if (progressPercent) {
            progressPercent.textContent = "0%";
        }

        if (progressText) {
            progressText.textContent =
                "Preparing conversion...";
        }

        if (timeRemaining) {
            timeRemaining.textContent =
                "Please wait...";
        }


        // ----------------------------------------------------
        // STOP OLD TIMER
        // ----------------------------------------------------

        if (progressTimer) {

            clearTimeout(progressTimer);

            progressTimer = null;

        }


        try {

            // ------------------------------------------------
            // SEND FILE TO SERVER
            // ------------------------------------------------

            const response = await fetch(
                "/convert",
                {
                    method: "POST",
                    body: formData
                }
            );


            console.log(
                "Convert response status:",
                response.status
            );


            // ------------------------------------------------
            // READ RESPONSE
            // ------------------------------------------------

            const responseText =
                await response.text();


            console.log(
                "Convert response:",
                responseText
            );


            let result;


            try {

                result =
                    JSON.parse(responseText);

            } catch (jsonError) {

                throw new Error(
                    "Server returned an invalid response."
                );

            }


            // ------------------------------------------------
            // SERVER ERROR
            // ------------------------------------------------

            if (!response.ok) {

                throw new Error(
                    result.error ||
                    result.message ||
                    "Unable to start conversion."
                );

            }


            // ------------------------------------------------
            // GET JOB ID
            // ------------------------------------------------

            const jobId =
                result.job_id ||
                result.id ||
                result.jobId;


            if (!jobId) {

                throw new Error(
                    "Server did not return a job ID."
                );

            }


            currentJobId = jobId;


            console.log(
                "Conversion Job ID:",
                currentJobId
            );


            // ------------------------------------------------
            // START PROGRESS CHECK
            // ------------------------------------------------

            if (progressText) {
                progressText.textContent =
                    "Conversion started...";
            }


            checkProgress(currentJobId);


        } catch (error) {

            console.error(
                "Conversion error:",
                error
            );


            showConversionError(
                error.message ||
                "Conversion failed."
            );

        }

    });

}


// ============================================================
// CHECK PROGRESS
// ============================================================

async function checkProgress(jobId) {

    if (!jobId) {

        showConversionError(
            "Invalid conversion job ID."
        );

        return;

    }


    try {

        console.log(
            "Checking progress:",
            jobId
        );


        // ----------------------------------------------------
        // REQUEST PROGRESS
        // ----------------------------------------------------

        const response = await fetch(
            "/progress?id=" +
            encodeURIComponent(jobId),
            {
                method: "GET",
                cache: "no-store"
            }
        );


        console.log(
            "Progress HTTP status:",
            response.status
        );


        // ----------------------------------------------------
        // READ RESPONSE AS TEXT FIRST
        // ----------------------------------------------------

        const responseText =
            await response.text();


        console.log(
            "Progress response:",
            responseText
        );


        // ----------------------------------------------------
        // EMPTY RESPONSE
        // ----------------------------------------------------

        if (!responseText || !responseText.trim()) {

            throw new Error(
                "Server returned an empty progress response."
            );

        }


        // ----------------------------------------------------
        // PARSE JSON
        // ----------------------------------------------------

        let data;


        try {

            data =
                JSON.parse(responseText);

        } catch (jsonError) {

            console.error(
                "Invalid JSON from /progress:",
                responseText
            );


            throw new Error(
                "Server returned an invalid progress response."
            );

        }


        // ----------------------------------------------------
        // HTTP ERROR
        // ----------------------------------------------------

        if (!response.ok) {

            throw new Error(
                data.error ||
                data.message ||
                "Unable to check conversion progress."
            );

        }


        // ----------------------------------------------------
        // NORMALIZE DATA
        // ----------------------------------------------------

        const status =
            String(
                data.status ||
                "starting"
            ).toLowerCase();


        let progress =
            Number(
                data.progress
            );


        // Invalid progress = 0

        if (
            Number.isNaN(progress) ||
            !Number.isFinite(progress)
        ) {

            progress = 0;

        }


        // Keep between 0 and 100

        progress =
            Math.max(
                0,
                Math.min(
                    100,
                    progress
                )
            );


        console.log(
            "Status:",
            status,
            "Progress:",
            progress
        );


        // ----------------------------------------------------
        // UPDATE PROGRESS BAR
        // ----------------------------------------------------

        if (progressFill) {

            progressFill.style.width =
                progress + "%";

        }


        if (progressPercent) {

            progressPercent.textContent =
                Math.round(progress) + "%";

        }


        // ====================================================
        // STARTING
        // ====================================================

        if (
            status === "starting" ||
            status === "queued" ||
            status === "pending"
        ) {

            if (progressText) {

                progressText.textContent =
                    "Preparing conversion...";

            }


            if (timeRemaining) {

                timeRemaining.textContent =
                    "Please wait...";

            }

        }


        // ====================================================
        // CONVERTING
        // ====================================================

        else if (
            status === "converting" ||
            status === "processing" ||
            status === "running"
        ) {

            if (progressText) {

                progressText.textContent =
                    "Converting...";

            }


            if (timeRemaining) {

                timeRemaining.textContent =
                    "Conversion in progress...";

            }

        }


        // ====================================================
        // COMPLETED
        // ====================================================

        else if (
            status === "completed" ||
            status === "complete" ||
            status === "success" ||
            status === "finished"
        ) {

            conversionCompleted(
                jobId,
                data
            );

            return;

        }


        // ====================================================
        // ERROR
        // ====================================================

        else if (
            status === "error" ||
            status === "failed" ||
            status === "failure"
        ) {

            throw new Error(
                data.error ||
                data.message ||
                "Conversion failed on the server."
            );

        }


        // ====================================================
        // CONTINUE POLLING
        // ====================================================

        progressTimer =
            setTimeout(
                function () {

                    checkProgress(jobId);

                },
                1000
            );


    } catch (error) {

        console.error(
            "Progress check error:",
            error
        );


        showConversionError(
            error.message ||
            "Unable to check conversion progress."
        );

    }

}


// ============================================================
// CONVERSION COMPLETED
// ============================================================

function conversionCompleted(jobId, data) {

    console.log(
        "Conversion completed:",
        data
    );


    // --------------------------------------------------------
    // PROGRESS = 100
    // --------------------------------------------------------

    if (progressFill) {

        progressFill.style.width =
            "100%";

    }


    if (progressPercent) {

        progressPercent.textContent =
            "100%";

    }


    // --------------------------------------------------------
    // STATUS TEXT
    // --------------------------------------------------------

    if (progressText) {

        progressText.textContent =
            "Conversion complete!";

    }


    if (timeRemaining) {

        timeRemaining.textContent =
            "Your file is ready.";

    }


    // --------------------------------------------------------
    // BUTTON
    // --------------------------------------------------------

    if (convertBtn) {

        convertBtn.disabled = false;

        convertBtn.textContent =
            "Convert Again";

    }


    // --------------------------------------------------------
    // SHOW DOWNLOAD
    // --------------------------------------------------------

    if (downloadSection) {

        downloadSection.classList.remove(
            "hidden"
        );

    }


    // --------------------------------------------------------
    // DOWNLOAD URL
    // --------------------------------------------------------

    if (downloadBtn) {

        downloadBtn.href =
            "/download?id=" +
            encodeURIComponent(jobId);


        // ----------------------------------------------------
        // FILENAME
        // ----------------------------------------------------

        let filename =
            data.filename ||
            data.file_name ||
            data.output_filename;


        if (!filename) {

            filename =
                "converted-file";

        }


        downloadBtn.download =
            filename;

    }


    currentJobId = null;

}


// ============================================================
// SHOW ERROR
// ============================================================

function showConversionError(message) {

    console.error(
        "FINAL ERROR:",
        message
    );


    if (progressText) {

        progressText.textContent =
            "Conversion failed.";

    }


    if (timeRemaining) {

        timeRemaining.textContent =
            message;

    }


    if (progressFill) {

        progressFill.style.width =
            "0%";

    }


    if (progressPercent) {

        progressPercent.textContent =
            "0%";

    }


    if (convertBtn) {

        convertBtn.disabled = false;

        convertBtn.textContent =
            "Convert";

    }


    // Don't hide progress section.
    // User can see the actual error.


}


// ============================================================
// PAGE CLEANUP
// ============================================================

window.addEventListener(
    "beforeunload",
    function () {

        if (progressTimer) {

            clearTimeout(progressTimer);

        }

    }
);
