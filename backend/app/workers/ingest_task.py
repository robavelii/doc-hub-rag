import asyncio
import concurrent.futures
import uuid
from collections.abc import Coroutine
from typing import TypeVar

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.database import SyncSession, set_tenant_rls_sync
from app.models.document import Document
from app.services.cache_service import bump_corpus_version_sync
from app.services.embedding_service import embed_chunks
from app.services.storage_service import download_from_s3
from app.services.vector_service import replace_doc_chunks_sync
from app.workers.celery_app import celery
from app.workers.parsers.docx_parser import parse_docx
from app.workers.parsers.pdf_parser import parse_pdf
from app.workers.parsers.txt_parser import parse_txt
from app.workers.parsers.url_parser import parse_url

T = TypeVar("T")

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
BATCH_SIZE = 100

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
    separators=["\n\n", "\n", " ", ""],
)


def _run_async(coro: Coroutine[None, None, T]) -> T:
    """Run async code from sync Celery tasks (works inside or outside a running loop)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _mark_document_failed(doc_id: str, tenant_id: str, error: Exception) -> None:
    """Persist failed status in a fresh session (avoids SyncSession rollback undoing it)."""
    with SyncSession() as db:
        set_tenant_rls_sync(db, tenant_id)
        doc = db.get(Document, doc_id)
        if doc:
            doc.status = "failed"
            doc.error_message = str(error)[:500]


def _embed_chunks(chunks: list[str], filename: str) -> list[dict]:
    """Embed every chunk before anything is written. Raises if the provider fails."""
    vectors: list[dict] = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        embeddings = _run_async(embed_chunks(batch))
        if len(embeddings) != len(batch):
            raise RuntimeError(f"Embedding provider returned {len(embeddings)} vectors for {len(batch)} chunks")
        vectors.extend(
            {
                "id": str(uuid.uuid4()),
                "chunk_index": i + j,
                "text": chunk,
                "text_preview": chunk[:500],
                "filename": filename,
                "embedding": embedding,
            }
            for j, (chunk, embedding) in enumerate(zip(batch, embeddings, strict=True))
        )
    return vectors


def _index_text(db, doc: Document, tenant_id: str, text: str, filename: str, extra_metadata: dict | None = None) -> None:
    """Chunk + embed `text`, then swap the document's chunks in one transaction."""
    if not text.strip():
        raise ValueError("Document produced no extractable text")
    chunks = text_splitter.split_text(text)
    vectors = _embed_chunks(chunks, filename)

    replace_doc_chunks_sync(db, tenant_id, str(doc.id), vectors)
    doc.chunk_count = len(chunks)
    doc.status = "ready"
    doc.error_message = None
    doc.metadata_ = {
        **(extra_metadata or {}),
        "word_count": len(text.split()),
        "char_count": len(text),
    }
    db.commit()
    bump_corpus_version_sync(tenant_id)


def _load_owned_document(db, doc_id: str, tenant_id: str) -> Document | None:
    doc = db.get(Document, doc_id)
    if doc and str(doc.tenant_id) != str(tenant_id):
        raise ValueError(f"Document {doc_id} does not belong to tenant {tenant_id}")
    return doc


def _extract_text(doc: Document) -> str:
    if doc.file_type == "url":
        return parse_url(doc.source_url or doc.filename)
    if not doc.s3_key:
        raise ValueError("Document has no stored file (empty S3 key)")
    parser = {"pdf": parse_pdf, "docx": parse_docx, "txt": parse_txt}.get(doc.file_type)
    if not parser:
        raise ValueError(f"No parser for type: {doc.file_type}")
    return parser(download_from_s3(doc.s3_key))


@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_document(self, doc_id: str, tenant_id: str):
    try:
        with SyncSession() as db:
            set_tenant_rls_sync(db, tenant_id)
            doc = _load_owned_document(db, doc_id, tenant_id)
            if not doc:
                return
            doc.status = "processing"
            db.commit()
            _index_text(db, doc, tenant_id, _extract_text(doc), doc.filename)
    except ValueError as exc:
        # Non-retryable: bad input (missing file, unsupported type, empty text)
        _mark_document_failed(doc_id, tenant_id, exc)
        raise
    except Exception as exc:
        _mark_document_failed(doc_id, tenant_id, exc)
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_notion_page(self, doc_id: str, tenant_id: str, text: str, filename: str, last_edited: str | None = None):
    try:
        with SyncSession() as db:
            set_tenant_rls_sync(db, tenant_id)
            doc = _load_owned_document(db, doc_id, tenant_id)
            if not doc:
                return
            doc.status = "processing"
            doc.filename = filename
            db.commit()
            extra = {"last_edited": last_edited} if last_edited else None
            _index_text(db, doc, tenant_id, text, filename, extra)
    except ValueError as exc:
        _mark_document_failed(doc_id, tenant_id, exc)
        raise
    except Exception as exc:
        _mark_document_failed(doc_id, tenant_id, exc)
        raise self.retry(exc=exc) from exc
