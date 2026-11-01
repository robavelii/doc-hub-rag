import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Computed, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.config import settings
from app.database import Base


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_preview = Column(String(500), nullable=False, default="")
    filename = Column(String, nullable=False, default="")
    # Denormalised from documents.collection_id so retrieval can filter without a join.
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id", ondelete="SET NULL"), index=True)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSIONS))
    # Full-text index over filename + text, maintained by Postgres.
    search_vector = Column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(filename, '') || ' ' || coalesce(text, ''))", persisted=True),
    )
    # Structural context for citations and display: {"heading": "...", "page": 3, ...}
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="chunks")
