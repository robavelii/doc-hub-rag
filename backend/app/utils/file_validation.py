import io
import os
import re
import zipfile

# Formats the ingestion pipeline can parse (see app/workers/parsers/registry.py).
SUPPORTED_TYPES = ("pdf", "docx", "pptx", "xlsx", "csv", "html", "md", "txt", "eml")

_ZIP_MARKERS = {
    "word/document.xml": "docx",
    "ppt/presentation.xml": "pptx",
    "xl/workbook.xml": "xlsx",
}
_TEXT_EXTENSIONS = {
    "md": "md",
    "markdown": "md",
    "csv": "csv",
    "tsv": "csv",
    "html": "html",
    "htm": "html",
    "eml": "eml",
    "txt": "txt",
    "text": "txt",
    "log": "txt",
    "json": "txt",
    "yaml": "txt",
    "yml": "txt",
}
_TEXT_MIME = {
    "text/markdown": "md",
    "text/csv": "csv",
    "text/html": "html",
    "message/rfc822": "eml",
    "text/plain": "txt",
}


def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return "upload.bin"
    base = os.path.basename(filename.replace("\\", "/"))
    base = re.sub(r"[^\w.\- ]", "_", base).strip("._ ")
    return base[:200] or "upload.bin"


def _extension(filename: str | None) -> str:
    return filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else ""


def _zip_type(content: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return None
    for marker, file_type in _ZIP_MARKERS.items():
        if marker in names:
            return file_type
    return None


def _is_text(content: bytes) -> bool:
    sample = content[:65536]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multi-byte character cut at the sample boundary is still text.
        if exc.start < len(sample) - 4:
            return False
    return True


def detect_file_type(content: bytes, declared_type: str | None, filename: str | None = None) -> str | None:
    """Decide the type from the bytes; the extension or MIME type only picks
    between text formats. Returns None for anything we cannot parse."""
    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(b"PK\x03\x04"):
        return _zip_type(content)
    if content and _is_text(content):
        return _TEXT_EXTENSIONS.get(_extension(filename)) or _TEXT_MIME.get((declared_type or "").split(";")[0]) or "txt"
    return None
