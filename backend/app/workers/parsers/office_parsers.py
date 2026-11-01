"""PowerPoint, Excel and CSV."""

import csv
import io

from app.workers.parsers.sections import Section

ROWS_PER_SECTION = 25


def parse_pptx_sections(content: bytes) -> list[Section]:
    """One section per slide: title as heading, slide number as page, speaker notes included."""
    from pptx import Presentation

    presentation = Presentation(io.BytesIO(content))
    sections = []
    for number, slide in enumerate(presentation.slides, start=1):
        title_shape = slide.shapes.title
        title = title_shape.text_frame.text.strip() if title_shape is not None and title_shape.has_text_frame else None
        parts = []
        for shape in slide.shapes:
            if shape is title_shape:
                continue
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text.strip())
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        parts.append(" | ".join(cells))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            parts.append("Notes: " + slide.notes_slide.notes_text_frame.text.strip())
        body = "\n".join(parts).strip()
        if body or title:
            sections.append(Section(text=body or title, heading=title or f"Slide {number}", page=number))
    return sections


def _rows_to_sections(rows: list[list[str]], heading: str | None) -> list[Section]:
    """Rows become "Column: value; ..." lines, so each chunk keeps its column names."""
    rows = [[str(c).strip() if c is not None else "" for c in row] for row in rows]
    rows = [row for row in rows if any(row)]
    if not rows:
        return []
    header, data = rows[0], rows[1:]
    if not data:
        return [Section(text=" | ".join(c for c in header if c), heading=heading)]
    columns = [h or f"column {i + 1}" for i, h in enumerate(header)]
    lines = [
        "; ".join(f"{columns[i] if i < len(columns) else f'column {i + 1}'}: {v}" for i, v in enumerate(row) if v)
        for row in data
    ]
    return [
        Section(text="\n".join(lines[i : i + ROWS_PER_SECTION]), heading=heading)
        for i in range(0, len(lines), ROWS_PER_SECTION)
    ]


def parse_xlsx_sections(content: bytes) -> list[Section]:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sections: list[Section] = []
    for sheet in workbook.worksheets:
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        sections.extend(_rows_to_sections(rows, heading=sheet.title))
    workbook.close()
    return sections


def parse_csv_sections(content: bytes) -> list[Section]:
    text = content.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    return _rows_to_sections(rows, heading=None)
