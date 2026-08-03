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