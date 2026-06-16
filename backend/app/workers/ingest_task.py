import asyncio
import concurrent.futures
import uuid
from typing import Coroutine, TypeVar

from langchain_text_splitters import RecursiveCharacterTextSplitter

T = TypeVar("T")

from app.database import SyncSession, set_tenant_rls_sync
from app.models.document import Document
from app.services.embedding_service import embed_chunks
from app.services.storage_service import download_from_s3
from app.services.vector_service import delete_doc_vectors_sync, upsert_chunks_sync
from app.workers.celery_app import celery
from app.workers.parsers.docx_parser import parse_docx
from app.workers.parsers.pdf_parser import parse_pdf
from app.workers.parsers.txt_parser import parse_txt
from app.workers.parsers.url_parser import parse_url

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


@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_document(self, doc_id: str, tenant_id: str):
    try:
        with SyncSession() as db:
            set_tenant_rls_sync(db, tenant_id)
            doc = db.get(Document, doc_id)
            if not doc:
                return
            if str(doc.tenant_id) != str(tenant_id):
                raise ValueError(f"Document {doc_id} does not belong to tenant {tenant_id}")

            doc.status = "processing"
            db.commit()

            delete_doc_vectors_sync(db, doc_id, tenant_id)

            if doc.file_type == "url":
                text = parse_url(doc.source_url or doc.filename)
            else:
                if not doc.s3_key:
                    raise ValueError("Document has no stored file (empty S3 key)")
                raw_content = download_from_s3(doc.s3_key)
                parser_map = {"pdf": parse_pdf, "docx": parse_docx, "txt": parse_txt}
                parser = parser_map.get(doc.file_type)
                if not parser:
                    raise ValueError(f"No parser for type: {doc.file_type}")
                text = parser(raw_content)

            if not text.strip():
                raise ValueError("Document produced no extractable text")

            chunks = text_splitter.split_text(text)
            all_vectors = []

            for i in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[i : i + BATCH_SIZE]
                embeddings = _run_async(embed_chunks(batch))
                vectors = [
                    {
                        "id": str(uuid.uuid4()),
                        "chunk_index": i + j,
                        "text": chunk,
                        "text_preview": chunk[:500],
                        "filename": doc.filename,
                        "embedding": embedding,
                    }
                    for j, (chunk, embedding) in enumerate(zip(batch, embeddings))
                ]
                all_vectors.extend(vectors)

            upsert_chunks_sync(db, tenant_id, doc_id, all_vectors)

            doc.chunk_count = len(chunks)
            doc.status = "ready"
            doc.error_message = None
            doc.metadata_ = {"word_count": len(text.split()), "char_count": len(text)}
            db.commit()

    except ValueError as exc:
        # Non-retryable: bad input (missing file, unsupported type, empty text)
        _mark_document_failed(doc_id, tenant_id, exc)
        raise
    except Exception as exc:
        _mark_document_failed(doc_id, tenant_id, exc)
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def ingest_notion_page(self, doc_id: str, tenant_id: str, text: str, filename: str):
    try:
        with SyncSession() as db:
            set_tenant_rls_sync(db, tenant_id)
            doc = db.get(Document, doc_id)
            if not doc:
                return
            if str(doc.tenant_id) != str(tenant_id):
                raise ValueError(f"Document {doc_id} does not belong to tenant {tenant_id}")

            doc.status = "processing"
            doc.filename = filename
            db.commit()

            delete_doc_vectors_sync(db, doc_id, tenant_id)
            chunks = text_splitter.split_text(text)
            all_vectors = []

            for i in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[i : i + BATCH_SIZE]
                embeddings = _run_async(embed_chunks(batch))
                vectors = [
                    {
                        "id": str(uuid.uuid4()),
                        "chunk_index": i + j,
                        "text": chunk,
                        "text_preview": chunk[:500],
                        "filename": filename,
                        "embedding": embedding,
                    }
                    for j, (chunk, embedding) in enumerate(zip(batch, embeddings))
                ]
                all_vectors.extend(vectors)

            upsert_chunks_sync(db, tenant_id, doc_id, all_vectors)
            doc.chunk_count = len(chunks)
            doc.status = "ready"
            doc.error_message = None
            doc.metadata_ = {"word_count": len(text.split()), "char_count": len(text)}
            db.commit()

    except Exception as exc:
        _mark_document_failed(doc_id, tenant_id, exc)
        raise self.retry(exc=exc)
