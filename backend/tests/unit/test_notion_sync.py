from app.workers import sync_task
from app.workers.sync_task import extract_notion_text, extract_page_title, fetch_block_tree


def _para(text, **extra):
    return {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": text}]}, **extra}


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeNotion:
    """Serves block children in pages of one result to exercise pagination."""

    def __init__(self, children: dict[str, list[dict]]):
        self.children = children
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, params=None):
        self.calls.append((url, params or {}))
        block_id = url.split("/blocks/")[1].split("/")[0]
        items = self.children.get(block_id, [])
        start = int((params or {}).get("start_cursor") or 0)
        page = items[start : start + 1]
        has_more = start + 1 < len(items)
        return FakeResponse({"results": page, "has_more": has_more, "next_cursor": str(start + 1) if has_more else None})

    def post(self, url, json=None):
        self.calls.append((url, json or {}))
        start = int((json or {}).get("start_cursor") or 0)
        pages = [{"id": f"page{i}"} for i in range(3)]
        page = pages[start : start + 1]
        has_more = start + 1 < len(pages)
        return FakeResponse({"results": page, "has_more": has_more, "next_cursor": str(start + 1) if has_more else None})


def test_title_from_plain_page():
    page = {"properties": {"title": {"id": "title", "type": "title", "title": [{"plain_text": "Handbook"}]}}}
    assert extract_page_title(page) == "Handbook"


def test_title_from_database_page_with_custom_property_name():
    page = {
        "properties": {
            "Status": {"type": "select", "select": {"name": "Done"}},
            "Name": {"type": "title", "title": [{"plain_text": "Q3 "}, {"plain_text": "Plan"}]},
        }
    }
    assert extract_page_title(page) == "Q3 Plan"


def test_title_missing_falls_back():
    assert extract_page_title({}) == "Untitled"
    assert extract_page_title({"properties": {"title": {"type": "title", "title": []}}}) == "Untitled"


def test_block_tree_paginates_and_recurses():
    client = FakeNotion(
        {
            "root": [_para("one"), _para("two", has_children=True, id="b2"), _para("three")],
            "b2": [_para("nested a"), _para("nested b")],
        }
    )
    blocks = fetch_block_tree(client, "root")
    text = extract_notion_text(blocks)
    assert text.split("\n\n") == ["one", "two", "  nested a", "  nested b", "three"]


def test_child_pages_are_not_walked_inline():
    client = FakeNotion(
        {"root": [{"type": "child_page", "id": "p2", "has_children": True, "child_page": {"title": "Sub page"}}]}
    )
    blocks = fetch_block_tree(client, "root")
    assert extract_notion_text(blocks) == "Sub page"
    assert all("/blocks/p2/" not in url for url, _ in client.calls)


def test_search_pagination_yields_every_page():
    client = FakeNotion({})
    pages = list(sync_task._paginate(client, "POST", "https://api.notion.com/v1/search", {"filter": {}}))
    assert [p["id"] for p in pages] == ["page0", "page1", "page2"]


def test_table_rows_are_extracted():
    row = {"type": "table_row", "table_row": {"cells": [[{"plain_text": "Plan"}], [{"plain_text": "Price"}]]}}
    assert extract_notion_text([row]) == "Plan | Price"
