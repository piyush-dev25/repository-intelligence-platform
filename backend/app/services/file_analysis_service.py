from pathlib import Path

import time

from sqlalchemy.orm import Session

from app.models.repository import Repository, RepositoryFile, RepositoryStatus
from app.models.file_knowledge import FileKnowledge
from app.services.extractors.registry import get_extractor
from app.services.llm_service import llm_service, DailyLimitReached
from app.data_access.file_knowledge_data_access import (
    create_knowledge,
    get_knowledge_by_file,
    get_knowledge_by_repository,
    update_knowledge,
)
from app.data_access.repository_data_access import (
    update_repository_status,
    update_repository_analysis_summary,
    update_repository_summary,
)
from app.data_access.repository_file_data_access import get_files_by_repository


NO_SUMMARY_AVAILABLE = "No summary available yet."


CHUNK_SIZE_CHARS = 8000
MAX_CHUNKS = 4
CHUNK_CALL_DELAY_SECONDS = 20

def _summarize_file(file_path: str, source_code: bytes) -> str:
    text = source_code.decode("utf-8", errors="ignore")

    if len(text) <= CHUNK_SIZE_CHARS:
        prompt = (
            f"Explain in plain English what this file does, in 2-3 sentences. "
            f"File: {file_path}\n\n{text}"
        )
        return llm_service.generate(prompt)

    chunks = [text[i:i + CHUNK_SIZE_CHARS] for i in range(0, len(text), CHUNK_SIZE_CHARS)][:MAX_CHUNKS]

    partial_summaries = []
    for index, chunk in enumerate(chunks):
        chunk_prompt = (
            f"This is part {index + 1} of {len(chunks)} of a larger file "
            f"(it continues beyond what's shown here). Briefly describe "
            f"what this part does, in 1-2 sentences.\n\nFile: {file_path}\n\n{chunk}"
        )
        partial_summaries.append(llm_service.generate(chunk_prompt))
        if index < len(chunks) - 1:
            time.sleep(CHUNK_CALL_DELAY_SECONDS)

    combine_prompt = (
        "Here are summaries of different parts of the same file. Combine "
        "them into one coherent summary (2-3 sentences) of what this file "
        f"does as a whole.\n\nFile: {file_path}\n\n"
        + "\n\n".join(f"- {s}" for s in partial_summaries)
    )
    return llm_service.generate(combine_prompt)


# Analyzes a single file: extracts structure, gets an LLM summary, and
# saves (or updates) its FileKnowledge row. Returns None if the file's
# extension isn't supported yet - callers looping over many files decide
# how to count/log that, this function just signals "nothing to do here."
def analyze_file(
    db: Session,
    repository_file: RepositoryFile,
    source_code: bytes,
) -> FileKnowledge | None:
    extractor = get_extractor(repository_file.path)
    if extractor is None:
        return None

    existing = get_knowledge_by_file(db, repository_file.id)

    # Skip re-analysis entirely if the file hasn't changed since we last
    # generated knowledge for it - avoids a wasted extraction pass and,
    # more importantly, an unnecessary LLM call.
    if existing is not None and existing.source_content_hash == repository_file.content_hash:
        return existing

    parsed = extractor.extract(source_code)

    # LLM summary uses the raw source text, not the extracted structure -
    # tree-sitter gives us facts, the LLM reads the actual code for meaning.
    summary = _summarize_file(repository_file.path, source_code)

    if existing is not None:
        return update_knowledge(
            db,
            existing,
            language=parsed["language"],
            entities=parsed["entities"],
            imports=parsed["imports"],
            summary=summary,
            source_content_hash=repository_file.content_hash,
        )

    new_knowledge = FileKnowledge(
        repository_file_id=repository_file.id,
        language=parsed["language"],
        entities=parsed["entities"],
        imports=parsed["imports"],
        summary=summary,
        source_content_hash=repository_file.content_hash,
    )
    return create_knowledge(db, new_knowledge)

# Runs analyze_file() across every file in a repository. Reads each
# file's bytes from disk here - analyze_file itself stays disk-agnostic.
# Per-file failures (e.g. a transient LLM error) don't stop the whole
# run - one bad file shouldn't waste work already done on the other 99.
def analyze_repository(db: Session, repository: Repository) -> dict:
    update_repository_status(db, repository, RepositoryStatus.ANALYZING)

    files = get_files_by_repository(db, repository.id)

    analyzed_count = 0
    failed_count = 0
    skipped_count = 0

    daily_limit_hit = False
    for repository_file in files:
        full_path = Path(repository.storage_path) / repository_file.path

        if not full_path.exists():
            skipped_count += 1
            continue

        try:
            source_code = full_path.read_bytes()
            result = analyze_file(db, repository_file, source_code)
            if result is None:
                skipped_count += 1
            else:
                analyzed_count += 1
        except DailyLimitReached:
            print(f"Daily LLM limit reached - stopping. {analyzed_count} analyzed so far.")
            daily_limit_hit = True
            break
        except Exception as e:
            print(f"Failed to analyze {repository_file.path}: {e}")
            failed_count += 1

    update_repository_analysis_summary(
        db, repository, analyzed_count, failed_count, skipped_count,
    )
    update_repository_status(db, repository, RepositoryStatus.ANALYZED)

    # Only regenerate the repo-level summary if something actually
    # changed this run - avoids a wasted LLM call when every file hit
    # the content_hash skip-check (e.g. a re-scan with nothing new).
    if not daily_limit_hit and (analyzed_count > 0 or repository.repo_summary is None):
        generate_repository_summary(db, repository)

    
    return {
        "analyzed_count": analyzed_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "daily_limit_reached": daily_limit_hit,
    }

def _build_repo_summary_prompt(file_summaries: list[str]) -> str:
    joined = "\n\n".join(f"- {summary}" for summary in file_summaries)
    return (
        "Here are plain-English summaries of individual files in a code repository. "
        "Write one short paragraph (3-5 sentences) describing what this repository/project "
        "does as a whole, based on these file summaries.\n\n"
        f"{joined}"
    )


# Combines every file's summary into one repo-level description. Called
# at the end of analyze_repository(), after the per-file loop finishes -
# uses whatever summaries succeeded, even if some files failed/skipped.
def generate_repository_summary(db: Session, repository: Repository) -> Repository:
    knowledge_rows = get_knowledge_by_repository(db, repository.id)
    file_summaries = [row.summary for row in knowledge_rows if row.summary]

    if not file_summaries:
        return update_repository_summary(db, repository, NO_SUMMARY_AVAILABLE)

    prompt = _build_repo_summary_prompt(file_summaries)
    repo_summary = llm_service.generate(prompt)
    return update_repository_summary(db, repository, repo_summary)