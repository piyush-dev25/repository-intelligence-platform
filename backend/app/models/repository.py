from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


# The two ways a repo can enter the system: a git URL, or an uploaded file.
class SourceType(str, PyEnum):
    GIT = "git"
    UPLOAD = "upload"


# Where a repo currently sits in the pipeline: upload -> scan -> embed -> ready.
class RepositoryStatus(str, PyEnum):
    PENDING = "pending"      # just registered, nothing's happened yet
    SCANNING = "scanning"    # reading files, gathering metadata
    EMBEDDING = "embedding"  # generating vector embeddings for search
    READY = "ready"          # fully processed, safe to query
    FAILED = "failed"        # something went wrong (see error_message)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Links this repo to the user who added it. Points at users.id.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    name: Mapped[str] = mapped_column(String(255))

    # How this repo got in: 'git' or 'upload'. Only one ever applies.
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type"),
    )

    # Only set when source_type is 'git'. Null for uploads.
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Where the repo's files actually live once downloaded/unpacked.
    # Null at first — this gets filled in by a later pipeline step.
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Current pipeline stage. Starts at 'pending' the moment the row is created.
    status: Mapped[RepositoryStatus] = mapped_column(
        Enum(RepositoryStatus, name="repository_status"),
        default=RepositoryStatus.PENDING,
    )

    # Human-readable reason if status becomes 'failed'.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Auto-updates every time the row changes, thanks to onupdate.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )