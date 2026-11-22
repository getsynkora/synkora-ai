"""
Limits for turning an uploaded document into text.

A small upload can unpack into something enormous: an Office file is a zip whose XML can compress 300:1, and a PDF
can hold thousands of pages. These checks run before parsing, and the extraction stops at a text cap, so a 100 KB
file cannot freeze a worker or exhaust its memory.
"""

import io
import zipfile

MAX_UNPACKED_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2000
MAX_COMPRESSION_RATIO = 100


class DocumentLimitError(ValueError):
    """The document is too large or too complex to process. The message is safe to show to the caller."""


def check_office_archive(content: bytes, max_unpacked: int = MAX_UNPACKED_BYTES) -> None:
    """Refuse a zip-based document (DOCX, XLSX, PPTX) that would unpack to too much data."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise DocumentLimitError("The document is damaged or not a valid Office file") from None
    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise DocumentLimitError("The document contains too many parts")
        unpacked = sum(entry.file_size for entry in entries)
        if unpacked > max_unpacked:
            raise DocumentLimitError("The document is too large when unpacked")
        if unpacked > MAX_COMPRESSION_RATIO * max(len(content), 1):
            raise DocumentLimitError("The document is compressed too heavily to process safely")


def docx_text(content: bytes, max_chars: int, max_unpacked: int = MAX_UNPACKED_BYTES) -> str:
    """Text of a DOCX, checked first and stopped at ``max_chars``."""
    check_office_archive(content, max_unpacked)
    import docx

    parts: list[str] = []
    size = 0
    for paragraph in docx.Document(io.BytesIO(content)).paragraphs:
        text = paragraph.text
        if text.strip():
            parts.append(text)
            size += len(text) + 2
            if size >= max_chars:
                break
    return "\n\n".join(parts)[:max_chars]


def pdf_text_pymupdf(content: bytes, max_pages: int, max_chars: int) -> str:
    """Text of a PDF with PyMuPDF, refusing more than ``max_pages`` pages and stopping at ``max_chars``."""
    import fitz

    document = fitz.open(stream=content, filetype="pdf")
    try:
        if document.page_count > max_pages:
            raise DocumentLimitError(f"The PDF has more than {max_pages} pages")
        parts: list[str] = []
        size = 0
        for page in document:
            text = page.get_text()
            parts.append(text)
            size += len(text) + 1
            if size >= max_chars:
                break
        return "\n".join(parts)[:max_chars]
    finally:
        document.close()


def pdf_text_pypdf(content: bytes, max_pages: int, max_chars: int) -> str:
    """Text of a PDF with pypdf, refusing more than ``max_pages`` pages and stopping at ``max_chars``."""
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(content))
    if len(reader.pages) > max_pages:
        raise DocumentLimitError(f"The PDF has more than {max_pages} pages")
    parts: list[str] = []
    size = 0
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text()
        except Exception:
            continue
        if text and text.strip():
            parts.append(f"--- Page {number} ---\n{text}")
            size += len(parts[-1]) + 2
            if size >= max_chars:
                break
    return "\n\n".join(parts)[:max_chars]
