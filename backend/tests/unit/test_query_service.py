import pytest

from app.services import query_service
from app.services.query_service import (
    CONTEXT_CHUNK_COUNT,
    SYSTEM_PROMPT,
    _compute_confidence,
    _expand_search_terms,
    _query_terms,
)


def test_query_terms_strips_stopwords():
    terms = _query_terms("what is the refund policy")
    assert "what" not in terms
    assert "the" not in terms
    assert terms == ["refund", "policy"]


def test_expand_search_terms_has_no_corpus_specific_synonyms():
    assert _expand_search_terms(["balance", "name"]) == ["balance", "name"]
    assert len(_expand_search_terms([f"t{i}" for i in range(30)])) == 12


def test_system_prompt_requires_concise_answer():
    assert "directly and concisely" in SYSTEM_PROMPT
    assert "UNVRS" not in SYSTEM_PROMPT


def test_context_chunk_count_increased():
    assert CONTEXT_CHUNK_COUNT == 6


def test_compute_confidence_uses_vector_scores_when_not_mock():
    top_chunks = [
        ({"score": 0.82, "metadata": {"text": "a"}}, 0.9),
        ({"score": 0.71, "metadata": {"text": "b"}}, 0.8),
    ]
    confidence = _compute_confidence(top_chunks, use_mock_scoring=False)
    assert 0.45 <= confidence <= 0.92


def test_compute_confidence_low_when_vectors_weak():
    top_chunks = [
        ({"score": 0.12, "metadata": {"text": "a"}}, 0.3),
    ]
    confidence = _compute_confidence(top_chunks, use_mock_scoring=False)
    assert confidence < 0.35


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
