"""Re-ingest all documents to rebuild chunks with current parser/chunk/embedding settings."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SyncSession
from app.models.document import Document
from app.workers.ingest_task import ingest_document


def main() -> None:
    with SyncSession() as db:
        docs = (
            db.execute(
                select(Document).where(Document.status.in_(["ready", "failed", "processing"]))
            )
            .scalars()
            .all()
        )
        if not docs:
            print("No documents to re-ingest.")
            return

        print(f"Re-ingesting {len(docs)} document(s)...")
        for doc in docs:
            print(f"  -> {doc.filename} ({doc.status})")
            ingest_document.apply(args=[str(doc.id), str(doc.tenant_id)])
        print("Done. Check document status in the dashboard.")


if __name__ == "__main__":
    main()
