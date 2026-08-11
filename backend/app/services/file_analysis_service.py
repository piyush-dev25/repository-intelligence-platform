from sqlalchemy.orm import Session

from app.models.repository import RepositoryFile
from app.models.file_knowledge import FileKnowledge
from app.services.extractors.registry import get_extractor
from app.services.llm_service import llm_service
from app.data_access.file_knowledge_data_access import (
    create_knowledge,
    get_knowledge_by_file,
    update_knowledge,
)


# Builds the prompt sent to the LLM for a single file's summary. Kept as
# its own function so the prompt wording can be tweaked without touching
# the orchestration logic around it.
def _build_summary_prompt(file_path: str, source_code: str) -> str:
    return (
        f"Explain in plain English what this file does, in 2-3 sentences. "
        f"File: {file_path}\n\n{source_code}"
    )


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
    prompt = _build_summary_prompt(repository_file.path, source_code.decode("utf-8"))
    summary = llm_service.generate(prompt)

    existing = get_knowledge_by_file(db, repository_file.id)
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