import io
import re
import zipfile

from docx import Document

from app.workers.parsers.sections import HEADING_SEPARATOR, Section, sections_to_text, text_sections


def _parse_docx_xml_fallback(content: bytes) -> str:
    """Extract text from raw document.xml when python-docx cannot parse the file."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^/]*/>", "\t", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    xml = re.sub(r"&lt;", "<", xml)
    xml = re.sub(r"&gt;", ">", xml)
    xml = re.sub(r"&amp;", "&", xml)
    lines = [line.strip() for line in xml.splitlines() if line.strip()]
    return "\n\n".join(lines)


def parse_docx_sections(content: bytes) -> list[Section]:
    """Split on Word heading styles ("Heading 1".."Heading 6", "Title")."""
    try:
        doc = Document(io.BytesIO(content))
    except Exception:
        return text_sections(_parse_docx_xml_fallback(content))

    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        body = "\n\n".join(buffer).strip()
        if body:
            heading = HEADING_SEPARATOR.join(name for _, name in stack) or None
            sections.append(Section(text=body, heading=heading))
        buffer.clear()

    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = (paragraph.style.name if paragraph.style is not None else "") or ""
        level = 1 if style == "Title" else int(style.split()[-1]) if re.match(r"^Heading \d$", style) else None
        if level is None:
            buffer.append(text)
            continue
        flush()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))

    for table in doc.tables:
        rows = [" | ".join(c.text.strip() for c in row.cells if c.text.strip()) for row in table.rows]
        rows = [r for r in rows if r]
        if rows:
            buffer.append("\n".join(rows))
    flush()
    return sections or text_sections(_parse_docx_xml_fallback(content))


def parse_docx(content: bytes) -> str:
    return sections_to_text(parse_docx_sections(content))
