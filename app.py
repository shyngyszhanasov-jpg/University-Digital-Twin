
from flask import Flask, render_template, jsonify, request
from pathlib import Path
from datetime import datetime
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from docx import Document
from database import get_connection, create_database
from agent import ask_agent

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {"pdf", "docx"}

create_database()


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def extract_text(file_path):
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(str(file_path))

        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")

        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        ).strip()

    if suffix == ".docx":
        document = Document(str(file_path))
        paragraphs = [
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        for table in document.tables:
            for row in table.rows:
                paragraphs.append(
                    " | ".join(cell.text for cell in row.cells)
                )

        return "\n".join(paragraphs).strip()

    raise ValueError("Unsupported file type.")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stages", methods=["GET"])
def get_stages():
    connection = get_connection()
    stages = connection.execute(
        "SELECT * FROM stages ORDER BY id"
    ).fetchall()
    connection.close()

    return jsonify([dict(stage) for stage in stages])


@app.route("/api/stages/<int:stage_id>", methods=["POST"])
def update_stage(stage_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")

    if status not in {"pending", "in_progress", "completed"}:
        return jsonify({"error": "Invalid status"}), 400

    connection = get_connection()
    cursor = connection.execute(
        "UPDATE stages SET status = ? WHERE id = ?",
        (status, stage_id)
    )
    connection.commit()
    updated = cursor.rowcount > 0
    connection.close()

    if not updated:
        return jsonify({"error": "Stage not found"}), 404

    return jsonify({"message": "Stage updated successfully"})


@app.route("/api/documents", methods=["GET"])
def get_documents():
    connection = get_connection()
    documents = connection.execute("""
        SELECT id, filename, uploaded_at, source,
               length(extracted_text) AS text_length
        FROM documents
        ORDER BY id DESC
    """).fetchall()
    connection.close()

    return jsonify([dict(document) for document in documents])


@app.route("/api/documents/<int:document_id>", methods=["GET"])
def get_document(document_id):
    connection = get_connection()
    document = connection.execute("""
        SELECT id, filename, extracted_text, uploaded_at, source
        FROM documents
        WHERE id = ?
    """, (document_id,)).fetchone()
    connection.close()

    if document is None:
        return jsonify({"error": "Document not found"}), 404

    return jsonify(dict(document))


@app.route("/api/documents", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "Select a file first."}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"error": "Select a file first."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF and DOCX files are allowed."}), 400

    original_name = secure_filename(file.filename)

    if not original_name:
        return jsonify({"error": "Invalid filename."}), 400

    destination = UPLOAD_FOLDER / original_name

    counter = 1
    while destination.exists():
        destination = UPLOAD_FOLDER / (
            f"{Path(original_name).stem}_{counter}"
            f"{Path(original_name).suffix}"
        )
        counter += 1

    try:
        file.save(destination)
        text = extract_text(destination)

        if not text:
            raise ValueError(
                "No readable text found. Scanned PDFs may need OCR."
            )

        connection = get_connection()
        cursor = connection.execute("""
            INSERT INTO documents
                (filename, file_path, extracted_text, uploaded_at, source)
            VALUES (?, ?, ?, ?, 'uploaded')
        """, (
            original_name,
            str(destination.relative_to(BASE_DIR)),
            text,
            datetime.now().isoformat(timespec="seconds")
        ))
        connection.commit()
        document_id = cursor.lastrowid
        connection.close()

        return jsonify({
            "message": "Document uploaded and processed.",
            "id": document_id
        }), 201

    except Exception as error:
        if destination.exists():
            destination.unlink()

        if isinstance(error, (ValueError, OSError)):
            return jsonify({"error": str(error)}), 400

        app.logger.exception("Document processing failed")
        return jsonify({
            "error": "Could not process the document."
        }), 500


@app.route("/api/documents/<int:document_id>", methods=["DELETE"])
def delete_document(document_id):
    connection = get_connection()
    document = connection.execute("""
        SELECT file_path, source
        FROM documents
        WHERE id = ?
    """, (document_id,)).fetchone()

    if document is None:
        connection.close()
        return jsonify({"error": "Document not found"}), 404

    connection.execute(
        "DELETE FROM documents WHERE id = ?",
        (document_id,)
    )
    connection.commit()
    connection.close()

    if document["file_path"]:
        path = (BASE_DIR / document["file_path"]).resolve()

        if path.parent == UPLOAD_FOLDER.resolve() and path.is_file():
            path.unlink()

    return jsonify({"message": "Document deleted."})


@app.errorhandler(413)
def file_too_large(error):
    return jsonify({"error": "Maximum file size is 10 MB."}), 413


if __name__ == "__main__":
    app.run(debug=True)


    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.get_json(silent=True) or {}
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"error": "Please enter a question."}), 400

        if len(question) > 2000:
            return jsonify({"error": "Question is too long."}), 400

        try:
            answer = ask_agent(question)
            return jsonify({"answer": answer})

        except Exception as error:
            app.logger.exception("Gemini API request failed")
            return jsonify({
                "error": "Could not get an answer from the AI agent. Check the server log."
            }), 500