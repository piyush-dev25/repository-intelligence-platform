from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file_knowledge import FileKnowledge
from app.models.repository import RepositoryFile


# Saves a new FileKnowledge row the first time a file's structure is
# extracted. The summary is usually still empty at this point - the
# summary pass fills it in later.
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


# Overwrites an existing knowledge row's structure (language, entities,
# imports) in place - one row per file, since repository_file_id is unique.
# clear_summary=True wipes the summary when the file's content changed,
# because the old summary describes code that no longer exists.
def update_knowledge_structure(
    db: Session,
    existing: FileKnowledge,
    language: str,
    entities: list[dict],
    imports: list[str],
    source_content_hash: str,
    clear_summary: bool,
) -> FileKnowledge:
    existing.language = language
    existing.entities = entities
    existing.imports = imports
    existing.source_content_hash = source_content_hash
    if clear_summary:
        existing.summary = None
    db.commit()
    return existing


# Saves one file's LLM summary. Called right after each summary is
# generated, so progress survives a crash or quota hit mid-run.
def update_knowledge_summary(db: Session, knowledge: FileKnowledge, summary: str) -> FileKnowledge:
    knowledge.summary = summary
    db.commit()
    return knowledge

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