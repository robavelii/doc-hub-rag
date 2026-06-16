import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_tenant
from app.middleware.rate_limiter import rate_limit
from app.models.chunk import Chunk
from app.models.document import Document
from app.utils.file_validation import detect_file_type, sanitize_filename
from app.models.tenant import Tenant
from app.services.storage_service import build_s3_key, delete_from_s3, upload_to_s3
from app.services.usage_service import check_storage_limit, record_storage_usage
from app.services.vector_service import delete_doc_vectors
from app.utils.url_safety import UnsafeUrlError, validate_url_for_fetch
from app.workers.ingest_task import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
}
MAX_FILE_SIZE = 50 * 1024 * 1024


class UrlIngestRequest(BaseModel):
    url: HttpUrl


@router.get("")
async def list_documents(tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).where(Document.tenant_id == tenant.id).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "file_type": d.file_type,
            "size_bytes": d.size_bytes,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "error_message": d.error_message,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, doc_id)
    if not doc or str(doc.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Document not found")

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
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, doc_id)
    if not doc or str(doc.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_type": doc.file_type,
        "size_bytes": doc.size_bytes,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "error_message": doc.error_message,
        "metadata": doc.metadata_,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit("documents")),
):
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    detected_type = detect_file_type(content, file.content_type)
    if not detected_type or detected_type not in ALLOWED_TYPES.values():
        raise HTTPException(status_code=400, detail="Unsupported or unrecognized file type")

    await check_storage_limit(tenant, len(content), db)

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
    )
    db.add(doc)
    await db.commit()
    await record_storage_usage(str(tenant.id), len(content), str(doc_id), db)

    ingest_document.delay(str(doc_id), str(tenant.id))

    return {"id": str(doc_id), "status": "pending", "filename": safe_filename}


@router.post("/url")
async def ingest_url(
    body: UrlIngestRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit("documents")),
):
    try:
        validate_url_for_fetch(str(body.url))
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=tenant.id,
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
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, doc_id)
    if not doc or str(doc.tenant_id) != str(tenant.id):
        raise HTTPException(status_code=404, detail="Document not found")

    await delete_doc_vectors(db, str(doc.id), str(tenant.id))
    doc.status = "pending"
    doc.error_message = None
    doc.chunk_count = 0
    await db.commit()

    ingest_document.delay(str(doc_id), str(tenant.id))
    return {"id": str(doc_id), "status": "pending"}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    tenant: Tenant = Depends(get_current_tenant),
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
    return {"deleted": True}
