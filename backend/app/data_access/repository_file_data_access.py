from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.repository import RepositoryFile


# Saves many file records at once - the scanner will call this once per
# repo with the full list, not one file at a time.
def create_repository_files(
    db: Session,
    files: list[RepositoryFile],
) -> list[RepositoryFile]:
    db.add_all(files)
    db.commit()
    return files


# Gets every file record for a given repo.
def get_files_by_repository(db: Session, repository_id: int) -> list[RepositoryFile]:
    statement = select(RepositoryFile).where(
        RepositoryFile.repository_id == repository_id
    )
    return db.execute(statement).scalars().all()


# Deletes every file record for a given repo. Needed for re-scans - old
# file records shouldn't linger once a repo gets scanned again.
def delete_files_by_repository(db: Session, repository_id: int) -> None:
    statement = delete(RepositoryFile).where(
        RepositoryFile.repository_id == repository_id
    )
    db.execute(statement)
    db.commit()


# Reconciles a repo's file records against a fresh scan result, instead
# of blindly deleting and recreating everything. This matters because
# RepositoryFile.id feeds FileKnowledge's foreign key - if we deleted
# and recreated every row on every scan, unchanged files would get new
# ids, breaking the content_hash skip-check and wiping their existing
# FileKnowledge (via cascade) for no reason.
def reconcile_repository_files(
    db: Session,
    repository_id: int,
    scanned_files: list[dict],
) -> list[RepositoryFile]:
    existing = get_files_by_repository(db, repository_id)
    existing_by_path = {file.path: file for file in existing}
    scanned_paths = {file["path"] for file in scanned_files}

    result = []
    for scanned in scanned_files:
        existing_file = existing_by_path.get(scanned["path"])
        if existing_file is not None:
            # File already existed - update in place, keeping its id
            # (and therefore its FileKnowledge, if content didn't change).
            existing_file.extension = scanned["extension"]
            existing_file.size_bytes = scanned["size_bytes"]
            existing_file.content_hash = scanned["content_hash"]
            result.append(existing_file)
        else:
            # Genuinely new file - no existing row to preserve.
            new_file = RepositoryFile(
                repository_id=repository_id,
                path=scanned["path"],
                extension=scanned["extension"],
                size_bytes=scanned["size_bytes"],
                content_hash=scanned["content_hash"],
            )
            db.add(new_file)
            result.append(new_file)

    # Remove files that existed before but are no longer present in this
    # scan (e.g. deleted from the repo since last time) - their
    # FileKnowledge cascades away too, which is correct: the file's gone.
    for path, file in existing_by_path.items():
        if path not in scanned_paths:
            db.delete(file)

    db.commit()
    return result