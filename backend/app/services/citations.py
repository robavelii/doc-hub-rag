"""Numbered citations.

The model cites context blocks as [1], [2] (short tokens it copies reliably)
instead of 36-character UUIDs. Before text reaches a client, numbers are
rewritten to the `[source:<chunk_id>]` markers the frontends render.
"""

import re

CITATION_RE = re.compile(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]")
# Longest marker we may need to hold back while streaming, e.g. "[12, 13, 14]".
_MAX_PENDING = 24


def rewrite_citations(text: str, citation_map: dict[int, str]) -> str:
    def replace(match: re.Match) -> str:
        ids = [citation_map.get(int(n)) for n in re.split(r"\s*,\s*", match.group(1))]
        tags = [f"[source:{cid}]" for cid in ids if cid]
        return "".join(tags)

    return CITATION_RE.sub(replace, text)


class StreamingCitationRewriter:
    """Rewrites citations in streamed deltas, holding back a possibly unfinished `[..`."""

    def __init__(self, citation_map: dict[int, str]) -> None:
        self._map = citation_map
        self._pending = ""

    def feed(self, delta: str) -> str:
        text = self._pending + delta
        cut = text.rfind("[")
        if cut != -1 and "]" not in text[cut:] and len(text) - cut <= _MAX_PENDING:
            self._pending = text[cut:]
            text = text[:cut]
        else:
            self._pending = ""
        return rewrite_citations(text, self._map)

    def flush(self) -> str:
        text, self._pending = self._pending, ""
        return rewrite_citations(text, self._map)
