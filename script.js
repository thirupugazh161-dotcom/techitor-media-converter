const MAX_FILES = 7;

const browseBtn = document.getElementById("browseBtn");
const fileInput = document.getElementById("fileInput");
const dropZone = document.getElementById("dropZone");
const filesContainer = document.getElementById("filesContainer");

let filesList = [];


/* =========================================
   BROWSE
========================================= */

browseBtn.addEventListener("click", () => {
    fileInput.click();
});


fileInput.addEventListener("change", (event) => {

    const selectedFiles = Array.from(event.target.files);

    addFiles(selectedFiles);

    // Allows selecting same file again later
    fileInput.value = "";
});


/* =========================================
   DRAG & DROP
========================================= */

dropZone.addEventListener("dragover", (event) => {

    event.preventDefault();

    dropZone.classList.add("drag-active");
});


dropZone.addEventListener("dragleave", () => {

    dropZone.classList.remove("drag-active");
});


dropZone.addEventListener("drop", (event) => {

    event.preventDefault();

    dropZone.classList.remove("drag-active");

    const droppedFiles = Array.from(event.dataTransfer.files);

    addFiles(droppedFiles);
});


/* =========================================
   ADD FILES
========================================= */

function addFiles(newFiles) {

    if (!newFiles.length) {
        return;
    }

    if (filesList.length >= MAX_FILES) {

        alert("Maximum 7 files allowed.");

        return;
    }


    const remainingSlots = MAX_FILES - filesList.length;

    const filesToAdd = newFiles.slice(0, remainingSlots);


    filesToAdd.forEach((file) => {

        const fileObject = {
            id: crypto.randomUUID(),
            file: file,
            outputFormat: "mp4",
            converting: false,
            completed: false
        };

        filesList.push(fileObject);

        createFileCard(fileObject);
    });


    updateFileCount();


    if (newFiles.length > remainingSlots) {

        alert("Only 7 files can be added at a time.");
    }
}


/* =========================================
   FILE CARD
========================================= */

function createFileCard(fileObject) {

    const card = document.createElement("section");

    card.className = "file-card";

    card.dataset.id = fileObject.id;


    const sizeMB =
        (fileObject.file.size / (1024 * 1024)).toFixed(2);


    card.innerHTML = `

        <div class="file-header">

            <div>

                <h3 class="file-name">
                    ${escapeHtml(fileObject.file.name)}
                </h3>

                <p class="file-size">
                    ${sizeMB} MB
                </p>

            </div>

            <button
                type="button"
                class="remove-btn"
                data-action="remove"
            >
                ×
            </button>

        </div>


        <label class="format-label">
            Convert To
        </label>


        <select class="format-select">

            <option value="mp3">MP3</option>
            <option value="wav">WAV</option>
            <option value="m4a">M4A</option>
            <option value="mp4" selected>MP4</option>
            <option value="mov">MOV</option>
            <option value="mkv">MKV</option>
            <option value="webm">WEBM</option>

        </select>


        <button
            type="button"
            class="convert-btn"
            data-action="convert"
        >
            Convert
        </button>


        <div class="add-more-files">

            <button
                type="button"
                class="add-more-btn"
                data-action="add"
            >
                + Add Another File
            </button>

            <p class="file-count">
                ${filesList.length} / ${MAX_FILES} files
            </p>

        </div>


        <div class="progress-section hidden">

            <div class="progress-info">

                <span class="progress-text">
                    Preparing conversion...
                </span>

                <span class="progress-percent">
                    0%
                </span>

            </div>


            <div class="progress-bar">

                <div class="progress-fill"></div>

            </div>


            <p class="time-remaining">
                Preparing conversion...
            </p>

        </div>


        <div class="download-section hidden">

            <p class="success-message">
                Conversion completed successfully!
            </p>

            <a
                class="download-btn"
                target="_blank"
                download
            >
                Download File
            </a>

        </div>
    `;


    filesContainer.appendChild(card);


    const formatSelect =
        card.querySelector(".format-select");


    formatSelect.addEventListener("change", () => {

        fileObject.outputFormat = formatSelect.value;
    });


    card.addEventListener("click", (event) => {

        const actionElement =
            event.target.closest("[data-action]");

        if (!actionElement) {
            return;
        }


        const action =
            actionElement.dataset.action;


        if (action === "remove") {

            removeFile(fileObject.id);

        } else if (action === "add") {

            fileInput.click();

        } else if (action === "convert") {

            convertFile(fileObject, card);
        }

    });
}


