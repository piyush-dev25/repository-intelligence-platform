from types import SimpleNamespace

import httpx
import pytest
from groq import AuthenticationError

from app.models.repository import RepositoryStatus
from app.services import file_analysis_service as analysis
from app.services import llm_service as llm_module
from app.services.llm_service import DailyLimitReached, LLMNotConfiguredError, LLMService


# Stand-in extractor: every supported file gets the same simple structure.
# Files containing "BROKEN" make it raise, to simulate a parse failure.
class FakeExtractor:
    def extract(self, source_code: bytes) -> dict:
        if b"BROKEN" in source_code:
            raise ValueError("cannot parse")
        return {"language": "python", "entities": [{"name": "f", "kind": "function"}], "imports": []}


# In-memory replacement for the database: holds knowledge rows by file id
# and records what analysis wrote to the repo (statuses, counts).
class FakeStore:
    def __init__(self):
        self.knowledge = {}            # repository_file_id -> knowledge object
        self.statuses = []             # (status, error_message) in order
        self.counts_history = []       # (analyzed, failed, skipped) after each write
        self.repo_summary_calls = 0


# Builds a repo whose files live in pytest's tmp_path, and patches every
# DB / LLM touchpoint inside file_analysis_service with fakes.
# `summarize` decides what the fake LLM does for each file path.
@pytest.fixture
def make_repo(tmp_path, monkeypatch):
    store = FakeStore()

    def build(file_contents: dict[str, str], summarize, repo_summary=None):
        files = []
        for index, (path, content) in enumerate(file_contents.items(), start=1):
            if content is not None:  # None = file missing on disk
                (tmp_path / path).write_text(content)
            files.append(SimpleNamespace(id=index, path=path, content_hash=f"hash-{content}"))

        repository = SimpleNamespace(id=1, storage_path=str(tmp_path), repo_summary=repo_summary)

        def fake_create(db, knowledge):
            store.knowledge[knowledge.repository_file_id] = knowledge
            return knowledge

        def fake_update_structure(db, existing, language, entities, imports, source_content_hash, clear_summary):
            existing.language = language
            existing.entities = entities
            existing.imports = imports
            existing.source_content_hash = source_content_hash
            if clear_summary:
                existing.summary = None
            return existing

        def fake_update_summary(db, knowledge, summary):
            knowledge.summary = summary
            return knowledge

        def fake_status(db, repo, status, error_message=None):
            store.statuses.append((status, error_message))
            return repo

        def fake_counts(db, repo, analyzed, failed, skipped):
            store.counts_history.append((analyzed, failed, skipped))
            return repo

        def fake_repo_summary(db, repo):
            store.repo_summary_calls += 1
            # Lets a test simulate the quota running out at the repo-summary step.
            analysis._summarize_file("__repo__", b"")
            repo.repo_summary = "repo summary"
            return repo

        def fake_set_repo_summary(db, repo, value):
            repo.repo_summary = value
            return repo

        monkeypatch.setattr(analysis, "get_files_by_repository", lambda db, rid: files)
        monkeypatch.setattr(analysis, "get_knowledge_by_file", lambda db, fid: store.knowledge.get(fid))
        monkeypatch.setattr(analysis, "create_knowledge", fake_create)
        monkeypatch.setattr(analysis, "update_knowledge_structure", fake_update_structure)
        monkeypatch.setattr(analysis, "update_knowledge_summary", fake_update_summary)
        monkeypatch.setattr(analysis, "update_repository_status", fake_status)
        monkeypatch.setattr(analysis, "update_repository_analysis_summary", fake_counts)
        monkeypatch.setattr(analysis, "update_repository_summary", fake_set_repo_summary)
        monkeypatch.setattr(analysis, "generate_repository_summary", fake_repo_summary)
        monkeypatch.setattr(
            analysis, "get_extractor",
            lambda path: FakeExtractor() if path.endswith(".py") else None,
        )
        monkeypatch.setattr(analysis, "_summarize_file", lambda path, code: summarize(path))

        return repository, files

    return build, store


# Fake LLM that records which files it was asked to summarize, and can be
# told to fail on specific files or run out of quota after N calls.
class ScriptedLLM:
    def __init__(self, fail_on=(), quota_after=None, quota_on_repo_summary=False):
        self.calls = []
        self.fail_on = set(fail_on)
        self.quota_after = quota_after
        self.quota_on_repo_summary = quota_on_repo_summary

    def __call__(self, path):
        if path == "__repo__":
            if self.quota_on_repo_summary:
                raise DailyLimitReached("rpd")
            return "repo"
        if self.quota_after is not None and len(self.calls) >= self.quota_after:
            raise DailyLimitReached("rpd")
        self.calls.append(path)
        if path in self.fail_on:
            raise RuntimeError("LLM hiccup")
        return f"summary of {path}"


def test_structure_saved_even_when_summary_fails(make_repo):
    build, store = make_repo
    llm = ScriptedLLM(fail_on={"b.py"})
    repository, _ = build({"a.py": "x = 1", "b.py": "y = 2"}, llm)

    result = analysis.analyze_repository(None, repository)

    # b.py's structure is saved even though its summary failed.
    assert store.knowledge[2].entities == [{"name": "f", "kind": "function"}]
    assert store.knowledge[2].summary is None
    assert store.knowledge[1].summary == "summary of a.py"
    assert result["failed_count"] == 1
    assert result["analyzed_count"] == 1
    # Per-file (non-quota) failure: repo summary still generated, run ends ANALYZED.
    assert store.repo_summary_calls == 1
    assert store.statuses[-1] == (RepositoryStatus.ANALYZED, None)


