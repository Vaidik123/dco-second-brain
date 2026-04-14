from sqlalchemy import Column, String, Text, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

from app.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String, unique=True, nullable=True)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    # slack | substack_dco | substack_td | twitter | manual
    source = Column(String, nullable=False)
    author = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    # LLM Wiki v2: confidence scoring (boosted when multiple sources reference same content)
    confidence_score = Column(Float, default=1.0)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, nullable=True)
    tags = Column(ARRAY(String), default=list)
    extra = Column(JSON, default=dict)


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    # voyage-3 produces 1024-dim embeddings
    embedding = Column(Vector(1024))


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_item_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"))
    to_item_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"))
    # related | contradicts | cites | supersedes
    relationship = Column(String, nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
