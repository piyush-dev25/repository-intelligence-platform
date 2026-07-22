from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.repository import Repository, RepositoryStatus


# Saves a new repo row to the database.
def create_repository(db: Session, db_repo: Repository) -> Repository:
    db.add(db_repo)
    db.commit()
    db.refresh(db_repo)  # reloads it so we get the auto-generated id, timestamps, etc.
    return db_repo


# Finds one repo by its id. Returns None if it doesn't exist.
def get_repository_by_id(db: Session, repository_id: int) -> Repository | None:
    statement = select(Repository).where(Repository.id == repository_id)
    return db.execute(statement).scalar_one_or_none()


# Gets every repo that belongs to a given user.
def get_repositories_by_owner(db: Session, owner_id: int) -> list[Repository]:
    statement = select(Repository).where(Repository.owner_id == owner_id)
    return db.execute(statement).scalars().all()


# Updates a repo's pipeline status (and optionally an error message).
def update_repository_status(
    db: Session,
    db_repo: Repository,
    status: RepositoryStatus,
    error_message: str | None = None,
) -> Repository:
    db_repo.status = status
    db_repo.error_message = error_message
    db.commit()
    db.refresh(db_repo)
    return db_repo


# Updates where a repo's files actually live, once they've been stored.
def update_repository_storage_path(
    db: Session,
    db_repo: Repository,
    storage_path: str,
) -> Repository:
    db_repo.storage_path = storage_path
    db.commit()
    db.refresh(db_repo)
    return db_repo