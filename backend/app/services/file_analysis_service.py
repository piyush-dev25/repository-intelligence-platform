from dataclasses import dataclass, field
from pathlib import Path

import time

from sqlalchemy.orm import Session

from app.models.repository import Repository, RepositoryFile, RepositoryStatus
from app.models.file_knowledge import FileKnowledge
from app.services.extractors.registry import get_extractor
from app.services.llm_service import llm_service, DailyLimitReached, LLMNotConfiguredError
from app.data_access.file_knowledge_data_access import (
    create_knowledge,
    get_knowledge_by_file,
    get_knowledge_by_repository,
    update_knowledge_structure,
    update_knowledge_summary,
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


# Extracts one file's structure (language, entities, imports) with
# Tree-sitter and saves it to its FileKnowledge row - no LLM involved.
# Always re-extracts (cheap), so structure is fresh even for unchanged
# files. If the file's content changed since its summary was written, the
# summary is cleared so the summary pass regenerates it. Returns None if
# the file's extension isn't supported.
def extract_file_structure(
    db: Session,
    repository_file: RepositoryFile,
    source_code: bytes,
) -> FileKnowledge | None:
    extractor = get_extractor(repository_file.path)
    if extractor is None:
        return None

    parsed = extractor.extract(source_code)
    existing = get_knowledge_by_file(db, repository_file.id)

    if existing is not None:
        return update_knowledge_structure(
            db,
            existing,
            language=parsed["language"],
            entities=parsed["entities"],
            imports=parsed["imports"],
            source_content_hash=repository_file.content_hash,
            clear_summary=existing.source_content_hash != repository_file.content_hash,
        )

    new_knowledge = FileKnowledge(
        repository_file_id=repository_file.id,
        language=parsed["language"],
        entities=parsed["entities"],
        imports=parsed["imports"],
        summary=None,
        source_content_hash=repository_file.content_hash,
    )
    return create_knowledge(db, new_knowledge)


# Running tally for one analysis run, shared by both passes so the
# progress counts can be written to the repo after every file.
@dataclass
class _AnalysisProgress:
    # (file, knowledge) pairs whose structure pass succeeded this run.
    processed: list[tuple[RepositoryFile, FileKnowledge]] = field(default_factory=list)
    skipped_count: int = 0        # files with no extractor
    supported_count: int = 0      # files with an extractor
    failed_ids: set[int] = field(default_factory=set)  # a set, so a file never counts twice
    new_summaries_count: int = 0  # summaries generated in THIS run

    # Supported files that have a summary - cumulative, so summaries from
    # earlier (e.g. paused) runs count too.
    @property
    def analyzed_count(self) -> int:
        return sum(1 for _, knowledge in self.processed if knowledge.summary is not None)


# Writes the current counts onto the repo, so a client polling the
# status endpoint sees progress while analysis is still running.
def _write_progress(db: Session, repository: Repository, progress: _AnalysisProgress) -> None:
    update_repository_analysis_summary(
        db,
        repository,
        progress.analyzed_count,
        len(progress.failed_ids),
        progress.skipped_count,
    )


# Pass 1 (no LLM): extracts and saves structure for every supported file.
# One file failing to parse (or missing on disk) is logged and counted as
# failed - it doesn't stop the rest.
def _run_structure_pass(
    db: Session,
    repository: Repository,
    files: list[RepositoryFile],
    progress: _AnalysisProgress,
) -> None:
    for repository_file in files:
        if get_extractor(repository_file.path) is None:
            progress.skipped_count += 1
            continue

        progress.supported_count += 1
        try:
            source_code = (Path(repository.storage_path) / repository_file.path).read_bytes()
            knowledge = extract_file_structure(db, repository_file, source_code)
            progress.processed.append((repository_file, knowledge))
        except Exception as e:
            print(f"Failed to extract structure from {repository_file.path}: {e}")
            progress.failed_ids.add(repository_file.id)


# Pass 3 (LLM): summarizes only files whose summary is still empty - new
# files, changed files, or ones a previous run didn't get to. Each summary
# is saved right away. A per-file error leaves that summary empty so the
# next run retries it. Quota and setup errors are NOT per-file problems,
# so they're re-raised to stop the whole pass.
def _run_summary_pass(
    db: Session,
    repository: Repository,
    progress: _AnalysisProgress,
) -> None:
    pending = [
        (repository_file, knowledge)
        for repository_file, knowledge in progress.processed
        if knowledge.summary is None
    ]

    for repository_file, knowledge in pending:
        try:
            source_code = (Path(repository.storage_path) / repository_file.path).read_bytes()
            summary = _summarize_file(repository_file.path, source_code)
            update_knowledge_summary(db, knowledge, summary)
            progress.new_summaries_count += 1
        except (DailyLimitReached, LLMNotConfiguredError):
            raise
        except Exception as e:
            print(f"Failed to summarize {repository_file.path}: {e}")
            progress.failed_ids.add(repository_file.id)

        _write_progress(db, repository, progress)


# Stops analysis cleanly when the daily LLM quota runs out: saves the
# counts, marks the repo PAUSED with a readable message, and returns
# normally - so the background runner doesn't treat it as a failure.
# Re-running analysis later picks up only the files still missing a summary.
def _pause_for_daily_limit(
    db: Session,
    repository: Repository,
    progress: _AnalysisProgress,
    summary_pass_finished: bool,
) -> None:
    _write_progress(db, repository, progress)

    # New file summaries arrived, but the repo summary wasn't redone - the
    # old one is stale. Clearing it makes the next run regenerate it.
    if progress.new_summaries_count > 0:
        update_repository_summary(db, repository, None)

    counts_text = f"{progress.analyzed_count} of {progress.supported_count} files summarized"
    if summary_pass_finished:
        message = (
            f"Daily LLM quota reached before the repository summary was generated "
            f"({counts_text}). Run analysis again later to continue."
        )
    else:
        message = f"Daily LLM quota reached: {counts_text}. Run analysis again later to continue."

    print(message)
    update_repository_status(db, repository, RepositoryStatus.PAUSED, message)


# Runs the full analysis for a repo, in passes:
#   1. structure (Tree-sitter, no LLM) for every supported file
#   2. dependency graph - coming in task 5.4
#   3. LLM summaries for files missing one, then the repo-level summary
# Ends ANALYZED, or PAUSED if the daily LLM quota runs out. Any other
# unexpected error propagates to the background runner, which marks FAILED.
def analyze_repository(db: Session, repository: Repository) -> dict:
    update_repository_status(db, repository, RepositoryStatus.ANALYZING)

    files = get_files_by_repository(db, repository.id)
    progress = _AnalysisProgress()

    # --- Pass 1: structure (no LLM) ---
    _run_structure_pass(db, repository, files, progress)
    _write_progress(db, repository, progress)

    # --- Pass 2: dependency graph (task 5.4) goes here ---
    # It only needs the structure saved above, never the LLM quota.

    # --- Pass 3: LLM summaries, then the repo-level summary ---
    summary_pass_finished = False
    try:
        _run_summary_pass(db, repository, progress)
        summary_pass_finished = True

        # Only regenerate the repo-level summary if something actually
        # changed this run - avoids a wasted LLM call when every file
        # already had a summary (e.g. a re-scan with nothing new). Uses
        # whatever file summaries exist, even if some files failed.
        if progress.new_summaries_count > 0 or repository.repo_summary is None:
            generate_repository_summary(db, repository)
    except DailyLimitReached:
        _pause_for_daily_limit(db, repository, progress, summary_pass_finished)
        return _analysis_result(progress, daily_limit_reached=True)

    _write_progress(db, repository, progress)
    update_repository_status(db, repository, RepositoryStatus.ANALYZED)
    return _analysis_result(progress, daily_limit_reached=False)


# Builds the dict analyze_repository() returns - same keys as before the
# pass split, so callers don't need to change.
def _analysis_result(progress: _AnalysisProgress, daily_limit_reached: bool) -> dict:
    return {
        "analyzed_count": progress.analyzed_count,
        "failed_count": len(progress.failed_ids),
        "skipped_count": progress.skipped_count,
        "daily_limit_reached": daily_limit_reached,
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