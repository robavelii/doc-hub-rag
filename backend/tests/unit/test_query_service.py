from app.services.query_service import (
    CONTEXT_CHUNK_COUNT,
    SYSTEM_PROMPT,
    _compute_confidence,
    _expand_search_terms,
    _query_terms,
)


def test_query_terms_strips_stopwords():
    terms = _query_terms("what is the persons name")
    assert "what" not in terms
    assert "persons" not in terms
    assert "name" in terms


def test_expand_search_terms_adds_finance_synonyms():
    expanded = _expand_search_terms(["balance", "name"])
    assert "running balance" in expanded
    assert "account holder" in expanded


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
