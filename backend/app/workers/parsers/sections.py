"""Structure-aware document representation and chunking.

Parsers return `Section`s (text plus where it came from: heading path, page or
slide). The chunker splits each section on its own, never across a heading
boundary, and prefixes every chunk with its heading so both the embedding and
the full-text index know what the passage is about ("Paid Time Off > Sick
leave" instead of an orphaned paragraph). Heading and page travel with the
chunk as metadata for citations.
"""

import re
from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Evals (structure-aware): 1200→0.943, 800→0.953, 600→0.962 hit@1. 800 keeps longer
# real-world sections from fragmenting while capturing most of the gain.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
HEADING_SEPARATOR = " > "


@dataclass
class Section:
    text: str
    heading: str | None = None
    page: int | None = None


@dataclass
class ChunkDraft:
    text: str
    metadata: dict = field(default_factory=dict)


_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def markdown_sections(text: str) -> list[Section]:
    """Split markdown on headings. A single leading H1 is the document title and
    is not repeated in every heading path."""
    lines = text.splitlines()
    h1_count, fenced = 0, False
    for line in lines:
        if line.strip().startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"^#\s+", line):
            h1_count += 1
    stack: list[tuple[int, str]] = []
    sections: list[Section] = []
    buffer: list[str] = []

    def heading_path() -> str | None:
        names = [name for level, name in stack if not (level == 1 and h1_count == 1 and len(stack) > 1)]
        return HEADING_SEPARATOR.join(names) or None

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append(Section(text=body, heading=heading_path()))
        buffer.clear()

    in_code = False
    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
        match = None if in_code else _MD_HEADING.match(line)
        if match:
            flush()
            level, name = len(match.group(1)), match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, name))
        else:
            buffer.append(line)
    flush()
    return sections


def text_sections(text: str) -> list[Section]:
    return [Section(text=text.strip())] if text.strip() else []


def sections_to_text(sections: list[Section]) -> str:
    return "\n\n".join(s.text for s in sections)


def chunk_sections(
    sections: list[Section], chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP
) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for section in sections:
        body = section.text.strip()
        if not body:
            continue
        prefix = f"{section.heading}\n" if section.heading else ""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(200, chunk_size - len(prefix)),
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        metadata = {k: v for k, v in (("heading", section.heading), ("page", section.page)) if v is not None}
        drafts.extend(ChunkDraft(text=prefix + piece, metadata=dict(metadata)) for piece in splitter.split_text(body))
    return drafts
