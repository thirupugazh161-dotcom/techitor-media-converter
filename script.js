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


// -----------------------------
// BROWSE FILE
// -----------------------------

browseBtn.addEventListener("click", function () {
    fileInput.click();
});

fileInput.addEventListener("change", function () {

    if (fileInput.files.length === 0) {
        return;
    }

    selectFile(fileInput.files[0]);
});


// -----------------------------
// SELECT FILE
// -----------------------------

function selectFile(file) {

    selectedFile = file;

    fileName.textContent = file.name;

    const sizeMB =
        file.size / (1024 * 1024);

    fileSize.textContent =
        sizeMB.toFixed(2) + " MB";

    fileSection.classList.remove("hidden");

    progressSection.classList.add("hidden");
    downloadSection.classList.add("hidden");

    progressFill.style.width = "0%";
    progressPercent.textContent = "0%";

    timeRemaining.textContent =
        "Ready to convert";
}


// -----------------------------
// DRAG & DROP
// -----------------------------

dropZone.addEventListener("dragover", function (event) {

    event.preventDefault();

    dropZone.style.borderColor =
        "#1677ff";
});


dropZone.addEventListener("dragleave", function () {

    dropZone.style.borderColor =
        "#46506a";
});


dropZone.addEventListener("drop", function (event) {

    event.preventDefault();

    dropZone.style.borderColor =
        "#46506a";

    const files = event.dataTransfer.files;

    if (files.length > 0) {

        selectFile(files[0]);

    }
});


// -----------------------------
// REMOVE FILE
// -----------------------------

removeBtn.addEventListener("click", function () {

    selectedFile = null;

    fileInput.value = "";

    fileSection.classList.add("hidden");

    progressSection.classList.add("hidden");

    downloadSection.classList.add("hidden");

    progressFill.style.width = "0%";

    progressPercent.textContent = "0%";
});


// -----------------------------
// CONVERT
// -----------------------------

convertBtn.addEventListener("click", async function () {

    if (!selectedFile) {

        alert("Please select a file first.");

        return;
    }


    const format =
        formatSelect.value;


    const formData =
        new FormData();

    formData.append(
        "file",
        selectedFile
    );

    formData.append(
        "format",
        format
    );


    convertBtn.disabled = true;

    convertBtn.textContent =
        "Starting...";


    progressSection.classList.remove(
        "hidden"
    );

    downloadSection.classList.add(
        "hidden"
    );


    progressFill.style.width =
        "0%";

    progressPercent.textContent =
        "0%";

    progressText.textContent =
        "Starting conversion...";

    timeRemaining.textContent =
        "Please wait...";


    try {

        // START CONVERSION

        const response =
            await fetch(
                "/convert",
                {
                    method: "POST",
                    body: formData
                }
            );


        if (!response.ok) {

            throw new Error(
                "Unable to start conversion."
            );
        }


        const result =
            await response.json();


        const jobId =
            result.job_id;


        // START PROGRESS CHECK

        checkProgress(jobId);


    } catch (error) {

        console.error(error);

        progressText.textContent =
            "Conversion failed.";

        timeRemaining.textContent =
            "Please try again.";

        convertBtn.disabled = false;

        convertBtn.textContent =
            "Convert";
    }

});


// -----------------------------
// CHECK PROGRESS
// -----------------------------

async function checkProgress(jobId) {

    try {

        const response =
            await fetch(
                "/progress?id=" +
                encodeURIComponent(jobId)
            );


        const responseText = await response.text();

let result;

try {
    result = JSON.parse(responseText);
} catch (e) {
    throw new Error(
        "Server returned an invalid response: " +
        responseText.substring(0, 300)
    );
}

if (!response.ok) {
    throw new Error(
        result.error ||
        "Unable to start conversion."
    );
}

        const progress =
            Number(data.progress) || 0;


        // UPDATE PROGRESS BAR

        progressFill.style.width =
            progress + "%";


        progressPercent.textContent =
            progress + "%";


        if (data.status === "starting") {

            progressText.textContent =
                "Preparing conversion...";

            timeRemaining.textContent =
                "Please wait...";
        }


        else if (data.status === "converting") {

            progressText.textContent =
                "Converting...";

            timeRemaining.textContent =
                "Conversion in progress...";
        }


        // -------------------------
        // COMPLETE
        // -------------------------

        if (data.status === "completed") {

            progressFill.style.width =
                "100%";

            progressPercent.textContent =
                "100%";

            progressText.textContent =
                "Conversion complete!";

            timeRemaining.textContent =
                "Your file is ready.";

            convertBtn.disabled = false;

            convertBtn.textContent =
                "Convert Again";


            downloadSection.classList.remove(
                "hidden"
            );


            downloadBtn.href =
                "/download?id=" +
                encodeURIComponent(jobId);


            downloadBtn.download =
                data.filename;


            return;
        }


        // -------------------------
        // ERROR
        // -------------------------

        if (data.status === "error") {

            throw new Error(
                data.error ||
                "Conversion failed."
            );
        }


        // CHECK AGAIN

        setTimeout(
            function () {
                checkProgress(jobId);
            },
            500
        );


    } catch (error) {

        console.error(error);

        progressText.textContent =
            "Conversion failed.";

        timeRemaining.textContent =
            error.message;

        convertBtn.disabled = false;

        convertBtn.textContent =
            "Convert";
    }

}
