from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.repository import RepositoryFile

class FileKnowledge(Base):
    __tablename__ = "file_knowledge"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    repository_file_id: Mapped[int] = mapped_column(
        ForeignKey("repository_files.id"), unique=True, index=True,
    )

    language: Mapped[str] = mapped_column(String(50))
    entities: Mapped[list[dict]] = mapped_column(JSON)
    imports: Mapped[list[str]] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)

    # The content_hash this knowledge was generated FROM - compare against
    # RepositoryFile.content_hash on re-scan to decide whether to re-summarize.
    source_content_hash: Mapped[str] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Lets you write knowledge.repository_file instead of a manual query.
    repository_file: Mapped["RepositoryFile"] = relationship(back_populates="knowledge")