document.addEventListener("DOMContentLoaded", () => {

    // --------------------------------------------------
    // ELEMENTS
    // --------------------------------------------------

    const dropZone = document.getElementById("dropZone");
    const browseBtn = document.getElementById("browseBtn");
    const fileInput = document.getElementById("fileInput");

    const fileSection = document.getElementById("fileSection");

    const fileName = document.getElementById("fileName");
    const fileSize = document.getElementById("fileSize");

    const removeBtn = document.getElementById("removeBtn");

    const formatSelect = document.getElementById("formatSelect");
    const convertBtn = document.getElementById("convertBtn");

    const progressSection =
        document.getElementById("progressSection");

    const progressText =
        document.getElementById("progressText");

    const progressPercent =
        document.getElementById("progressPercent");

    const progressFill =
        document.getElementById("progressFill");

    const timeRemaining =
        document.getElementById("timeRemaining");

    const downloadSection =
        document.getElementById("downloadSection");

    const downloadBtn =
        document.getElementById("downloadBtn");

    const successMessage =
        document.getElementById("successMessage");


    // --------------------------------------------------
    // STATE
    // --------------------------------------------------

    let selectedFile = null;

    // IMPORTANT:
    // Keep timer outside the convert function so it can
    // always be cleared when selecting/removing a file.
    let progressTimer = null;

    // Used to identify the latest conversion.
    // Prevents an old conversion from updating a new file.
    let conversionId = 0;

    // Allows us to cancel the browser-side request
    // when a new file is selected.
    let activeController = null;


    // --------------------------------------------------
    // RESET PROGRESS
    // --------------------------------------------------

    function resetProgress() {

        if (progressTimer !== null) {
            clearInterval(progressTimer);
            progressTimer = null;
        }

        progressFill.style.width = "0%";
        progressPercent.textContent = "0%";

        progressText.textContent =
            "Ready to convert";

        timeRemaining.textContent =
            "Select an output format and click Convert.";
    }


    // --------------------------------------------------
    // CANCEL CURRENT CONVERSION
    // --------------------------------------------------

    function cancelCurrentConversion() {

        // Stop fake progress timer
        if (progressTimer !== null) {
            clearInterval(progressTimer);
            progressTimer = null;
        }

        // Cancel browser fetch request
        if (activeController !== null) {
            activeController.abort();
            activeController = null;
        }

        // Make every old async operation obsolete
        conversionId++;
    }


    // --------------------------------------------------
    // FORMAT FILE SIZE
    // --------------------------------------------------

    function formatFileSize(bytes) {

        if (bytes === 0) {
            return "0 Bytes";
        }

        const units = [
            "Bytes",
            "KB",
            "MB",
            "GB"
        ];

        const i =
            Math.floor(
                Math.log(bytes) /
                Math.log(1024)
            );

        return (
            parseFloat(
                (bytes / Math.pow(1024, i))
                    .toFixed(2)
            )
            + " "
            + units[i]
        );
    }


    // --------------------------------------------------
    // SELECT FILE
    // --------------------------------------------------

    function selectFile(file) {

        if (!file) {
            return;
        }

        // IMPORTANT:
        // Stop any previous conversion before accepting
        // the new file.
        cancelCurrentConversion();

        selectedFile = file;

        fileName.textContent = file.name;

        fileSize.textContent =
            formatFileSize(file.size);

        fileSection.classList.remove("hidden");

        downloadSection.classList.add("hidden");

        progressSection.classList.add("hidden");

        progressFill.style.width = "0%";

        progressPercent.textContent = "0%";

        progressText.textContent =
            "Ready to convert";

        timeRemaining.textContent =
            "Select an output format and click Convert.";

        // Reset download link
        downloadBtn.removeAttribute("href");

        // Reset success message
        successMessage.textContent = "";
    }


    // --------------------------------------------------
    // BROWSE
    // --------------------------------------------------

    browseBtn.addEventListener("click", () => {
        fileInput.click();
    });


    // --------------------------------------------------
    // FILE INPUT
    // --------------------------------------------------

    fileInput.addEventListener("change", () => {

        const file = fileInput.files[0];

        if (file) {
            selectFile(file);
        }
    });


    // --------------------------------------------------
    // DRAG OVER
    // --------------------------------------------------

    dropZone.addEventListener("dragover", (event) => {

        event.preventDefault();

        dropZone.classList.add("dragging");
    });


    // --------------------------------------------------
    // DRAG LEAVE
    // --------------------------------------------------

    dropZone.addEventListener("dragleave", () => {

        dropZone.classList.remove("dragging");
    });


    // --------------------------------------------------
    // DROP
    // --------------------------------------------------

    dropZone.addEventListener("drop", (event) => {

        event.preventDefault();

        dropZone.classList.remove("dragging");

        const file =
            event.dataTransfer.files[0];

        if (file) {
            selectFile(file);
        }
    });


    // --------------------------------------------------
    // REMOVE FILE
    // --------------------------------------------------

    removeBtn.addEventListener("click", () => {

        // Stop everything related to old file
        cancelCurrentConversion();

        selectedFile = null;

        fileInput.value = "";

        fileSection.classList.add("hidden");

        progressSection.classList.add("hidden");

        downloadSection.classList.add("hidden");

        progressFill.style.width = "0%";

        progressPercent.textContent = "0%";

        progressText.textContent =
            "Ready to convert";

        timeRemaining.textContent =
            "Select an output format and click Convert.";

        downloadBtn.removeAttribute("href");

        successMessage.textContent = "";

        convertBtn.disabled = false;

        convertBtn.textContent = "Convert";
    });


    // --------------------------------------------------
    // CONVERT
    // --------------------------------------------------

    convertBtn.addEventListener("click", async () => {

        if (!selectedFile) {

            alert("Please select a file first.");

            return;
        }


        // --------------------------------------------------
        // CANCEL ANY PREVIOUS CONVERSION
        // --------------------------------------------------

        cancelCurrentConversion();


        // Create a unique ID for this conversion
        const thisConversionId = conversionId;


        const outputFormat =
            formatSelect.value;


        // Create AbortController for this request
        const controller = new AbortController();

        activeController = controller;


        // --------------------------------------------------
        // DISABLE BUTTON
        // --------------------------------------------------

        convertBtn.disabled = true;

        convertBtn.textContent =
            "Converting...";


        // --------------------------------------------------
        // SHOW PROGRESS
        // --------------------------------------------------

        progressSection.classList.remove("hidden");

        downloadSection.classList.add("hidden");

        progressText.textContent =
            "Uploading file...";

        progressPercent.textContent =
            "0%";

        progressFill.style.width =
            "0%";

        timeRemaining.textContent =
            "Preparing conversion.";


        // --------------------------------------------------
        // FORM DATA
        // --------------------------------------------------

        const formData =
            new FormData();

        formData.append(
            "file",
            selectedFile
        );

        formData.append(
            "format",
            outputFormat
        );


        // --------------------------------------------------
        // FAKE PROGRESS
        // --------------------------------------------------

        let progress = 0;

        progressTimer = setInterval(() => {

            // If this is no longer the active conversion,
            // stop immediately.
            if (thisConversionId !== conversionId) {

                clearInterval(progressTimer);

                progressTimer = null;

                return;
            }


            if (progress < 90) {

                progress += 1;

                progressFill.style.width =
                    progress + "%";

                progressPercent.textContent =
                    progress + "%";

                progressText.textContent =
                    "Converting...";
            }

        }, 250);


        // --------------------------------------------------
        // SEND TO SERVER
        // --------------------------------------------------

        try {

            const response =
                await fetch(
                    "/api/convert",
                    {
                        method: "POST",
                        body: formData,
                        signal: controller.signal
                    }
                );


            // --------------------------------------------------
            // CHECK WHETHER THIS IS STILL THE ACTIVE
            // CONVERSION
            // --------------------------------------------------

            if (thisConversionId !== conversionId) {

                return;
            }


            // --------------------------------------------------
            // STOP PROGRESS TIMER
            // --------------------------------------------------

            if (progressTimer !== null) {

                clearInterval(progressTimer);

                progressTimer = null;
            }


            // --------------------------------------------------
            // ERROR
            // --------------------------------------------------

            if (!response.ok) {

                let errorMessage =
                    "Conversion failed.";

                try {

                    const errorData =
                        await response.json();

                    if (errorData.error) {

                        errorMessage =
                            errorData.error;
                    }

                    if (errorData.details) {

                        console.error(
                            "Server details:",
                            errorData.details
                        );
                    }

                } catch (e) {

                    console.error(
                        "Could not read error response:",
                        e
                    );
                }


                throw new Error(
                    errorMessage
                );
            }


            // --------------------------------------------------
            // GET CONVERTED FILE
            // --------------------------------------------------

            const blob =
                await response.blob();


            // Check one more time because
            // file could have changed while downloading.
            if (thisConversionId !== conversionId) {

                return;
            }


            // --------------------------------------------------
            // FINISH PROGRESS
            // --------------------------------------------------

            progressFill.style.width =
                "100%";

            progressPercent.textContent =
                "100%";

            progressText.textContent =
                "Conversion complete";

            timeRemaining.textContent =
                "Your file is ready to download.";


            // --------------------------------------------------
            // DOWNLOAD
            // --------------------------------------------------

            const url =
                window.URL.createObjectURL(
                    blob
                );

            downloadBtn.href = url;

            downloadBtn.download =
                getDownloadName(
                    selectedFile.name,
                    outputFormat
                );


            downloadSection.classList.remove(
                "hidden"
            );


            successMessage.textContent =
                "Conversion completed successfully!";


        } catch (error) {

            // --------------------------------------------------
            // IGNORE ABORTED / OLD REQUEST
            // --------------------------------------------------

            if (
                error.name === "AbortError" ||
                thisConversionId !== conversionId
            ) {

                return;
            }


            console.error(
                "Conversion error:",
                error
            );


            // --------------------------------------------------
            // STOP TIMER ON EVERY ERROR
            // --------------------------------------------------

            if (progressTimer !== null) {

                clearInterval(progressTimer);

                progressTimer = null;
            }


            // --------------------------------------------------
            // SHOW ERROR
            // --------------------------------------------------

            progressText.textContent =
                "Conversion failed";

            timeRemaining.textContent =
                error.message ||
                "Something went wrong during conversion.";

            progressFill.style.width =
                "0%";

            progressPercent.textContent =
                "0%";


        } finally {

            // Only update the button if this is
            // still the current conversion.
            if (thisConversionId === conversionId) {

                convertBtn.disabled = false;

                convertBtn.textContent =
                    "Convert";

                activeController = null;
            }
        }

    });


    // --------------------------------------------------
    // DOWNLOAD NAME
    // --------------------------------------------------

    function getDownloadName(
        originalName,
        extension
    ) {

        const lastDot =
            originalName.lastIndexOf(".");


        let baseName =
            originalName;


        if (lastDot !== -1) {

            baseName =
                originalName.substring(
                    0,
                    lastDot
                );
        }


        return (
            baseName +
            "_converted." +
            extension
        );
    }

});
