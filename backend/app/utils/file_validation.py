import os
import re

MAGIC_SIGNATURES: dict[str, bytes] = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",
    "txt": b"",
}

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return "upload.bin"
    base = os.path.basename(filename.replace("\\", "/"))
    base = re.sub(r"[^\w.\- ]", "_", base).strip("._ ")
    return base[:200] or "upload.bin"


def detect_file_type(content: bytes, declared_type: str | None) -> str | None:
    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(b"PK\x03\x04"):
        return "docx"
    if declared_type == "text/plain" or (content and all(b < 128 for b in content[:512])):
        return "txt"
    return None
