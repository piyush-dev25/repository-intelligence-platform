from fastapi import HTTPException, UploadFile, status as http_status
from sqlalchemy.orm import Session
from app.data_access.repository_data_access import (
    create_repository,
    get_repositories_by_owner,
    get_repository_by_id,
    update_repository_status,
    update_repository_storage_path,
    delete_repository,
    update_repository_scan_summary,
)
from app.data_access.repository_file_data_access import (
    create_repository_files,
    delete_files_by_repository,
)
from app.models.repository import Repository, RepositoryStatus, SourceType, RepositoryFile
from app.schemas.repository import RepositoryCreate
from app.services.storage_service import save_and_unzip_repository, clone_repository, delete_repository_files
from app.services.scanner_service import scan_repository as run_filesystem_scan

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
    auto_scan: bool = True,
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
    repo = update_repository_status(db, repo, RepositoryStatus.INGESTED)

    if auto_scan:
        repo = scan_repository(db, repo.id, owner_id)

    return repo


# Clones a git repo for a repo that's already registered, and updates
# its status accordingly. Mirrors ingest_uploaded_repository's shape.
def ingest_git_repository(
    db: Session,
    repository_id: int,
    owner_id: int,
    auto_scan: bool = True,
) -> Repository:
    repo = get_repository_for_owner(db, repository_id, owner_id)

    # Make sure this repo was actually registered as a "git" type -
    # cloning makes no sense for an upload-type repo.
    if repo.source_type != SourceType.GIT:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="This repository is not a git-type repository.",
        )

    # Defensive check - the schema validator guarantees this at the API
    # boundary, but this function shouldn't blindly trust that. Protects
    # against a manually edited DB row or a future bug elsewhere.
    if not repo.source_url:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Repository has no source URL.",
        )

    try:
        storage_path = clone_repository(repo.id, repo.source_url)
    except Exception as exc:
        update_repository_status(db, repo, RepositoryStatus.FAILED, str(exc))
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to clone repository: {exc}",
        )

    update_repository_storage_path(db, repo, storage_path)
    repo = update_repository_status(db, repo, RepositoryStatus.INGESTED)

    if auto_scan:
        repo = scan_repository(db, repo.id, owner_id)

    return repo

# Deletes a repo entirely - both its database row and its files on disk.
# Owner-checked, same as every other repo-specific operation.
def remove_repository(
    db: Session,
    repository_id: int,
    owner_id: int,
) -> None:
    repo = get_repository_for_owner(db, repository_id, owner_id)

    # Delete file records first - the FK from repository_files to
    # repositories means Postgres won't let us delete the repo row
    # while file rows still reference it.
    delete_files_by_repository(db, repo.id)


    # Remove files first, then the database row. If file deletion fails,
    # we'd rather still have the DB record (so you know it exists and
    # can retry) than lose track of orphaned files with no record at all.
    delete_repository_files(repo.id)
    delete_repository(db, repo)


# Scans a repo's files on disk, saves per-file records, and updates the
# repo's summary fields (totals, languages, key files).
def scan_repository(
    db: Session,
    repository_id: int,
    owner_id: int,
) -> Repository:
    repo = get_repository_for_owner(db, repository_id, owner_id)

    # Can't scan a repo that has no files yet.
    if not repo.storage_path:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Repository has no files to scan yet.",
        )

    update_repository_status(db, repo, RepositoryStatus.SCANNING)

    try:
        scan_result = run_filesystem_scan(repo.storage_path)
    except Exception as exc:
        update_repository_status(db, repo, RepositoryStatus.FAILED, str(exc))
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to scan repository: {exc}",
        )

    # Clear any file records from a previous scan, so re-scans don't
    # leave stale/duplicate entries behind.
    delete_files_by_repository(db, repo.id)

    file_records = [
        RepositoryFile(
            repository_id=repo.id,
            path=file["path"],
            extension=file["extension"],
            size_bytes=file["size_bytes"],
            content_hash=file["content_hash"],
        )
        for file in scan_result["files"]
    ]
    create_repository_files(db, file_records)

    update_repository_scan_summary(
        db,
        repo,
        total_files=scan_result["total_files"],
        total_directories=scan_result["total_directories"],
        total_size_bytes=scan_result["total_size_bytes"],
        language_breakdown=scan_result["language_breakdown"],
        key_files=scan_result["key_files"],
    )

    return update_repository_status(db, repo, RepositoryStatus.SCANNED)