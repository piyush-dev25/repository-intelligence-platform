from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file_knowledge import FileKnowledge
from app.models.repository import RepositoryFile


# Saves a new FileKnowledge row after a file's been analyzed for the
# first time (extraction + LLM summary already done by the caller -
# this function only persists it).
def create_knowledge(db: Session, knowledge: FileKnowledge) -> FileKnowledge:
    db.add(knowledge)
    db.commit()
    return knowledge


# Looks up existing knowledge for a file, by the file's own id - used
# both to check "has this file been analyzed before" and to fetch the
# source_content_hash for the skip-on-unchanged check during re-scans.
def get_knowledge_by_file(db: Session, repository_file_id: int) -> FileKnowledge | None:
    statement = select(FileKnowledge).where(
        FileKnowledge.repository_file_id == repository_file_id
    )
    return db.execute(statement).scalars().first()


# Updates an existing knowledge row in place, for when a file changed
# and needs re-analysis - avoids leaving stale duplicate rows behind,
# since repository_file_id is unique (one knowledge row per file).
def update_knowledge(
    db: Session,
    existing: FileKnowledge,
    language: str,
    entities: list[dict],
    imports: list[str],
    summary: str,
    source_content_hash: str,
) -> FileKnowledge:
    existing.language = language
    existing.entities = entities
    existing.imports = imports
    existing.summary = summary
    existing.source_content_hash = source_content_hash
    db.commit()
    return existing

# Gets every FileKnowledge row for a repo, by joining through
# RepositoryFile (FileKnowledge has no direct repository_id of its own).
# Used to gather all per-file summaries for the repo-level summary step.
def get_knowledge_by_repository(db: Session, repository_id: int) -> list[FileKnowledge]:
    statement = (
        select(FileKnowledge)
        .join(RepositoryFile, FileKnowledge.repository_file_id == RepositoryFile.id)
        .where(RepositoryFile.repository_id == repository_id)
    )
    return db.execute(statement).scalars().all()