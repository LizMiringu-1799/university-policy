import logging
import re

from pypdf import PdfReader

from app.utils import filetypes
from app.rag import ocr

logger = logging.getLogger(__name__)

# Words split across a line break ("assess-\nment") come back hyphenated from pypdf and
# would otherwise embed as two fragments that match nothing.
HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
WHITESPACE = re.compile(r"\s+")

# Symbol fonts (Wingdings bullets and the like) extract as Private Use Area code points,
# which carry no meaning to the embedding model and render as mojibake in a citation.
# Control characters come out of the same badly-encoded PDFs.
JUNK = re.compile(
    r"[-\U000f0000-\U000ffffd\U00100000-\U0010fffd"  # private use areas
    r"�"  # replacement character, already-lost bytes
    r"\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"  # control chars, keeping tab/newline/return
)


class ExtractionError(Exception):
    """The document yielded no usable text. Carries the reason shown to the admin."""


def normalize(text):
    """Clean one page's raw extracted text: rejoin hyphen-broken words, strip junk
    glyphs and control characters, and collapse whitespace to single spaces."""
    text = JUNK.sub(" ", text or "")
    return WHITESPACE.sub(" ", HYPHEN_BREAK.sub(r"\1\2", text)).strip()


def _has_images(page):
    """Whether a pypdf page carries embedded images, used to decide whether a
    text-sparse page is worth sending to OCR versus genuinely blank."""
    try:
        return len(page.images) > 0
    except Exception:
        # Some encodings make pypdf throw on image enumeration. Treat as "maybe": OCR is
        # cheap insurance compared to silently indexing the page empty.
        return True


def _paginate_paragraphs(paragraphs, page_chars):
    """Group paragraph strings into pseudo-pages of about `page_chars` characters each,
    breaking between paragraphs so a page reads as a clean run of prose rather than
    being cut mid-sentence. Used for formats with no real page boundaries (Word, text).
    """
    pages = []
    current, current_len = [], 0
    for para in paragraphs:
        if current and current_len + len(para) > page_chars:
            pages.append(normalize(" ".join(current)))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para) + 1
    if current:
        pages.append(normalize(" ".join(current)))
    return [(number, text) for number, text in enumerate(pages, start=1) if text]


def _extract_pdf_pages(file_path, min_chars_per_page, ocr_enabled):
    """Native text per page, falling back to OCR page-by-page for a mixed document
    (some scanned pages, some not) rather than an all-or-nothing decision. `fitz` (the
    renderer OCR needs) is only opened if some page actually needs it."""
    reader = PdfReader(file_path)
    pages = []
    total_chars = 0
    ocr_pages = 0
    fitz_doc = None

    try:
        for page_number, page in enumerate(reader.pages, start=1):
            text = normalize(page.extract_text())
            if len(text) < min_chars_per_page and ocr_enabled and _has_images(page):
                if fitz_doc is None:
                    import fitz  # PyMuPDF

                    fitz_doc = fitz.open(file_path)
                ocr_text = normalize(ocr.ocr_pdf_page(fitz_doc, page_number - 1))
                if len(ocr_text) > len(text):
                    text = ocr_text
                    ocr_pages += 1
            total_chars += len(text)
            if text:
                pages.append((page_number, text))
    finally:
        if fitz_doc is not None:
            fitz_doc.close()

    page_count = len(reader.pages)
    if page_count and total_chars / page_count < min_chars_per_page:
        if ocr_enabled:
            raise ExtractionError(
                f"only {total_chars} characters of text across {page_count} page(s), even "
                "after OCR (the scan may be too low-resolution, skewed, or handwritten)"
            )
        raise ExtractionError(
            f"no extractable text layer across {page_count} page(s), only images "
            "(this looks like a scanned PDF; OCR is disabled — RAG_OCR_ENABLED=false)"
        )

    if ocr_pages:
        logger.info("OCR recovered text on %d of %d page(s) of %s", ocr_pages, page_count, file_path)

    return pages


def _extract_docx_pages(file_path, page_chars):
    """Paragraphs and table rows, in document order, paginated into pseudo-pages."""
    from docx import Document as DocxDocument

    document = DocxDocument(file_path)
    paragraphs = []
    for para in document.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))

    if not paragraphs:
        raise ExtractionError("the document has no readable paragraphs or tables")

    return _paginate_paragraphs(paragraphs, page_chars)


def _extract_text_pages(file_path, page_chars):
    """Plain text or markdown, split on blank lines into paragraphs, then paginated the
    same way as Word docs. Markdown syntax (#, *, etc.) is left in place rather than
    parsed — it costs a little embedding noise, not worth a Markdown dependency for."""
    with open(file_path, "rb") as f:
        raw = f.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("utf-8", errors="replace")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if not paragraphs:
        raise ExtractionError("the file is empty")

    return _paginate_paragraphs(paragraphs, page_chars)


def _extract_image_pages(file_path, ocr_enabled):
    """A single uploaded image, OCR'd as the document's one page."""
    if not ocr_enabled:
        raise ExtractionError("OCR is disabled (RAG_OCR_ENABLED=false), so images can't be indexed")
    text = normalize(ocr.ocr_image(file_path))
    if not text:
        raise ExtractionError("OCR found no recognizable text in this image")
    return [(1, text)]


def extract_pages(file_path, file_type, min_chars_per_page, page_chars, ocr_enabled=True):
    """Return [(page_number, text)] for pages/pseudo-pages that have text, 1-based.

    Raises ExtractionError when there is too little text to index. Failing here is
    deliberate: the alternative is a document that indexes to zero chunks and is
    silently unanswerable.
    """
    if file_type == filetypes.PDF:
        return _extract_pdf_pages(file_path, min_chars_per_page, ocr_enabled)
    if file_type == filetypes.DOCX:
        return _extract_docx_pages(file_path, page_chars)
    if file_type == filetypes.TEXT:
        return _extract_text_pages(file_path, page_chars)
    if file_type == filetypes.IMAGE:
        return _extract_image_pages(file_path, ocr_enabled)
    raise ExtractionError(f"unsupported file type: {file_type}")
