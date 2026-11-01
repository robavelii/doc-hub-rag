"""HTML, Markdown, plain text and email."""

import email
import email.policy

import trafilatura
from bs4 import BeautifulSoup

from app.workers.parsers.sections import Section, markdown_sections, text_sections


def decode_text(content: bytes) -> str:
    return content.decode("utf-8-sig", errors="replace")


def parse_markdown_sections(content: bytes) -> list[Section]:
    return markdown_sections(decode_text(content))


def parse_txt_sections(content: bytes) -> list[Section]:
    return text_sections(decode_text(content))


def html_to_sections(html: str) -> list[Section]:
    """Main content as markdown (keeps headings and tables), boilerplate removed."""
    extracted = trafilatura.extract(html, include_comments=False, include_tables=True, output_format="markdown")
    if extracted:
        return markdown_sections(extracted)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return text_sections(soup.get_text(separator="\n"))


def parse_html_sections(content: bytes) -> list[Section]:
    return html_to_sections(decode_text(content))


def parse_eml_sections(content: bytes) -> list[Section]:
    message = email.message_from_bytes(content, policy=email.policy.default)
    subject = str(message.get("subject", "")).strip() or "Email"
    header = "\n".join(f"{name}: {message[name]}" for name in ("From", "To", "Date") if message.get(name))

    body_part = message.get_body(preferencelist=("plain", "html"))
    body = ""
    if body_part is not None:
        body = body_part.get_content()
        if body_part.get_content_type() == "text/html":
            body = "\n\n".join(s.text for s in html_to_sections(body))
    text = f"{header}\n\n{body.strip()}".strip()
    return [Section(text=text, heading=subject)] if text else []