/* =========================================
   REMOVE FILE
========================================= */

function removeFile(id) {

    const index =
        filesList.findIndex(item => item.id === id);


    if (index === -1) {
        return;
    }


    filesList.splice(index, 1);


    const card =
        filesContainer.querySelector(
            `[data-id="${id}"]`
        );


    if (card) {
        card.remove();
    }


    updateFileCount();
}


/* =========================================
   UPDATE COUNT
========================================= */

function updateFileCount() {

    const cards =
        filesContainer.querySelectorAll(".file-card");


    cards.forEach((card) => {

        const count =
            card.querySelector(".file-count");

        if (count) {

            count.textContent =
                `${filesList.length} / ${MAX_FILES} files`;
        }
    });
}


/* =========================================
   CONVERT
========================================= */

async function convertFile(fileObject, card) {

    if (fileObject.converting) {
        return;
    }


    const formatSelect =
        card.querySelector(".format-select");

    const convertBtn =
        card.querySelector(".convert-btn");

    const progressSection =
        card.querySelector(".progress-section");

    const progressFill =
        card.querySelector(".progress-fill");

    const progressText =
        card.querySelector(".progress-text");

    const progressPercent =
        card.querySelector(".progress-percent");

    const timeRemaining =
        card.querySelector(".time-remaining");

    const downloadSection =
        card.querySelector(".download-section");

    const downloadBtn =
        card.querySelector(".download-btn");

    const successMessage =
        card.querySelector(".success-message");


    const outputFormat =
        formatSelect.value;


    fileObject.outputFormat =
        outputFormat;

    fileObject.converting = true;


    convertBtn.disabled = true;

    convertBtn.textContent = "Converting...";

    progressSection.classList.remove("hidden");

    downloadSection.classList.add("hidden");


    progressFill.style.width = "0%";

    progressPercent.textContent = "0%";

    progressText.textContent =
        "Preparing conversion...";

    timeRemaining.textContent =
        "Preparing conversion...";


    /*
     * Fake initial progress so the UI doesn't look frozen.
     * Real conversion result is still controlled by server.
     */

    let fakeProgress = 0;

    const progressTimer = setInterval(() => {

        if (fakeProgress < 90) {

            fakeProgress += 1;

            progressFill.style.width =
                `${fakeProgress}%`;

            progressPercent.textContent =
                `${fakeProgress}%`;

            progressText.textContent =
                "Converting...";

        }

    }, 500);


    try {

        const formData = new FormData();

        formData.append(
            "file",
            fileObject.file
        );

        formData.append(
            "format",
            outputFormat
        );


        const response =
            await fetch("/api/convert", {

                method: "POST",

                body: formData
            });


        clearInterval(progressTimer);


        let data = null;

        try {

            data = await response.json();

        } catch (jsonError) {

            throw new Error(
                "Server returned an invalid response."
            );
        }


        if (!response.ok || !data.success) {

            throw new Error(
                data?.error ||
                data?.details ||
                "Conversion failed."
            );
        }


        /*
         * SUCCESS
         */

        progressFill.style.width = "100%";

        progressPercent.textContent = "100%";

        progressText.textContent =
            "Conversion completed!";

        timeRemaining.textContent =
            "Ready to download.";


        fileObject.completed = true;


        if (data.download_url) {

            downloadBtn.href =
                data.download_url;

        } else if (data.file_url) {

            downloadBtn.href =
                data.file_url;

        } else if (data.download) {

            downloadBtn.href =
                data.download;

        } else {

            throw new Error(
                "Conversion completed, but download URL was not returned."
            );
        }


        if (data.filename) {

            downloadBtn.download =
                data.filename;
        }


        successMessage.textContent =
            "Conversion completed successfully!";


        downloadSection.classList.remove("hidden");


        convertBtn.textContent =
            "Convert Again";

    } catch (error) {

        clearInterval(progressTimer);


        progressFill.style.width = "0%";

        progressPercent.textContent = "0%";

        progressText.textContent =
            "Conversion failed";

        timeRemaining.textContent =
            error.message ||
            "Conversion failed.";


        convertBtn.disabled = false;

        convertBtn.textContent =
            "Convert";

    } finally {

        fileObject.converting = false;
    }
}


/* =========================================
   HTML ESCAPE
========================================= */

function escapeHtml(value) {

    return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
