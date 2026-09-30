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
    // MULTI FILE ELEMENTS
    // --------------------------------------------------

    const addMoreFiles =
        document.getElementById("addMoreFiles");

    const addMoreBtn =
        document.getElementById("addMoreBtn");

    const fileCount =
        document.getElementById("fileCount");

    const MAX_FILES = 7;


    // --------------------------------------------------
    // STATE
    // --------------------------------------------------

    let selectedFile = null;

    let selectedFileCount = 0;


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
                (
                    bytes /
                    Math.pow(1024, i)
                ).toFixed(2)
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

        selectedFile = file;

        fileName.textContent =
            file.name;

        fileSize.textContent =
            formatFileSize(file.size);

        fileSection.classList.remove(
            "hidden"
        );

        downloadSection.classList.add(
            "hidden"
        );

        progressSection.classList.add(
            "hidden"
        );

        progressFill.style.width =
            "0%";

        progressPercent.textContent =
            "0%";

        progressText.textContent =
            "Ready to convert";

        timeRemaining.textContent =
            "Select an output format and click Convert.";


        // --------------------------------------------------
        // SHOW ADD ANOTHER FILE
        // --------------------------------------------------

        selectedFileCount = 1;

        if (addMoreFiles) {

            addMoreFiles.classList.remove(
                "hidden"
            );
        }

        if (fileCount) {

            fileCount.textContent =
                selectedFileCount +
                " / " +
                MAX_FILES +
                " files";
        }
    }


    // --------------------------------------------------
    // BROWSE
    // --------------------------------------------------

    browseBtn.addEventListener(
        "click",
        () => {

            fileInput.click();

        }
    );


    // --------------------------------------------------
    // FILE INPUT
    // --------------------------------------------------

    fileInput.addEventListener(
        "change",
        () => {

            const file =
                fileInput.files[0];

            selectFile(file);

        }
    );


    // --------------------------------------------------
    // ADD ANOTHER FILE
    // --------------------------------------------------

    if (addMoreBtn) {

        addMoreBtn.addEventListener(
            "click",
            () => {

                if (
                    selectedFileCount >=
                    MAX_FILES
                ) {

                    alert(
                        "Maximum 7 files allowed."
                    );

                    return;
                }

                fileInput.value = "";

                fileInput.click();

            }
        );
    }


    // --------------------------------------------------
    // DRAG OVER
    // --------------------------------------------------

    dropZone.addEventListener(
        "dragover",
        (event) => {

            event.preventDefault();

            dropZone.classList.add(
                "dragging"
            );

        }
    );


    // --------------------------------------------------
    // DRAG LEAVE
    // --------------------------------------------------

    dropZone.addEventListener(
        "dragleave",
        () => {

            dropZone.classList.remove(
                "dragging"
            );

        }
    );


    // --------------------------------------------------
    // DROP
    // --------------------------------------------------

    dropZone.addEventListener(
        "drop",
        (event) => {

            event.preventDefault();

            dropZone.classList.remove(
                "dragging"
            );

            const file =
                event.dataTransfer.files[0];

            selectFile(file);

        }
    );


    // --------------------------------------------------
    // REMOVE FILE
    // --------------------------------------------------

    removeBtn.addEventListener(
        "click",
        () => {

            selectedFile = null;

            selectedFileCount = 0;

            fileInput.value = "";

            fileSection.classList.add(
                "hidden"
            );

            progressSection.classList.add(
                "hidden"
            );

            downloadSection.classList.add(
                "hidden"
            );

            progressFill.style.width =
                "0%";


            // Hide add-more section

            if (addMoreFiles) {

                addMoreFiles.classList.add(
                    "hidden"
                );
            }

            if (fileCount) {

                fileCount.textContent =
                    "0 / " +
                    MAX_FILES +
                    " files";
            }

        }
    );


    // --------------------------------------------------
    // CONVERT
    // --------------------------------------------------

    convertBtn.addEventListener(
        "click",
        async () => {

            if (!selectedFile) {

                alert(
                    "Please select a file first."
                );

                return;
            }


            const outputFormat =
                formatSelect.value;


            // --------------------------------------------------
            // DISABLE BUTTON
            // --------------------------------------------------

            convertBtn.disabled = true;

            convertBtn.textContent =
                "Converting...";


            // --------------------------------------------------
            // SHOW PROGRESS
            // --------------------------------------------------

            progressSection.classList.remove(
                "hidden"
            );

            downloadSection.classList.add(
                "hidden"
            );

            progressText.textContent =
                "Uploading file...";

            progressPercent.textContent =
                "0%";

            progressFill.style.width =
                "0%";

            timeRemaining.textContent =
                "Preparing conversion...";


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
            // FAKE PROGRESS WHILE SERVER WORKS
            // --------------------------------------------------

            let progress = 0;

            const progressTimer =
                setInterval(
                    () => {

                        if (progress < 90) {

                            progress += 1;

                            progressFill.style.width =
                                progress + "%";

                            progressPercent.textContent =
                                progress + "%";

                            progressText.textContent =
                                "Converting...";
                        }

                    },
                    250
                );


            // --------------------------------------------------
            // SEND TO SERVER
            // --------------------------------------------------

            try {

                const response =
                    await fetch(
                        "/api/convert",
                        {
                            method: "POST",
                            body: formData
                        }
                    );


                clearInterval(
                    progressTimer
                );


                // --------------------------------------------------
                // ERROR
                // --------------------------------------------------

                if (!response.ok) {

                    let errorMessage =
                        "Conversion failed.";

                    try {

                        const errorData =
                            await response.json();

                        if (
                            errorData.error
                        ) {

                            errorMessage =
                                errorData.error;
                        }

                        if (
                            errorData.details
                        ) {

                            console.error(
                                errorData.details
                            );
                        }

                    } catch (e) {

                        // Response wasn't JSON
                    }

                    throw new Error(
                        errorMessage
                    );
                }


                // --------------------------------------------------
                // GET FILE
                // --------------------------------------------------

                const blob =
                    await response.blob();


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

                downloadBtn.href =
                    url;

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

                console.error(
                    "Conversion error:",
                    error
                );

                progressText.textContent =
                    "Conversion failed";

                timeRemaining.textContent =
                    error.message;

                progressFill.style.width =
                    "0%";

                progressPercent.textContent =
                    "0%";

            } finally {

                convertBtn.disabled =
                    false;

                convertBtn.textContent =
                    "Convert";
            }

        }
    );


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
