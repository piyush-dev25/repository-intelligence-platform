from pathlib import Path

from sqlalchemy import select

from unittest.mock import patch

from app.db.database import SessionLocal
from app.models.repository import RepositoryFile, Repository
from app.services.file_analysis_service import analyze_file
from app.data_access.file_knowledge_data_access import get_knowledge_by_file
from app.services.llm_service import llm_service



def test_analyze_file_creates_knowledge_end_to_end():
    db = SessionLocal()
    try:
        # Grab the first .js file we can find - most-tested extractor,
        # and avoids needing to hardcode a specific repository/file id.
        statement = select(RepositoryFile).where(RepositoryFile.extension == ".js")
        repository_file = db.execute(statement).scalars().first()
        assert repository_file is not None, "No .js RepositoryFile found - ingest a repo first"

        repository = db.get(Repository, repository_file.repository_id)
        assert repository is not None
        assert repository.storage_path is not None, "Repository has no storage_path set"

        # RepositoryFile.path is relative to the repo's storage location -
        # join them to get the real file location on disk.
        full_path = Path(repository.storage_path) / repository_file.path
        source_code = full_path.read_bytes()

        knowledge = analyze_file(db, repository_file, source_code)

        assert knowledge is not None
        assert knowledge.language == "javascript"
        assert len(knowledge.entities) > 0
        assert isinstance(knowledge.summary, str) and len(knowledge.summary) > 0
        assert knowledge.source_content_hash == repository_file.content_hash

        # Confirm it's actually retrievable via the data-access layer too,
        # not just returned in memory - proves the DB write really happened.
        saved = get_knowledge_by_file(db, repository_file.id)
        assert saved is not None
        assert saved.summary == knowledge.summary
    finally:
        db.close()


def test_analyze_file_skips_unchanged_file():
    db = SessionLocal()
    try:
        statement = select(RepositoryFile).where(RepositoryFile.extension == ".js")
        repository_file = db.execute(statement).scalars().first()
        assert repository_file is not None

        repository = db.get(Repository, repository_file.repository_id)
        full_path = Path(repository.storage_path) / repository_file.path
        source_code = full_path.read_bytes()

        with patch.object(llm_service, "generate", wraps=llm_service.generate) as mock_generate:
            # First call - may create or update depending on whether earlier
            # tests already ran against this file. Either way, this call
            # itself should hit the LLM exactly once.
            first = analyze_file(db, repository_file, source_code)
            calls_after_first = mock_generate.call_count

            # Second call, same unchanged file - hash matches, should
            # return the same row without calling the LLM again.
            second = analyze_file(db, repository_file, source_code)

            assert second is not None
            assert second.id == first.id
            assert mock_generate.call_count == calls_after_first
    finally:
        db.close()