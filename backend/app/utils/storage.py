import hashlib
import os

from flask import current_app
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.utils.errors import ApiError

CHUNK_SIZE = 1024 * 1024


def validate_pdf_upload(file_storage):
    if not file_storage or not file_storage.filename:
        raise ApiError("validation_error", "a PDF file is required", 400)
    if file_storage.mimetype != "application/pdf":
        raise ApiError("validation_error", "only PDF files are accepted", 400)


def save_pdf_version(file_storage, document_id, version_number):
    """Stream the upload to disk under PDF_STORAGE_DIR/{document_id}/v{n}.pdf, hashing as it writes."""
    doc_dir = os.path.join(current_app.config["PDF_STORAGE_DIR"], str(document_id))
    os.makedirs(doc_dir, exist_ok=True)
    file_path = os.path.join(doc_dir, f"v{version_number}.pdf")

    sha256 = hashlib.sha256()
    with open(file_path, "wb") as out:
        while True:
            chunk = file_storage.stream.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
            out.write(chunk)

    try:
        page_count = len(PdfReader(file_path).pages)
    except PdfReadError:
        os.remove(file_path)
        raise ApiError("validation_error", "the uploaded file is not a valid PDF", 400)

    return file_path, sha256.hexdigest(), page_count
