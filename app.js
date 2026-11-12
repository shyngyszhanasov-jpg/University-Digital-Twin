
const stagesContainer = document.getElementById("stages-container");
const documentsList = document.getElementById("documents-list");
const uploadForm = document.getElementById("upload-form");
const uploadMessage = document.getElementById("upload-message");

async function loadStages() {
    try {
        const response = await fetch("/api/stages");

        if (!response.ok) throw new Error("Failed to load stages");

        const stages = await response.json();
        stagesContainer.replaceChildren();

        stages.forEach(stage => {
            const card = document.createElement("div");
            card.className = "stage-card";

            const number = document.createElement("span");
            number.className = "stage-number";
            number.textContent = `STAGE ${String(stage.id).padStart(2, "0")}`;

            const title = document.createElement("h3");
            title.textContent = stage.name;

            const label = document.createElement("label");
            label.textContent = "Stage status";

            const select = document.createElement("select");

            [
                ["pending", "Pending"],
                ["in_progress", "In Progress"],
                ["completed", "Completed"]
            ].forEach(([value, text]) => {
                const option = document.createElement("option");
                option.value = value;
                option.textContent = text;
                select.appendChild(option);
            });

            select.value = stage.status;

            select.addEventListener("change", async () => {
                select.disabled = true;

                try {
                    const result = await fetch(`/api/stages/${stage.id}`, {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({status: select.value})
                    });

                    if (!result.ok) throw new Error("Update failed");

                    await loadStages();
                } catch (error) {
                    alert("Could not update the stage.");
                    await loadStages();
                }
            });

            card.append(number, title, label, select);
            stagesContainer.appendChild(card);
        });

        const completed = stages.filter(s => s.status === "completed").length;
        const active = stages.filter(s => s.status === "in_progress").length;
        const progress = stages.length
            ? Math.round(completed / stages.length * 100)
            : 0;

        document.getElementById("total-stages").textContent = stages.length;
        document.getElementById("completed-stages").textContent = completed;
        document.getElementById("active-stages").textContent = active;
        document.getElementById("progress-value").textContent = `${progress}%`;
        document.getElementById("progress-label").textContent = `${progress}% completed`;
        document.getElementById("progress-bar").style.width = `${progress}%`;

    } catch (error) {
        stagesContainer.textContent = "Unable to load process stages.";
        console.error(error);
    }
}

async function loadDocuments() {
    try {
        const response = await fetch("/api/documents");

        if (!response.ok) throw new Error("Failed to load documents");

        const documents = await response.json();
        documentsList.replaceChildren();

        if (documents.length === 0) {
            documentsList.textContent = "No documents uploaded yet.";
            return;
        }

        documents.forEach(doc => {
            const item = document.createElement("div");
            item.className = "document-item";

            const title = document.createElement("h4");
            title.textContent = doc.filename;

            const info = document.createElement("p");
            info.textContent =
                `${doc.source === "demo" ? "DEMO DATA" : "Uploaded"} · ` +
                `${doc.text_length} text characters · ${doc.uploaded_at}`;

            const actions = document.createElement("div");
            actions.className = "document-actions";

            const viewButton = document.createElement("button");
            viewButton.type = "button";
            viewButton.textContent = "View Text";
            viewButton.addEventListener("click", () => viewDocument(doc.id));

            actions.appendChild(viewButton);

            if (doc.source !== "demo") {
                const deleteButton = document.createElement("button");
                deleteButton.type = "button";
                deleteButton.className = "delete-document";
                deleteButton.textContent = "Delete";

                deleteButton.addEventListener("click", async () => {
                    if (!confirm(`Delete "${doc.filename}"?`)) return;

                    try {
                        const result = await fetch(`/api/documents/${doc.id}`, {
                            method: "DELETE"
                        });

                        const data = await result.json();

                        if (!result.ok) throw new Error(data.error);

                        document.getElementById("preview-title").textContent =
                            "Document Text";
                        document.getElementById("preview-info").textContent =
                            "Select a document to view its extracted text.";
                        document.getElementById("document-text").textContent =
                            "No document selected.";

                        await loadDocuments();
                    } catch (error) {
                        alert(error.message || "Could not delete document.");
                    }
                });

                actions.appendChild(deleteButton);
            }

            item.append(title, info, actions);
            documentsList.appendChild(item);
        });
    } catch (error) {
        documentsList.textContent = "Unable to load documents.";
        console.error(error);
    }
}

async function viewDocument(id) {
    try {
        const response = await fetch(`/api/documents/${id}`);
        const doc = await response.json();

        if (!response.ok) throw new Error(doc.error);

        document.getElementById("preview-title").textContent = doc.filename;
        document.getElementById("preview-info").textContent =
            doc.source === "demo"
                ? "Demonstration text — not an official university regulation."
                : `Uploaded on ${doc.uploaded_at}`;

        document.getElementById("document-text").textContent =
            doc.extracted_text;
    } catch (error) {
        alert(error.message || "Could not read document.");
    }
}

uploadForm.addEventListener("submit", async event => {
    event.preventDefault();

    const fileInput = document.getElementById("document-file");
    const file = fileInput.files[0];

    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
        uploadMessage.textContent = "The file must be smaller than 10 MB.";
        return;
    }

    const extension = file.name.split(".").pop().toLowerCase();

    if (!["pdf", "docx"].includes(extension)) {
        uploadMessage.textContent = "Only PDF and DOCX files are supported.";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    const submitButton = uploadForm.querySelector("button");
    submitButton.disabled = true;
    uploadMessage.textContent = "Uploading and extracting text...";

    try {
        const response = await fetch("/api/documents", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) throw new Error(data.error || "Upload failed");

        uploadMessage.textContent = data.message;
        uploadForm.reset();
        await loadDocuments();
        await viewDocument(data.id);
    } catch (error) {
        uploadMessage.textContent = error.message || "Upload failed.";
    } finally {
        submitButton.disabled = false;
    }
});

loadStages();
loadDocuments();

const chatForm = document.getElementById("chat-form");

if (chatForm) {
    chatForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const input = document.getElementById("chat-input");
        const messages = document.getElementById("chat-messages");

        const question = input.value.trim();

        if (!question) return;

        const userMessage = document.createElement("div");
        userMessage.className = "chat-message user";
        userMessage.textContent = question;
        messages.appendChild(userMessage);

        input.value = "";

        const loading = document.createElement("div");
        loading.className = "chat-message assistant";
        loading.textContent = "AI is thinking...";
        messages.appendChild(loading);

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ question: question })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Request failed");
            }

            loading.textContent = data.answer;

        } catch (error) {
            loading.textContent = "Error: " + error.message;
        }

        messages.scrollTop = messages.scrollHeight;
    });
}