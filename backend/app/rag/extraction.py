import re

from pypdf import PdfReader

# Words split across a line break ("assess-\nment") come back hyphenated from pypdf and
# would otherwise embed as two fragments that match nothing.
HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
WHITESPACE = re.compile(r"\s+")

# Symbol fonts (Wingdings bullets and the like) extract as Private Use Area code points,
# which carry no meaning to the embedding model and render as mojibake in a citation.
# Control characters come out of the same badly-encoded PDFs.
JUNK = re.compile(
    r"[-\U000f0000-\U000ffffd\U00100000-\U0010fffd"  # private use areas
    r"�"  # replacement character, already-lost bytes
    r"\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"  # control chars, keeping tab/newline/return
)


class ExtractionError(Exception):
    """The PDF yielded no usable text. Carries the reason shown to the admin."""


def normalize(text):
    text = JUNK.sub(" ", text or "")
    return WHITESPACE.sub(" ", HYPHEN_BREAK.sub(r"\1\2", text)).strip()


def _has_images(reader, sample_pages=3):
    for page in reader.pages[:sample_pages]:
        try:
            if len(page.images):
                return True
        except Exception:
            # Some encodings make pypdf throw on image enumeration. Only used to word the
            # error message, so an unreadable answer is not worth failing extraction over.
            continue
    return False


def extract_pages(file_path, min_chars_per_page):
    """Return [(page_number, text)] for pages that have text, 1-based.

    Raises ExtractionError when there is too little text to index. Failing here is
    deliberate: the alternative is a document that indexes to zero chunks and is
    silently unanswerable. The message distinguishes a scanned PDF from an empty one,
    because the fix differs: one needs OCR, the other needs a real file uploading.
    """
    reader = PdfReader(file_path)
    pages = []
    total_chars = 0

    for page_number, page in enumerate(reader.pages, start=1):
        text = normalize(page.extract_text())
        total_chars += len(text)
        if text:
            pages.append((page_number, text))

    page_count = len(reader.pages)
    if page_count and total_chars / page_count < min_chars_per_page:
        if _has_images(reader):
            raise ExtractionError(
                f"no extractable text layer across {page_count} page(s), only images "
                "(this looks like a scanned PDF; OCR is out of scope)"
            )
        raise ExtractionError(
            f"only {total_chars} characters of text across {page_count} page(s) "
            "(the PDF looks blank or malformed)"
        )

    return pages
