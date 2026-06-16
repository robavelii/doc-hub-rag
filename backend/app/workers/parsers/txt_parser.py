def parse_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="ignore")
