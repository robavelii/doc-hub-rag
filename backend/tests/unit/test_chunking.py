from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", " ", ""],
)


def test_chunks_respect_size_limit():
    text = "word " * 1000
    chunks = text_splitter.split_text(text)
    assert all(len(c) <= CHUNK_SIZE * 6 for c in chunks)
    assert len(chunks) > 1


def test_overlap_exists():
    text = "sentence one. " * 100
    chunks = text_splitter.split_text(text)
    assert len(chunks) > 1
    assert chunks[0][-20:] in chunks[1] or chunks[1][:20] in chunks[0]
