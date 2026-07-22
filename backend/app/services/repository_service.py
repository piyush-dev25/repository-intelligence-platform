from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session
from app.data_access.repository_data_access import (
    create_repository,
    get_repositories_by_owner,
    get_repository_by_id,
)
from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate


# Creates a new repo record. Doesn't clone/download any files yet -
# that happens later, in the upload/scan step.
def register_repository(
    db: Session,
    owner_id: int,
    repo_in: RepositoryCreate,
) -> Repository:
    repo = Repository(
        owner_id=owner_id,
        name=repo_in.name,
        source_type=repo_in.source_type,
        source_url=repo_in.source_url,
    )
    return create_repository(db, repo)


# Gets all repos belonging to a given user.
def list_user_repositories(db: Session, owner_id: int) -> list[Repository]:
    return get_repositories_by_owner(db, owner_id)


# Gets one repo, but only if it actually belongs to this user.
def get_repository_for_owner(
    db: Session,
    repository_id: int,
    owner_id: int,
) -> Repository:
    repo = get_repository_by_id(db, repository_id)

    # If it doesn't exist OR belongs to someone else, treat it the same way:
    # say "not found" rather than "not yours" - so we don't confirm to a
    # stranger that a repo with that id even exists.
    if repo is None or repo.owner_id != owner_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    return repo