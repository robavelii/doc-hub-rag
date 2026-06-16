from app.workers.ingest_task import ingest_document


def queue_document_ingestion(doc_id: str, tenant_id: str) -> None:
    ingest_document.delay(doc_id, tenant_id)
