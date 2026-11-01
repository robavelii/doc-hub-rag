import io

import pdfplumber
import pymupdf as fitz
import pytesseract
from PIL import Image

from app.workers.parsers.sections import Section

MIN_PAGE_TEXT_LEN = 30


def _ocr_page(page: fitz.Page) -> str:
    pix = page.get_pixmap(dpi=200)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return pytesseract.image_to_string(img).strip()


def _extract_table_rows(plumber_page) -> list[str]:
    rows: list[str] = []
    for table in plumber_page.extract_tables() or []:
        for row in table:
            cells = [str(cell).strip() if cell is not None else "" for cell in row]
            cells = [cell for cell in cells if cell]
            if cells:
                rows.append(" | ".join(cells))
    return rows


def parse_pdf_sections(content: bytes) -> list[Section]:
    """One section per page, carrying the page number for citations."""
    doc = fitz.open(stream=content, filetype="pdf")
    sections: list[Section] = []
    with pdfplumber.open(io.BytesIO(content)) as plumber_pdf:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            table_rows = _extract_table_rows(plumber_pdf.pages[i]) if i < len(plumber_pdf.pages) else []
            table_text = "\n".join(table_rows)
            parts = [text] if text else []
            if table_text and table_text not in text:
                parts.append(table_text)
            if len("\n".join(parts).strip()) < MIN_PAGE_TEXT_LEN:
                ocr = _ocr_page(page)
                if ocr:
                    parts = [ocr] + ([table_text] if table_text and table_text not in ocr else [])
            body = "\n".join(parts).strip()
            if body:
                sections.append(Section(text=body, page=i + 1))
    doc.close()
    return sections


def parse_pdf(content: bytes) -> str:
    return "\n\n".join(f"[page {s.page}]\n{s.text}" for s in parse_pdf_sections(content))
