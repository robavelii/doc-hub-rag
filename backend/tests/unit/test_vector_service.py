from app.services.vector_service import _format_vector, _row_to_candidate


def test_format_vector_produces_pg_array():
    vec = _format_vector([0.1, 0.2, 0.3])
    assert vec.startswith("[")
    assert "0.1" in vec


def test_row_to_candidate_maps_metadata():
    class Row:
        id = "abc"
        document_id = "doc1"
        chunk_index = 0
        text = "full text"
        text_preview = "preview"
        filename = "file.txt"

    candidate = _row_to_candidate(Row(), "tenant-1", 0.9)
    assert candidate["score"] == 0.9
    assert candidate["metadata"]["filename"] == "file.txt"
    assert candidate["metadata"]["text"] == "full text"
