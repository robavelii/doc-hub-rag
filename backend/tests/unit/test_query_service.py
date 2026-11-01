import pytest

from app.services import query_service
from app.services.citations import StreamingCitationRewriter, rewrite_citations
from app.services.query_service import CONTEXT_CHUNK_COUNT, SYSTEM_PROMPT, build_context
from app.services.retrieval import RetrievedChunk, reciprocal_rank_fusion
from app.services.vector_service import build_or_tsquery


def test_system_prompt_requires_concise_numbered_citations():
    assert "directly and concisely" in SYSTEM_PROMPT
    assert "[1]" in SYSTEM_PROMPT
    assert "source:" not in SYSTEM_PROMPT


def test_context_chunk_count():
    assert CONTEXT_CHUNK_COUNT == 6


def _chunk(cid: str, text: str = "text", **meta) -> RetrievedChunk:
    return RetrievedChunk(id=cid, doc_id="d", filename="f.md", text=text, chunk_index=0, score=0.0, metadata=meta)


def test_build_context_numbers_passages_and_includes_location():
    context, used = build_context([_chunk("a", heading="Paid Time Off", page=3), _chunk("b")])
    assert context.startswith("[1] (from f.md · Paid Time Off · page 3):\ntext")
    assert "[2] (from f.md):" in context
    assert [c.id for c in used] == ["a", "b"]


def test_build_context_respects_size_budget():
    big = "x" * 4000
    _, used = build_context([_chunk("a", big), _chunk("b", big), _chunk("c", big)])
    assert len(used) == 1


def test_rrf_rewards_agreement_between_retrievers():
    vector = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    text = [{"id": "c"}, {"id": "d"}]
    fused = [c["id"] for c, _ in reciprocal_rank_fusion(vector, text)]
    assert fused[0] == "c"  # found by both
    assert set(fused) == {"a", "b", "c", "d"}


def test_or_tsquery_is_sanitized():
    assert build_or_tsquery("What's the refund-policy? DROP TABLE;") == "what | the | refund | policy | drop | table"
    assert build_or_tsquery("!!! ?") == ""


def test_rewrite_citations_maps_numbers_to_chunk_ids():
    mapping = {1: "id-1", 2: "id-2"}
    assert rewrite_citations("A [1]. B [2][1].", mapping) == "A [source:id-1]. B [source:id-2][source:id-1]."
    assert rewrite_citations("C [1, 2].", mapping) == "C [source:id-1][source:id-2]."
    assert rewrite_citations("unknown [9] dropped", mapping) == "unknown  dropped"
    assert rewrite_citations("array[i] stays? [x]", mapping) == "array[i] stays? [x]"


def test_streaming_rewriter_handles_markers_split_across_deltas():
    rw = StreamingCitationRewriter({1: "id-1", 12: "id-12"})
    out = "".join(rw.feed(d) for d in ["The answer", " is 30 days [", "1", "]. Also [1", "2]."]) + rw.flush()
    assert out == "The answer is 30 days [source:id-1]. Also [source:id-12]."


def test_streaming_rewriter_releases_unclosed_bracket_on_flush():
    rw = StreamingCitationRewriter({1: "id-1"})
    out = rw.feed("ends with [") + rw.flush()
    assert out == "ends with ["


@pytest.mark.asyncio
async def test_follow_up_query_includes_previous_topic_without_llm(monkeypatch):
    history = [
        {"role": "user", "content": "What is the parental leave policy?"},
        {"role": "assistant", "content": "20 weeks."},
    ]
    query = await query_service.build_search_query("Is it paid?", history)
    assert "parental leave" in query
    assert "Is it paid?" in query
    assert await query_service.build_search_query("standalone question", []) == "standalone question"


@pytest.fixture
def corpus_version(monkeypatch):
    state = {"v": 0}

    async def fake_version(_tenant_id):
        return state["v"]

    monkeypatch.setattr(query_service, "get_corpus_version", fake_version)
    return state


@pytest.mark.asyncio
async def test_cache_key_changes_when_documents_change(corpus_version):
    before = await query_service.build_cache_key("t1", "What is the refund policy?", [])
    corpus_version["v"] = 1
    after = await query_service.build_cache_key("t1", "What is the refund policy?", [])
    assert before != after


@pytest.mark.asyncio
async def test_cache_key_depends_on_conversation_context(corpus_version):
    fresh = await query_service.build_cache_key("t1", "what about the second one?", [])
    followup = await query_service.build_cache_key(
        "t1", "what about the second one?", [{"role": "user", "content": "list our plans"}]
    )
    assert fresh != followup


@pytest.mark.asyncio
async def test_cache_key_is_tenant_scoped_and_normalized(corpus_version):
    a = await query_service.build_cache_key("t1", "Refund   policy?", None)
    assert a == await query_service.build_cache_key("t1", "refund policy?", [])
    assert a != await query_service.build_cache_key("t2", "refund policy?", [])


@pytest.mark.asyncio
async def test_cache_key_survives_redis_outage(monkeypatch):
    async def broken(_tenant_id):
        raise ConnectionError("redis down")

    monkeypatch.setattr(query_service, "get_corpus_version", broken)
    assert await query_service.build_cache_key("t1", "q", [])


def test_prompt_token_count_includes_context_and_history():
    class WordCounter:
        def count_tokens(self, text):
            return len(text.split())

    messages = [
        {"role": "system", "content": "context " * 500},
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
        {"role": "user", "content": "new question"},
    ]
    total = query_service.count_prompt_tokens(WordCounter(), messages)
    assert total == 500 + 2 + 2 + 2 + 4 * query_service.TOKENS_PER_MESSAGE
