
import os
import re

from dotenv import load_dotenv
from google import genai

from database import get_connection

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key) if api_key else None

MODEL_NAME = "gemini-flash-latest"


def find_relevant_documents(question, limit=3):
    connection = get_connection()

    documents = connection.execute("""
        SELECT id, filename, extracted_text, source
        FROM documents
        WHERE extracted_text IS NOT NULL
        ORDER BY uploaded_at DESC
    """).fetchall()

    connection.close()

    words = set(re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]{3,}", question.lower()))

    ranked = []

    for document in documents:
        text = document["extracted_text"] or ""
        searchable = (document["filename"] + " " + text).lower()

        score = sum(1 for word in words if word in searchable)

        if score > 0:
            ranked.append((score, document))

    ranked.sort(key=lambda item: item[0], reverse=True)

    return [item[1] for item in ranked[:limit]]


def ask_agent(question):
    if client is None:
        return "Gemini API key is not configured. Check your .env file."

    documents = find_relevant_documents(question)

    if not documents:
        return "I could not find relevant information in the uploaded documents."

    context_parts = []

    for document in documents:
        context_parts.append(
            f"Document: {document['filename']}\n"
            f"Source type: {document['source']}\n"
            f"Text:\n{document['extracted_text'][:5000]}"
        )

    context = "\n\n".join(context_parts)

    prompt = f"""
You are the AI assistant of the University Digital Twin system.

Answer the user's question using only the supplied document context.

Rules:
- Answer in Russian.
- Do not invent university rules, deadlines, or responsibilities.
- If information is missing, clearly say that it was not found.
- Mention the filename of the document supporting the answer.
- Treat demonstration documents as fictional test data, not official regulations.
- If documents disagree, explain the disagreement.

DOCUMENT CONTEXT:
{context}

USER QUESTION:
{question}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text or "The AI model did not return a text response."
