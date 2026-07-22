from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.repository import RepositoryStatus, SourceType


# Fields every repo schema shares.
class RepositoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


# What the user sends us when registering a new repo.
class RepositoryCreate(RepositoryBase):
    source_type: SourceType
    source_url: str | None = None  # only needed if source_type is 'git'

    # Extra check: if it's a git repo, source_url must be filled in.
    @model_validator(mode="after")
    def validate_source_url(self):
        if self.source_type == SourceType.GIT and not self.source_url:
            raise ValueError("source_url is required when source_type is 'git'")
        if self.source_type == SourceType.UPLOAD and self.source_url:
            raise ValueError("source_url must not be set when source_type is 'upload'")
        return self


# What we send back to the user (a full repo record).
class RepositoryOut(RepositoryBase):
    id: int
    owner_id: int
    source_type: SourceType
    source_url: str | None
    status: RepositoryStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    # Lets Pydantic read this straight from a SQLAlchemy object.
    model_config = ConfigDict(from_attributes=True)