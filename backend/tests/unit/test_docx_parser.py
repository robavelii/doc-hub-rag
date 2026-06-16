from pathlib import Path

from app.workers.parsers.docx_parser import parse_docx

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_sample_docx_extracts_requirements_language():
    text = parse_docx((FIXTURES / "sample.docx").read_bytes())
    assert "Doc-Hub" in text
    assert len(text) > 10
