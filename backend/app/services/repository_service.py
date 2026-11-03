import traceback

from fastapi import BackgroundTasks, HTTPException, UploadFile, status as http_status
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.data_access.repository_data_access import (
    create_repository,
    get_repositories_by_owner,
    get_repository_by_id,
    update_repository_status,
    update_repository_storage_path,
    delete_repository,
    update_repository_scan_summary,
    mark_interrupted_repositories_failed,
)
from app.data_access.repository_file_data_access import (
    delete_files_by_repository,
    reconcile_repository_files,
)
from app.models.repository import Repository, RepositoryStatus, SourceType, RepositoryFile
from app.schemas.repository import RepositoryCreate
from app.services.storage_service import save_and_unzip_repository, clone_repository, delete_repository_files
from app.services.scanner_service import scan_repository as run_filesystem_scan
from app.services.file_analysis_service import analyze_repository

# Statuses that mean background work is running on this repo right now.
PROCESSING_STATUSES = {RepositoryStatus.SCANNING, RepositoryStatus.ANALYZING}

INTERRUPTED_ERROR_MESSAGE = "Processing was interrupted (server restarted). Please re-scan."

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


# Duplicate-run guard: refuses to touch a repo while background work is
# still running on it. Without this, a second scan/upload/delete could
# overwrite or remove files the first run is still reading.
def _ensure_not_processing(repo: Repository) -> None:
    if repo.status in PROCESSING_STATUSES:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                f"Repository is currently being processed (status: {repo.status.value}). "
                "Please wait until it finishes."
            ),
        )

# Takes an uploaded zip file for a repo that's already registered,
# saves + unzips it, and updates the repo's status accordingly.
# Saving happens here in the request (the UploadFile is gone after the
# response); scanning + analysis are queued as background work.
def ingest_uploaded_repository(
    db: Session,
    repository_id: int,
    owner_id: int,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    auto_scan: bool = True,
) -> Repository:
    # Reuses the ownership check we already built - only the owner
    # can upload files for their own repo.
    repo = get_repository_for_owner(db, repository_id, owner_id)
    _ensure_not_processing(repo)

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
        # Set SCANNING now, so the response already shows work has started.
        repo = update_repository_status(db, repo, RepositoryStatus.SCANNING)
        background_tasks.add_task(run_repository_pipeline, repo.id, True, True)

    return repo


# Clones a git repo for a repo that's already registered, and updates
# its status accordingly. Mirrors ingest_uploaded_repository's shape:
# cloning stays in the request, scanning + analysis go to the background.
def ingest_git_repository(
    db: Session,
    repository_id: int,
    owner_id: int,
    background_tasks: BackgroundTasks,
    auto_scan: bool = True,
) -> Repository:
    repo = get_repository_for_owner(db, repository_id, owner_id)
    _ensure_not_processing(repo)

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
        repo = update_repository_status(db, repo, RepositoryStatus.SCANNING)
        background_tasks.add_task(run_repository_pipeline, repo.id, True, True)

    return repo

# Deletes a repo entirely - both its database row and its files on disk.
# Owner-checked, same as every other repo-specific operation.
def remove_repository(
    db: Session,
    repository_id: int,
    owner_id: int,
) -> None:
    repo = get_repository_for_owner(db, repository_id, owner_id)
    _ensure_not_processing(repo)

    # Delete file records first - the FK from repository_files to
    # repositories means Postgres won't let us delete the repo row
    # while file rows still reference it.
    delete_files_by_repository(db, repo.id)


    # Remove files first, then the database row. If file deletion fails,
    # we'd rather still have the DB record (so you know it exists and
    # can retry) than lose track of orphaned files with no record at all.
    delete_repository_files(repo.id)
    delete_repository(db, repo)


# Request side of a scan: validates, marks the repo SCANNING, and queues
# the actual scan (and analysis, if auto_analyze) as background work.
def scan_repository(
    db: Session,
    repository_id: int,
    owner_id: int,
    background_tasks: BackgroundTasks,
    auto_analyze: bool = True,
) -> Repository:
    repo = get_repository_for_owner(db, repository_id, owner_id)
    _ensure_not_processing(repo)

    # Can't scan a repo that has no files yet.
    if not repo.storage_path:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Repository has no files to scan yet.",
        )

    repo = update_repository_status(db, repo, RepositoryStatus.SCANNING)
    background_tasks.add_task(run_repository_pipeline, repo.id, True, auto_analyze)

    return repo

