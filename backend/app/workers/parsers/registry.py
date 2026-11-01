"""File type → section parser."""

from collections.abc import Callable

from app.workers.parsers.docx_parser import parse_docx_sections
from app.workers.parsers.office_parsers import parse_csv_sections, parse_pptx_sections, parse_xlsx_sections
from app.workers.parsers.pdf_parser import parse_pdf_sections
from app.workers.parsers.sections import Section
from app.workers.parsers.web_parsers import (
    parse_eml_sections,
    parse_html_sections,
    parse_markdown_sections,
    parse_txt_sections,
)

PARSERS: dict[str, Callable[[bytes], list[Section]]] = {
    "pdf": parse_pdf_sections,
    "docx": parse_docx_sections,
    "pptx": parse_pptx_sections,
    "xlsx": parse_xlsx_sections,
    "csv": parse_csv_sections,
    "html": parse_html_sections,
    "md": parse_markdown_sections,
    "txt": parse_txt_sections,
    "eml": parse_eml_sections,
}


def parse_sections(file_type: str, content: bytes) -> list[Section]:
    parser = PARSERS.get(file_type)
    if parser is None:
        raise ValueError(f"No parser for type: {file_type}")
    return parser(content)
