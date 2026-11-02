"""The file formats the policy library accepts, in one place.

Upload validation, text extraction, and the reader all have to agree on what a given
file is; keeping that in one table means adding a format is an entry here plus an
extractor, rather than three independent lists drifting apart.

Keyed on the file extension rather than the browser's mimetype. Mimetypes for these
formats are unreliable in practice: .md arrives as text/plain or text/markdown depending
on the OS, and .docx sometimes as application/octet-stream. The extension picks the
handler, and the handler then has to actually parse the file (storage.save_version), so
a renamed file is still rejected.
"""

PDF = "pdf"
DOCX = "docx"
TEXT = "text"
IMAGE = "image"

# viewer: how PolicyReaderPage displays it. "pdf" and "image" go straight into the
# browser's own viewer; "text" renders the extracted text, since nothing renders a .docx.
FILE_TYPES = {
    PDF: {
        "extensions": (".pdf",),
        "media_type": "application/pdf",
        "label": "PDF",
        "viewer": "pdf",
    },
    DOCX: {
        "extensions": (".docx",),
        "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "label": "Word document",
        "viewer": "text",
    },
    TEXT: {
        "extensions": (".txt", ".md"),
        "media_type": "text/plain; charset=utf-8",
        "label": "text file",
        "viewer": "text",
    },
    IMAGE: {
        "extensions": (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"),
        "media_type": None,  # per-extension, see media_type_for()
        "label": "scanned image",
        "viewer": "image",
    },
}

IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
}

# Formats that are recognisably a policy document but that this system can't read, mapped
# to the advice the admin gets. Better than "unsupported file type" on a .doc, where the
# fix is a 10-second "Save As" rather than a different document.
REJECTED_EXTENSIONS = {
    ".doc": "legacy .doc files can't be read; open it in Word and save it as .docx",
    ".rtf": "RTF files can't be read; open it in Word and save it as .docx or PDF",
    ".pages": "Apple Pages files can't be read; export it as .docx or PDF",
    ".odt": "OpenDocument files can't be read; save it as .docx or PDF",
}

ALLOWED_EXTENSIONS = {ext: key for key, spec in FILE_TYPES.items() for ext in spec["extensions"]}


def extension_of(filename):
    """The lowercased extension of `filename`, including the dot ("" if it has none)."""
    _, _, ext = (filename or "").rpartition(".")
    return f".{ext.lower()}" if ext else ""


def type_for_filename(filename):
    """The FILE_TYPES key for `filename`, or None if the extension isn't supported."""
    return ALLOWED_EXTENSIONS.get(extension_of(filename))


def media_type_for(file_type, file_path):
    """The Content-Type to serve this file as. Images resolve per-extension; everything
    else has one media type for the whole format."""
    if file_type == IMAGE:
        return IMAGE_MEDIA_TYPES.get(extension_of(file_path), "application/octet-stream")
    return FILE_TYPES.get(file_type, {}).get("media_type") or "application/octet-stream"


def viewer_for(file_type):
    """How the reader should display this format: "pdf", "image", or "text"."""
    return FILE_TYPES.get(file_type, {}).get("viewer", "text")


def accepted_extensions_sentence():
    """Human-readable list of what can be uploaded, for validation messages."""
    return ", ".join(sorted(ALLOWED_EXTENSIONS))
