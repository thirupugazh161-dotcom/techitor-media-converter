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

let selectedFile = null;
let currentJobId = null;
let progressTimer = null;


// =====================================================
// BROWSE
// =====================================================

browseBtn.addEventListener("click", () => {
    fileInput.click();
});


// =====================================================
// FILE INPUT
// =====================================================

fileInput.addEventListener("change", () => {

    if (fileInput.files.length > 0) {
        selectFile(fileInput.files[0]);
    }

});


// =====================================================
// SELECT FILE
// =====================================================

function selectFile(file) {

    selectedFile = file;

    fileName.textContent = file.name;

    const sizeMB = file.size / (1024 * 1024);

    fileSize.textContent =
        sizeMB < 1
            ? `${(file.size / 1024).toFixed(1)} KB`
            : `${sizeMB.toFixed(2)} MB`;

    fileSection.classList.remove("hidden");

    progressSection.classList.add("hidden");
    downloadSection.classList.add("hidden");

    progressFill.style.width = "0%";
    progressPercent.textContent = "0%";

    progressText.textContent =
        "Ready to convert";

    timeRemaining.textContent =
        "Select the output format and click Convert.";

    convertBtn.disabled = false;
    convertBtn.textContent = "Convert";

    currentJobId = null;
}


// =====================================================
// DRAG OVER
// =====================================================

dropZone.addEventListener("dragover", (event) => {

    event.preventDefault();

    dropZone.style.borderColor = "#1677ff";

});


// =====================================================
// DRAG LEAVE
// =====================================================

dropZone.addEventListener("dragleave", () => {

    dropZone.style.borderColor = "#46506a";

});


// =====================================================
// DROP
// =====================================================

dropZone.addEventListener("drop", (event) => {

    event.preventDefault();

    dropZone.style.borderColor = "#46506a";

    const files = event.dataTransfer.files;

    if (files.length > 0) {
        selectFile(files[0]);
    }

});


// =====================================================
// REMOVE FILE
// =====================================================

removeBtn.addEventListener("click", () => {

    selectedFile = null;
    currentJobId = null;

    if (progressTimer) {
        clearTimeout(progressTimer);
        progressTimer = null;
    }

    fileInput.value = "";

    fileSection.classList.add("hidden");
    progressSection.classList.add("hidden");
    downloadSection.classList.add("hidden");

    progressFill.style.width = "0%";
    progressPercent.textContent = "0%";

});


// =====================================================
// CONVERT
// =====================================================

convertBtn.addEventListener("click", async () => {

    if (!selectedFile) {

        alert("Please select a file first.");

        return;
    }

    const format = formatSelect.value;

    const formData = new FormData();

    formData.append("file", selectedFile);
    formData.append("format", format);

    convertBtn.disabled = true;
    convertBtn.textContent = "Uploading...";

    progressSection.classList.remove("hidden");
    downloadSection.classList.add("hidden");

    progressFill.style.width = "0%";
    progressPercent.textContent = "0%";

    progressText.textContent =
        "Uploading file...";

    timeRemaining.textContent =
        "Please wait...";

    try {

        const response = await fetch("/convert", {
            method: "POST",
            body: formData
        });

        const responseText = await response.text();

        let result;

        try {

            result = JSON.parse(responseText);

        } catch (error) {

            throw new Error(
                "Server returned an invalid response."
            );
        }

        if (!response.ok) {

            throw new Error(
                result.error ||
                "Unable to start conversion."
            );
        }

        if (!result.job_id) {

            throw new Error(
                "Server did not return a job ID."
            );
        }

        currentJobId = result.job_id;

        progressText.textContent =
            "Conversion started...";

        convertBtn.textContent =
            "Converting...";

        checkProgress(currentJobId);

    } catch (error) {

        console.error(error);

        showError(error.message);

    }

});


// =====================================================
// CHECK PROGRESS
// =====================================================

async function checkProgress(jobId) {

    if (!jobId) {
        return;
    }

    try {

        const response = await fetch(
            `/progress?id=${encodeURIComponent(jobId)}`,
            {
                method: "GET",
                cache: "no-store"
            }
        );

        const responseText = await response.text();

        let result;

        try {

            result = JSON.parse(responseText);

        } catch (error) {

            throw new Error(
                "Server returned an invalid progress response."
            );
        }

        if (!response.ok) {

            throw new Error(
                result.error ||
                "Unable to check conversion progress."
            );
        }

        // ---------------------------------------------
        // IMPORTANT: use result, NOT undefined data
        // ---------------------------------------------

        const progress =
            Math.max(
                0,
                Math.min(
                    100,
                    Number(result.progress) || 0
                )
            );

        progressFill.style.width =
            `${progress}%`;

        progressPercent.textContent =
            `${progress}%`;


        // ---------------------------------------------
        // STARTING
        // ---------------------------------------------

        if (result.status === "starting") {

            progressText.textContent =
                "Preparing conversion...";

            timeRemaining.textContent =
                "Please wait...";

        }


        // ---------------------------------------------
        // CONVERTING
        // ---------------------------------------------

        else if (result.status === "converting") {

            progressText.textContent =
                "Converting...";

            timeRemaining.textContent =
                "Conversion in progress...";

        }


        // ---------------------------------------------
        // COMPLETED
        // ---------------------------------------------

        else if (result.status === "completed") {

            progressFill.style.width = "100%";
            progressPercent.textContent = "100%";

            progressText.textContent =
                "Conversion completed successfully!";

            timeRemaining.textContent =
                "Your file is ready to download.";

            convertBtn.disabled = false;
            convertBtn.textContent = "Convert Again";

            downloadSection.classList.remove("hidden");

            downloadBtn.href =
                `/download?id=${encodeURIComponent(jobId)}`;

            downloadBtn.removeAttribute("download");

            if (result.filename) {
                downloadBtn.setAttribute(
                    "download",
                    result.filename
                );
            }

            return;
        }


        // ---------------------------------------------
        // ERROR
        // ---------------------------------------------

        else if (
            result.status === "error" ||
            result.status === "failed"
        ) {

            throw new Error(
                result.error ||
                "Conversion failed."
            );

        }


        // ---------------------------------------------
        // UNKNOWN STATUS
        // ---------------------------------------------

        else {

            throw new Error(
                `Unknown conversion status: ${result.status}`
            );

        }


        // ---------------------------------------------
        // CHECK AGAIN
        // ---------------------------------------------

        progressTimer = setTimeout(() => {

            checkProgress(jobId);

        }, 800);


    } catch (error) {

        console.error(error);

        showError(error.message);

    }

}


// =====================================================
// ERROR DISPLAY
// =====================================================

function showError(message) {

    if (progressTimer) {
        clearTimeout(progressTimer);
        progressTimer = null;
    }

    progressText.textContent =
        "Conversion failed.";

    timeRemaining.textContent =
        message || "Please try again.";

    convertBtn.disabled = false;
    convertBtn.textContent = "Convert";

}


// =====================================================
// DOWNLOAD BUTTON
// =====================================================

downloadBtn.addEventListener("click", () => {

    if (!currentJobId) {
        return;
    }

    downloadBtn.textContent =
        "Downloading...";

    setTimeout(() => {

        downloadBtn.textContent =
            "Download File";

    }, 1500);

});
