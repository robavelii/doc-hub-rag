from pathlib import Path

from app.workers.parsers.docx_parser import parse_docx
from app.workers.parsers.pdf_parser import parse_pdf

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_sample_pdf_extracts_text():
    content = (FIXTURES / "sample.pdf").read_bytes()
    text = parse_pdf(content)
    assert "[page 1]" in text
    assert "Doc-Hub" in text or "Hello" in text


def test_parse_sample_docx_extracts_text():
    content = (FIXTURES / "sample.docx").read_bytes()
    text = parse_docx(content)
    assert "Doc-Hub" in text
    assert "DOCX" in text