def test_content_change_clears_and_regenerates_summary(make_repo, monkeypatch):
    build, store = make_repo
    repository, files = build({"a.py": "x = 1", "b.py": "y = 2"}, ScriptedLLM())
    analysis.analyze_repository(None, repository)

    # a.py changes on disk; b.py doesn't.
    files[0].content_hash = "hash-new"
    llm = ScriptedLLM()
    monkeypatch.setattr(analysis, "_summarize_file", lambda path, code: llm(path))

    analysis.analyze_repository(None, repository)

    assert llm.calls == ["a.py"]
    assert store.knowledge[1].source_content_hash == "hash-new"
    assert store.knowledge[1].summary == "summary of a.py"
    # A new summary arrived this run, so the repo summary is regenerated too.
    assert store.repo_summary_calls == 2


def test_unchanged_files_are_not_resummarized(make_repo, monkeypatch):
    build, store = make_repo
    repository, _ = build({"a.py": "x = 1"}, ScriptedLLM())
    analysis.analyze_repository(None, repository)

    llm = ScriptedLLM()
    monkeypatch.setattr(analysis, "_summarize_file", lambda path, code: llm(path))
    analysis.analyze_repository(None, repository)

    assert llm.calls == []
    assert store.repo_summary_calls == 1  # nothing new, repo summary already exists


def test_daily_limit_pauses_with_message(make_repo):
    build, store = make_repo
    llm = ScriptedLLM(quota_after=1)
    repository, _ = build({"a.py": "1", "b.py": "2", "c.py": "3", "readme.md": "hi"}, llm)

    result = analysis.analyze_repository(None, repository)

    assert result["daily_limit_reached"] is True
    status, message = store.statuses[-1]
    assert status == RepositoryStatus.PAUSED
    assert message == "Daily LLM quota reached: 1 of 3 files summarized. Run analysis again later to continue."
    # Files are still pending because of the quota -> no repo summary.
    assert store.repo_summary_calls == 0
    assert store.counts_history[-1] == (1, 0, 1)


def test_daily_limit_during_repo_summary_pauses(make_repo):
    build, store = make_repo
    repository, _ = build({"a.py": "1"}, ScriptedLLM(quota_on_repo_summary=True), repo_summary="old")

    analysis.analyze_repository(None, repository)

    status, message = store.statuses[-1]
    assert status == RepositoryStatus.PAUSED
    assert message.startswith("Daily LLM quota reached before the repository summary was generated")
    # The old repo summary is stale (a.py got a new summary) -> cleared, so resume regenerates it.
    assert repository.repo_summary is None


def test_resume_only_summarizes_missing_summaries(make_repo, monkeypatch):
    build, store = make_repo
    repository, _ = build({"a.py": "1", "b.py": "2", "c.py": "3"}, ScriptedLLM(quota_after=1))
    analysis.analyze_repository(None, repository)

    llm = ScriptedLLM()
    monkeypatch.setattr(analysis, "_summarize_file", lambda path, code: llm(path))
    result = analysis.analyze_repository(None, repository)

    assert llm.calls == ["b.py", "c.py"]
    assert result["analyzed_count"] == 3  # cumulative, includes a.py from the first run
    assert store.statuses[-1] == (RepositoryStatus.ANALYZED, None)
    assert store.repo_summary_calls == 1


def test_counts_written_after_every_summary(make_repo):
    build, store = make_repo
    repository, _ = build({"a.py": "1", "b.py": "2"}, ScriptedLLM())

    analysis.analyze_repository(None, repository)

    # After structure pass, after a.py, after b.py, final.
    assert store.counts_history == [(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 0, 0)]


def test_skipped_and_structure_failures(make_repo):
    build, store = make_repo
    llm = ScriptedLLM()
    repository, _ = build(
        {"a.py": "BROKEN", "b.py": "ok", "notes.txt": "text", "gone.py": None},
        llm,
    )

    result = analysis.analyze_repository(None, repository)

    assert result["skipped_count"] == 1   # notes.txt has no extractor
    assert result["failed_count"] == 2    # a.py fails to parse, gone.py missing on disk
    assert result["analyzed_count"] == 1  # b.py
    assert llm.calls == ["b.py"]
    assert store.statuses[-1] == (RepositoryStatus.ANALYZED, None)


def test_llm_not_configured_propagates(make_repo):
    build, store = make_repo

    def no_key(path):
        raise LLMNotConfiguredError("GROQ_API_KEY is not configured.")

    repository, _ = build({"a.py": "1", "b.py": "2"}, no_key)

    with pytest.raises(LLMNotConfiguredError):
        analysis.analyze_repository(None, repository)

    # Structure was saved before the LLM was ever needed.
    assert set(store.knowledge) == {1, 2}
    assert RepositoryStatus.ANALYZED not in [status for status, _ in store.statuses]


def test_llm_service_starts_without_key(monkeypatch):
    monkeypatch.setattr(llm_module, "GROQ_API_KEY", None)

    service = LLMService()  # must not raise

    with pytest.raises(LLMNotConfiguredError):
        service.generate("hello")


def test_groq_auth_error_becomes_not_configured(monkeypatch):
    def reject(**kwargs):
        response = httpx.Response(401, request=httpx.Request("POST", "https://api.groq.com"))
        raise AuthenticationError("invalid api key", response=response, body=None)

    service = LLMService()
    service.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=reject)),
    )

    with pytest.raises(LLMNotConfiguredError):
        service.generate("hello")
