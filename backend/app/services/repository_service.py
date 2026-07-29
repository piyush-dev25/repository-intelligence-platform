from fastapi import HTTPException, UploadFile, status as http_status
from sqlalchemy.orm import Session
from app.data_access.repository_data_access import (
    create_repository,
    get_repositories_by_owner,
    get_repository_by_id,
    update_repository_status,
    update_repository_storage_path,
)
from app.models.repository import Repository, RepositoryStatus, SourceType
from app.schemas.repository import RepositoryCreate
from app.services.storage_service import save_and_unzip_repository

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

# Takes an uploaded zip file for a repo that's already registered,
# saves + unzips it, and updates the repo's status accordingly.
def ingest_uploaded_repository(
    db: Session,
    repository_id: int,
    owner_id: int,
    file: UploadFile,
) -> Repository:
    # Reuses the ownership check we already built - only the owner
    # can upload files for their own repo.
    repo = get_repository_for_owner(db, repository_id, owner_id)

    # Make sure this repo was actually registered as an "upload" type,
    # not a "git" one - uploading a file to a git-type repo makes no sense.
    if repo.source_type != SourceType.UPLOAD:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="This repository is not an upload-type repository.",
        )

    # Mark as in-progress before starting, so status reflects reality
    # while the file is actually being saved/unzipped, not just after.
    update_repository_status(db, repo, RepositoryStatus.SCANNING)

    try:
        storage_path = save_and_unzip_repository(repo.id, file)
    except Exception as exc:
        # If saving/unzipping fails, record why - don't leave it stuck
        # at "scanning" with no explanation.
        update_repository_status(db, repo, RepositoryStatus.FAILED, str(exc))
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process uploaded file: {exc}",
        )

    update_repository_storage_path(db, repo, storage_path)
    return update_repository_status(db, repo, RepositoryStatus.READY)