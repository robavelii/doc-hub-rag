import httpx
import trafilatura
from bs4 import BeautifulSoup

from app.utils.url_safety import MAX_REDIRECTS, UnsafeUrlError, validate_url_for_fetch


def parse_url(url: str) -> str:
    safe_url = validate_url_for_fetch(url)

    with httpx.Client(timeout=30, follow_redirects=False) as client:
        current_url = safe_url
        for _ in range(MAX_REDIRECTS + 1):
            response = client.get(current_url)
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    response.raise_for_status()
                if location.startswith("/"):
                    parsed = httpx.URL(current_url)
                    location = str(parsed.copy_with(path=location))
                current_url = validate_url_for_fetch(location)
                continue
            response.raise_for_status()
            html = response.text
            break
        else:
            raise UnsafeUrlError("Too many redirects")

    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    if not text:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
    return text or ""
