import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import Principal, get_principal, require_document_writer
from app.middleware.rate_limiter import rate_limit
from app.models.access import Collection
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.tenant import Tenant
from app.services.access import resolve_scope
from app.services.audit_service import log_audit
from app.services.cache_service import bump_corpus_version
from app.services.storage_service import build_s3_key, delete_from_s3, upload_to_s3
from app.services.usage_service import check_storage_limit, record_storage_usage
from app.services.vector_service import delete_doc_vectors
from app.utils.file_validation import SUPPORTED_TYPES, detect_file_type, sanitize_filename
from app.utils.url_safety import UnsafeUrlError, validate_url_for_fetch
from app.workers.ingest_task import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 50 * 1024 * 1024


class UrlIngestRequest(BaseModel):
    url: HttpUrl
    collection_id: str | None = None


class DocumentUpdate(BaseModel):
    # null moves the document to General
    collection_id: str | None


async def _audit(db: AsyncSession, request: Request, tenant: Tenant, action: str, **details) -> None:
    user = getattr(request.state, "user", None)
    await log_audit(
        db, action, tenant_id=str(tenant.id), user_id=str(user.id) if user else None,
        details={k: str(v) if v is not None else None for k, v in details.items()},
    )


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


async def _collection_or_404(db: AsyncSession, tenant: Tenant, collection_id: str | None) -> uuid.UUID | None:
    if not collection_id:
        return None
    collection = await db.get(Collection, uuid.UUID(collection_id)) if _is_uuid(collection_id) else None
    if not collection or collection.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection.id


async def _visible_document(db: AsyncSession, principal: Principal, doc_id: str) -> Document:
    """404 for documents in other tenants *and* in collections the caller cannot see."""
    doc = await db.get(Document, uuid.UUID(doc_id)) if _is_uuid(doc_id) else None
    if not doc or doc.tenant_id != principal.tenant.id:
        raise HTTPException(status_code=404, detail="Document not found")
    if not (await resolve_scope(db, principal)).can_see(doc.collection_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _doc_summary(d: Document) -> dict:
    return {
        "id": str(d.id),
        "filename": d.filename,
        "file_type": d.file_type,
        "size_bytes": d.size_bytes,
        "chunk_count": d.chunk_count,
        "status": d.status,
        "error_message": d.error_message,
        "collection_id": str(d.collection_id) if d.collection_id else None,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@router.get("")
async def list_documents(
    collection_id: str | None = None,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    scope = await resolve_scope(db, principal)
    query = select(Document).where(Document.tenant_id == principal.tenant.id, scope.orm_filter(Document.collection_id))
    if collection_id == "general":
        query = query.where(Document.collection_id.is_(None))
    elif collection_id:
        query = query.where(Document.collection_id == await _collection_or_404(db, principal.tenant, collection_id))
    result = await db.execute(query.order_by(Document.created_at.desc()))
    return [_doc_summary(d) for d in result.scalars().all()]


@router.get("/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    doc = await _visible_document(db, principal, doc_id)
    tenant = principal.tenant

    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == doc.id, Chunk.tenant_id == tenant.id)
        .order_by(Chunk.chunk_index)
        .limit(20)
    )
    chunks = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "chunk_index": c.chunk_index,
            "text_preview": c.text_preview,
            "filename": c.filename,
        }
        for c in chunks
    ]


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    doc = await _visible_document(db, principal, doc_id)
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_type": doc.file_type,
        "size_bytes": doc.size_bytes,
        "chunk_count": doc.chunk_count,
        "collection_id": str(doc.collection_id) if doc.collection_id else None,
        "status": doc.status,
        "error_message": doc.error_message,
        "metadata": doc.metadata_,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    collection_id: str | None = Form(default=None),
    tenant: Tenant = Depends(require_document_writer),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit("documents")),
):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    detected_type = detect_file_type(content, file.content_type, file.filename)
    if not detected_type or detected_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported or unrecognized file type. Supported: {', '.join(SUPPORTED_TYPES)}",
        )

    await check_storage_limit(tenant, len(content), db)
    target_collection = await _collection_or_404(db, tenant, collection_id)

    safe_filename = sanitize_filename(file.filename)
    doc_id = uuid.uuid4()
    s3_key = build_s3_key(str(tenant.id), str(doc_id), safe_filename)
    await upload_to_s3(s3_key, content)

    doc = Document(
        id=doc_id,
        tenant_id=tenant.id,
        filename=safe_filename,
        file_type=detected_type,
        s3_key=s3_key,
        size_bytes=len(content),
        status="pending",
        collection_id=target_collection,
    )
    db.add(doc)
    await db.commit()
    await record_storage_usage(str(tenant.id), len(content), str(doc_id), db)

    await _audit(db, request, tenant, "document_uploaded", document_id=doc_id, filename=safe_filename,
                 collection_id=target_collection)
    ingest_document.delay(str(doc_id), str(tenant.id))

    return {"id": str(doc_id), "status": "pending", "filename": safe_filename}


@router.post("/url")
async def ingest_url(
    body: UrlIngestRequest,
    tenant: Tenant = Depends(require_document_writer),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit("documents")),
):
    try:
        validate_url_for_fetch(str(body.url))
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    target_collection = await _collection_or_404(db, tenant, body.collection_id)
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=tenant.id,
        collection_id=target_collection,
        filename=str(body.url),
        file_type="url",
        s3_key="",
        source_url=str(body.url),
        status="pending",
    )
    db.add(doc)
    await db.commit()
    ingest_document.delay(str(doc_id), str(tenant.id))
    return {"id": str(doc_id), "status": "pending", "filename": str(body.url)}


@router.post("/{doc_id}/reingest")
async def reingest_document(
    doc_id: str,
    tenant: Tenant = Depends(require_document_writer),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, doc_id)
    if not doc or str(doc.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Document not found")

    # Old chunks keep answering questions until the new ones replace them atomically.
    doc.status = "pending"
    doc.error_message = None
    await db.commit()

    ingest_document.delay(str(doc_id), str(tenant.id))
    return {"id": str(doc_id), "status": "pending"}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    request: Request,
    tenant: Tenant = Depends(require_document_writer),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, doc_id)
    if not doc or str(doc.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Document not found")

    await delete_doc_vectors(db, str(doc.id), str(tenant.id))
    delete_from_s3(doc.s3_key)
    size = doc.size_bytes
    await db.delete(doc)
    await db.commit()
    await record_storage_usage(str(tenant.id), -size, doc_id, db)
    await bump_corpus_version(str(tenant.id))
    await _audit(db, request, tenant, "document_deleted", document_id=doc_id)
    return {"deleted": True}


@router.patch("/{doc_id}")
async def move_document(
    doc_id: str,
    body: DocumentUpdate,
    request: Request,
    tenant: Tenant = Depends(require_document_writer),
    db: AsyncSession = Depends(get_db),
):
    """Move a document between collections. Its chunks move with it immediately."""
    doc = await db.get(Document, uuid.UUID(doc_id)) if _is_uuid(doc_id) else None
    if not doc or doc.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Document not found")
    target = await _collection_or_404(db, tenant, body.collection_id)
    doc.collection_id = target
    await db.execute(update(Chunk).where(Chunk.document_id == doc.id).values(collection_id=target))
    await db.commit()
    await bump_corpus_version(str(tenant.id))
    await _audit(db, request, tenant, "document_moved", document_id=doc.id, collection_id=target)
    return _doc_summary(doc)
