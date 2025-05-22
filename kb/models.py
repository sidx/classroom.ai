import enum
from datetime import datetime

from indexing.serializers import SourceItemKind
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from utils.sqlalchemy import Base


class IntegrationType(enum.Enum):
    github = "github"
    gitlab = "gitlab"
    azure_devops = "azure_devops"
    google_docs = "google_docs"
    quip = "quip"
    slack = "slack"
    custom = "custom"
    local = "local"


class KBState(enum.Enum):
    ready = "ready"
    indexing = "indexing"
    error = "error"
    disabled = "disabled"
    update_error= "update_error"
    updating = "updating"
    token_error = "token_error"


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    type = Column(
        Enum(IntegrationType, name="integration_type", create_type=True),
        nullable=False,
    )
    name = Column(String(255))
    credentials_json = Column(JSONB, nullable=True) # integration specific things
    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    image_name = Column(String)
    integration_help_url = Column(String)

    knowledge_bases = relationship(
        "KnowledgeBase", back_populates="integration",
        cascade="all, delete-orphan",
    )

class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    integration_id = Column(
        BigInteger,
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255))
    source_identifier = Column(Text, nullable=False)          # repo URL, doc ID …
    kb_type = Column(String(50))                               # repo / folder / …
    settings_json = Column(JSONB, default=dict)
    memory = Column(JSONB, default=dict)
    state = Column(
        Enum(KBState, name="kb_state", create_type=True),
        default=KBState.indexing,
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_indexed_at = Column(DateTime(timezone=True))
    team_id = Column(String, index=True)
    created_by = Column(String)
    org_id = Column(String, index=True)
    is_updatable = Column(Boolean, default=False, nullable=False)
    integration = relationship("Integration", back_populates="knowledge_bases")
    ingestion_runs = relationship(
        "IngestionRun", back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )
    source_items = relationship(
        "SourceItem", back_populates="knowledge_base",
        cascade="all, delete-orphan",
    )


class SourceItem(Base):
    __tablename__ = "source_items"

    id = Column(String, primary_key=True, index=True)

    kb_id = Column(
        BigInteger,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )

    provider_item_id = Column(Text, nullable=False)           # blob SHA, doc ID …
    kind = Column(
        Enum(SourceItemKind, name="source_item_kind", create_type=True),
        nullable=False,
    )
    logical_path = Column(Text)                               # repo path, folder …
    version_tag = Column(String(256))                         # commit SHA / rev
    checksum = Column(String(64))                             # SHA‑256

    metadata_json = Column(JSONB, default=dict)

    knowledge_base = relationship("KnowledgeBase", back_populates="source_items")
    chunks = relationship(
        "Chunk", back_populates="source_item",
        cascade="all, delete-orphan",
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    source_item_id = Column(
        String,
        ForeignKey("source_items.id", ondelete="CASCADE"),
        nullable=False,
    )

    chunk_index = Column(Integer, nullable=False)             # 0,1,2,…
    start_offset = Column(Integer)
    end_offset = Column(Integer)

    text = Column(Text)                                       # optional plaintext
    es_doc_id = Column(String(255))                           # Elasticsearch _id
    metadata_json = Column(JSONB, default=dict)               # {lines:[10,30]} …

    source_item = relationship("SourceItem", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint(
            "source_item_id",
            "chunk_index",
            name="uq_chunk_per_source_index",
        ),
    )
#
# per emit
class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    kb_id = Column(
        BigInteger,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )

    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(20), default="running", nullable=False)  # running /…

    stats_json = Column(JSONB, default=dict)      # {files:…, chunks:…}

    knowledge_base = relationship("KnowledgeBase", back_populates="ingestion_runs")
    errors = relationship(
        "IngestionError", back_populates="run",
        cascade="all, delete-orphan",
    )


class IngestionError(Base):
    __tablename__ = "ingestion_errors"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    run_id = Column(
        BigInteger,
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    error_message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("IngestionRun", back_populates="errors")
