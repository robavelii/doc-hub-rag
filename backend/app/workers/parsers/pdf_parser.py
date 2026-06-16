import io

import fitz
import pdfplumber
import pytesseract
from PIL import Image

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


def parse_pdf(content: bytes) -> str:
    doc = fitz.open(stream=content, filetype="pdf")
    page_blocks: list[str] = []

    with pdfplumber.open(io.BytesIO(content)) as plumber_pdf:
        for i, page in enumerate(doc):
            header = f"[page {i + 1}]"
            parts: list[str] = [header]

            text = page.get_text("text").strip()
            if text:
                parts.append(text)

            table_rows: list[str] = []
            if i < len(plumber_pdf.pages):
                table_rows = _extract_table_rows(plumber_pdf.pages[i])
                if table_rows:
                    table_text = "\n".join(table_rows)
                    if table_text not in text:
                        parts.append(table_text)

            body = "\n".join(parts[1:])
            if len(body.strip()) < MIN_PAGE_TEXT_LEN:
                ocr = _ocr_page(page)
                if ocr:
                    parts = [header, ocr]
                    if table_rows:
                        table_text = "\n".join(table_rows)
                        if table_text not in ocr:
                            parts.append(table_text)

            block = "\n".join(parts)
            if block.strip() and block != header:
                page_blocks.append(block)

    doc.close()
    return "\n\n".join(page_blocks)
