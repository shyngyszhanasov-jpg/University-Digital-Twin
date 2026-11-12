
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():
    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS stages (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_path TEXT,
            extracted_text TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'uploaded'
        )
    """)

    count = connection.execute(
        "SELECT COUNT(*) FROM stages"
    ).fetchone()[0]

    if count == 0:
        stages = [
            (1, "Student Registration", "completed"),
            (2, "Document Submission", "completed"),
            (3, "Document Verification", "in_progress"),
            (4, "Application Processing", "pending"),
            (5, "Application Approval", "pending"),
            (6, "Process Completion", "pending")
        ]

        connection.executemany(
            "INSERT INTO stages (id, name, status) VALUES (?, ?, ?)",
            stages
        )

    demo_count = connection.execute(
        "SELECT COUNT(*) FROM documents WHERE source = 'demo'"
    ).fetchone()[0]

    if demo_count == 0:
        demo_text = """
DEMONSTRATION DOCUMENT — NOT AN OFFICIAL UNIVERSITY REGULATION

Title: Example University Application Procedure

1. Application Submission
A student submits an application and the required documents.

2. Document Verification
A responsible staff member checks whether the submitted documents
are complete and readable.

3. Application Processing
The application is reviewed after the verification stage.

4. Decision
The application is marked as approved or requires additional information.

5. Process Completion
The application status is updated and the student is informed.

Note: This text is fictional test data created for the University
Digital Twin prototype. It does not describe verified university rules.
"""

        connection.execute("""
            INSERT INTO documents
                (filename, file_path, extracted_text, uploaded_at, source)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "demo_application_procedure.txt",
            None,
            demo_text.strip(),
            datetime.now().isoformat(timespec="seconds"),
            "demo"
        ))

    connection.commit()
    connection.close()


if __name__ == "__main__":
    create_database()
    print("Database initialized successfully!")
