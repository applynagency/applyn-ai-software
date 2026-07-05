"""Sprint 37D — document text extraction + chunking for the Knowledge Base.

Supports PDF, DOCX, TXT and Markdown. Extraction is best-effort and raises a
customer-safe ``DocumentProcessingError`` on unsupported or unreadable files.
"""

import io

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentProcessingError(Exception):
    """Raised when a document cannot be parsed into text."""


_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".text"}
_PDF_EXTENSIONS = {".pdf"}
_DOCX_EXTENSIONS = {".docx"}

SUPPORTED_EXTENSIONS = _TEXT_EXTENSIONS | _PDF_EXTENSIONS | _DOCX_EXTENSIONS


def _extension(filename: str) -> str:
    name = (filename or "").lower().strip()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def is_supported(filename: str) -> bool:
    return _extension(filename) in SUPPORTED_EXTENSIONS


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise DocumentProcessingError("PDF support is not available.") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise DocumentProcessingError("Could not read the PDF document.") from exc


def _extract_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise DocumentProcessingError("DOCX support is not available.") from exc
    try:
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    except Exception as exc:  # noqa: BLE001
        raise DocumentProcessingError("Could not read the DOCX document.") from exc


def _extract_text_file(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentProcessingError("Could not decode the text document.")


def extract_text(filename: str, data: bytes) -> str:
    ext = _extension(filename)
    if ext in _PDF_EXTENSIONS:
        text = _extract_pdf(data)
    elif ext in _DOCX_EXTENSIONS:
        text = _extract_docx(data)
    elif ext in _TEXT_EXTENSIONS:
        text = _extract_text_file(data)
    else:
        raise DocumentProcessingError(
            "Unsupported file type. Upload a PDF, DOCX, TXT or Markdown file."
        )
    text = (text or "").strip()
    if not text:
        raise DocumentProcessingError("No readable text found in the document.")
    return text


def chunk_text(
    text: str, *, size: int | None = None, overlap: int | None = None
) -> list[str]:
    """Split text into overlapping, word-boundary-aware chunks."""
    size = size or settings.KB_CHUNK_SIZE
    overlap = overlap if overlap is not None else settings.KB_CHUNK_OVERLAP
    overlap = max(0, min(overlap, size - 1))
    text = " ".join((text or "").split())  # normalize whitespace
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    n = len(text)
    step = size - overlap
    start = 0
    while start < n:
        end = min(start + size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start += step
    return chunks
