"""Structure-aware parsing for every supported format, using files built in memory."""

import io

import pytest

from app.utils.file_validation import detect_file_type
from app.workers.parsers.registry import parse_sections
from app.workers.parsers.sections import chunk_sections, markdown_sections


def _docx() -> bytes:
    from docx import Document

    doc = Document()
    doc.add_heading("Employee Handbook", level=0)
    doc.add_heading("Paid Time Off", level=1)
    doc.add_paragraph("Employees accrue 25 days of vacation.")
    doc.add_heading("Sick leave", level=2)
    doc.add_paragraph("Sick leave is unlimited for short illnesses.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pptx() -> bytes:
    from pptx import Presentation

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Q3 Roadmap"
    slide.placeholders[1].text = "Launch SSO in September"
    slide.notes_slide.notes_text_frame.text = "Mention the pilot customers"
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = "Hiring"
    slide.placeholders[1].text = "Two backend engineers"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _xlsx() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Price list"
    ws.append(["Plan", "Price", "Users"])
    ws.append(["Starter", "49 USD", 3])
    ws.append(["Growth", "149 USD", 15])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


EML = (
    b"From: Ana <ana@example.com>\r\nTo: team@example.com\r\nSubject: Office closure\r\n"
    b"Date: Mon, 3 Nov 2026 09:00:00 +0000\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
    b"The Lisbon office is closed on Friday for maintenance.\r\n"
)
HTML = (
    b"<html><head><title>FAQ</title><script>track()</script></head><body><nav>Home | About</nav>"
    b"<main><h1>Billing FAQ</h1><h2>Refunds</h2><p>Annual plans can be refunded within the first 60 days "
    b"of the subscription, on a prorated basis, by contacting our billing team.</p><h2>Payment methods</h2>"
    b"<p>We accept Visa, Mastercard and American Express for all plans and all currencies.</p></main>"
    b"<footer>Copyright</footer></body></html>"
)
MARKDOWN = b"# Runbook\n\nIntro.\n\n## Rollback\n\nRun `ship rollback`.\n\n```\n# not a heading\n```\n\n### Database\n\nNo automatic rollback."


@pytest.mark.parametrize(
    ("content", "filename", "declared", "expected"),
    [
        (b"%PDF-1.4 ...", "a.pdf", "application/pdf", "pdf"),
        (None, "a.docx", None, "docx"),
        (None, "a.pptx", None, "pptx"),
        (None, "a.xlsx", None, "xlsx"),
        (b"Plan,Price\nStarter,49\n", "prices.csv", "text/csv", "csv"),
        (MARKDOWN, "runbook.md", "application/octet-stream", "md"),
        (HTML, "faq.html", "text/html", "html"),
        (EML, "mail.eml", "message/rfc822", "eml"),
        ("Café menu: crème brûlée".encode(), "menu.txt", "application/octet-stream", "txt"),
        (b"PK\x03\x04garbage", "x.zip", None, None),
        (b"\x00\x01\x02binary", "x.bin", None, None),
    ],
)
def test_detect_file_type(content, filename, declared, expected):
    if content is None:
        content = {"docx": _docx, "pptx": _pptx, "xlsx": _xlsx}[expected]()
    assert detect_file_type(content, declared, filename) == expected


def test_utf8_text_without_declared_type_is_accepted():
    # Previously rejected: only pure-ASCII text was recognised unless the browser said text/plain.
    assert detect_file_type("Nairobi – Kenya".encode(), None, "notes.txt") == "txt"


def test_markdown_heading_paths_skip_title_and_code_blocks():
    sections = markdown_sections(MARKDOWN.decode())
    assert [(s.heading, s.text) for s in sections] == [
        ("Runbook", "Intro."),
        ("Rollback", "Run `ship rollback`.\n\n```\n# not a heading\n```"),
        ("Rollback > Database", "No automatic rollback."),
    ]


def test_docx_sections_follow_heading_styles():
    sections = parse_sections("docx", _docx())
    # Like a single markdown H1, the document Title is not repeated in every path.
    assert [s.heading for s in sections] == ["Paid Time Off", "Paid Time Off > Sick leave"]
    assert "25 days" in sections[0].text


def test_pptx_one_section_per_slide_with_notes():
    sections = parse_sections("pptx", _pptx())
    assert [(s.heading, s.page) for s in sections] == [("Q3 Roadmap", 1), ("Hiring", 2)]
    assert "Launch SSO" in sections[0].text and "pilot customers" in sections[0].text


def test_xlsx_rows_keep_column_names():
    sections = parse_sections("xlsx", _xlsx())
    assert sections[0].heading == "Price list"
    assert "Plan: Growth; Price: 149 USD; Users: 15" in sections[0].text


def test_csv_rows_keep_column_names():
    sections = parse_sections("csv", b"Plan;Price\nStarter;49\nGrowth;149\n")
    assert sections[0].text.splitlines() == ["Plan: Starter; Price: 49", "Plan: Growth; Price: 149"]


def test_html_keeps_main_content_and_headings():
    sections = parse_sections("html", HTML)
    text = "\n".join(f"{s.heading}: {s.text}" for s in sections)
    assert "Refunds" in text and "60 days" in text
    assert "track()" not in text and "Home | About" not in text


def test_eml_subject_is_heading_and_headers_are_kept():
    (section,) = parse_sections("eml", EML)
    assert section.heading == "Office closure"
    assert "From: Ana" in section.text and "closed on Friday" in section.text


def test_chunks_carry_heading_prefix_and_metadata():
    sections = markdown_sections("# Doc\n\n## Leave\n\n" + ("Leave paragraph. " * 120))
    chunks = chunk_sections(sections, chunk_size=400, chunk_overlap=50)
    assert len(chunks) > 1
    assert all(c.text.startswith("Leave\n") for c in chunks)
    assert all(c.metadata == {"heading": "Leave"} for c in chunks)
    assert all(len(c.text) <= 400 for c in chunks)


def test_unknown_type_is_rejected():
    with pytest.raises(ValueError):
        parse_sections("exe", b"MZ")
