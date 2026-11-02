import hashlib
import os

from flask import current_app
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.utils import filetypes
from app.utils.errors import ApiError

CHUNK_SIZE = 1024 * 1024


def validate_upload(file_storage):
    """Reject a missing file or an unsupported extension before anything is written to
    disk. Keyed on extension rather than the browser's mimetype (see filetypes.py) —
    returns the FILE_TYPES key so the caller doesn't re-derive it.

    A recognized-but-unreadable format (.doc, .rtf, ...) gets a specific "here's what to
    do" message rather than a generic rejection, since the fix is usually a 10-second
    re-save in the source application, not a different document.
    """
    if not file_storage or not file_storage.filename:
        raise ApiError("validation_error", "a file is required", 400)

    ext = filetypes.extension_of(file_storage.filename)
    if ext in filetypes.REJECTED_EXTENSIONS:
        raise ApiError("validation_error", filetypes.REJECTED_EXTENSIONS[ext], 400)

    file_type = filetypes.type_for_filename(file_storage.filename)
    if not file_type:
        raise ApiError(
            "validation_error",
            f"unsupported file type; accepted formats: {filetypes.accepted_extensions_sentence()}",
            400,
        )
    return file_type


def _write_to_disk(file_storage, file_path):
    """Stream the upload to `file_path`, hashing as it writes. Returns the sha256 hex
    digest. Streamed rather than read-then-write so a large scan doesn't sit in memory
    twice over."""
    sha256 = hashlib.sha256()
    with open(file_path, "wb") as out:
        while True:
            chunk = file_storage.stream.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
            out.write(chunk)
    return sha256.hexdigest()


def _validate_and_count_pages(file_path, file_type):
    """Confirm the file actually parses as its claimed type (a correct extension isn't
    proof of file contents) and return a page count.

    PDF and image counts are structural (pypdf's page count; one image is one page).
    Word and text have no structural page count, so this runs the same pseudo-pagination
    extraction that indexing will use later — cheap for both, since neither format ever
    goes through OCR — so the admin table's page count matches what citations will cite.
    """
    if file_type == filetypes.PDF:
        try:
            return len(PdfReader(file_path).pages)
        except PdfReadError:
            raise ApiError("validation_error", "the uploaded file is not a valid PDF", 400)

    if file_type == filetypes.IMAGE:
        try:
            from PIL import Image, UnidentifiedImageError

            with Image.open(file_path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError):
            raise ApiError("validation_error", "the uploaded file is not a valid image", 400)
        return 1

    # DOCX / TEXT: extract now (fast, no OCR) purely to learn the pseudo-page count.
    from app.rag.extraction import ExtractionError, extract_pages

    try:
        pages = extract_pages(
            file_path,
            file_type,
            min_chars_per_page=current_app.config["RAG_MIN_CHARS_PER_PAGE"],
            page_chars=current_app.config["RAG_PAGE_CHARS"],
            ocr_enabled=False,
        )
    except ExtractionError as err:
        label = filetypes.FILE_TYPES[file_type]["label"]
        raise ApiError("validation_error", f"the uploaded {label} could not be read: {err}", 400)
    return len(pages)


def save_version(file_storage, document_id, version_number, file_type):
    """Stream the upload to PDF_STORAGE_DIR/{document_id}/v{n}{ext}, hashing as it writes,
    then validate it actually parses as `file_type` and count its pages.

    Returns (file_path, sha256_hex, page_count). Raises ApiError and deletes the file if
    it does not parse as claimed."""
    ext = filetypes.extension_of(file_storage.filename)
    doc_dir = os.path.join(current_app.config["PDF_STORAGE_DIR"], str(document_id))
    os.makedirs(doc_dir, exist_ok=True)
    file_path = os.path.join(doc_dir, f"v{version_number}{ext}")

    sha256_hex = _write_to_disk(file_storage, file_path)

    try:
        page_count = _validate_and_count_pages(file_path, file_type)
    except ApiError:
        os.remove(file_path)
        raise

    return file_path, sha256_hex, page_count