# Standalone trigger for analysis, independent of scanning - used both
# when auto_analyze=False was set during scan, and to re-run analysis
# later (e.g. after new file-type support is added) without re-scanning.
# Validates here, then queues the analysis as background work.
def start_repository_analysis(
    db: Session,
    repository_id: int,
    owner_id: int,
    background_tasks: BackgroundTasks,
) -> Repository:
    repo = get_repository_for_owner(db, repository_id, owner_id)
    _ensure_not_processing(repo)

    # Must have gone through scanning at least once - PENDING/INGESTED/
    # SCANNING mean there are no RepositoryFile rows yet to analyze, and
    # FAILED means something already went wrong upstream. PAUSED is
    # deliberately allowed: re-running analysis resumes a quota-paused repo.
    not_ready_statuses = {
        RepositoryStatus.PENDING,
        RepositoryStatus.INGESTED,
        RepositoryStatus.SCANNING,
        RepositoryStatus.FAILED,
    }
    if repo.status in not_ready_statuses:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Repository must be scanned before it can be analyzed (current status: {repo.status.value}).",
        )

    repo = update_repository_status(db, repo, RepositoryStatus.ANALYZING)
    background_tasks.add_task(run_repository_pipeline, repo.id, False, True)
    return repo


# The actual filesystem scan: walks the repo's files on disk, saves
# per-file records, updates the summary fields (totals, languages, key
# files) and marks the repo SCANNED. Runs in the background, so it raises
# plain exceptions - never HTTPException, since no client would receive it.
def _run_filesystem_scan_step(db: Session, repo: Repository) -> Repository:
    scan_result = run_filesystem_scan(repo.storage_path)

    # Clear any file records from a previous scan, so re-scans don't
    # leave stale/duplicate entries behind.
    reconcile_repository_files(db, repo.id, scan_result["files"])

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


# The one background pipeline runner: scan -> analyze, each step optional.
# Opens its own DB session because the request's session is already closed
# by the time this runs. Any unexpected error marks the repo FAILED with a
# readable message and prints the traceback - background work must never
# fail silently, since nobody is waiting on the other end to see an error.
def run_repository_pipeline(
    repository_id: int,
    run_scan: bool,
    run_analyze: bool,
) -> None:
    db = SessionLocal()
    stage = "Processing"
    try:
        repo = get_repository_by_id(db, repository_id)
        if repo is None:
            print(f"Background pipeline: repository {repository_id} no longer exists - nothing to do.")
            return

        if run_scan:
            stage = "Scanning"
            repo = _run_filesystem_scan_step(db, repo)

        if run_analyze:
            stage = "Analysis"
            analyze_repository(db, repo)
    except Exception as exc:
        print(f"Background pipeline for repository {repository_id} failed during {stage.lower()}:")
        traceback.print_exc()
        _mark_pipeline_failed(db, repository_id, f"{stage} failed: {str(exc) or type(exc).__name__}")
    finally:
        db.close()


# Records a background failure on the repo. Rolls back first, because the
# error may have left the session mid-transaction and unusable. If even
# this fails (e.g. the DB went down), print that too rather than swallow it.
def _mark_pipeline_failed(db: Session, repository_id: int, error_message: str) -> None:
    try:
        db.rollback()
        repo = get_repository_by_id(db, repository_id)
        if repo is not None:
            update_repository_status(db, repo, RepositoryStatus.FAILED, error_message)
    except Exception:
        print(f"Could not mark repository {repository_id} as failed:")
        traceback.print_exc()


# Called once at server startup. Background tasks die with the server, so
# any repo still marked scanning/analyzing will never finish - mark them
# failed so the user sees what happened and can re-scan.
def reset_interrupted_repositories(db: Session) -> int:
    reset_count = mark_interrupted_repositories_failed(db, INTERRUPTED_ERROR_MESSAGE)
    if reset_count:
        print(f"Startup: marked {reset_count} interrupted repository(ies) as failed.")
    return reset_count
