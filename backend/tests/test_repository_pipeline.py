from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.repository import RepositoryStatus
from app.services import repository_service


# Stand-in for a real SQLAlchemy session - just records whether the
# pipeline rolled back and closed it. No database needed.
class FakeSession:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


# Swaps the DB-touching pieces inside repository_service for fakes, and
# returns the shared session + a list that records each step's call order.
@pytest.fixture
def fake_pipeline(monkeypatch):
    session = FakeSession()
    repo = SimpleNamespace(id=1, status=RepositoryStatus.SCANNING, error_message=None)
    calls = []

    def fake_update_status(db, db_repo, status, error_message=None):
        db_repo.status = status
        db_repo.error_message = error_message
        calls.append(("status", status))
        return db_repo

    monkeypatch.setattr(repository_service, "SessionLocal", lambda: session)
    monkeypatch.setattr(repository_service, "get_repository_by_id", lambda db, rid: repo)
    monkeypatch.setattr(repository_service, "update_repository_status", fake_update_status)
    monkeypatch.setattr(
        repository_service, "_run_filesystem_scan_step",
        lambda db, r: calls.append("scan") or r,
    )
    monkeypatch.setattr(
        repository_service, "analyze_repository",
        lambda db, r: calls.append("analyze"),
    )
    return SimpleNamespace(session=session, repo=repo, calls=calls)


def test_pipeline_runs_scan_then_analyze(fake_pipeline):
    repository_service.run_repository_pipeline(1, run_scan=True, run_analyze=True)

    assert fake_pipeline.calls == ["scan", "analyze"]
    assert fake_pipeline.session.closed


def test_pipeline_skips_analyze_when_flag_off(fake_pipeline):
    repository_service.run_repository_pipeline(1, run_scan=True, run_analyze=False)

    assert fake_pipeline.calls == ["scan"]
    assert fake_pipeline.session.closed


def test_pipeline_analyze_only(fake_pipeline):
    repository_service.run_repository_pipeline(1, run_scan=False, run_analyze=True)

    assert fake_pipeline.calls == ["analyze"]


def test_pipeline_failure_marks_repo_failed(fake_pipeline, monkeypatch):
    def broken_scan(db, repo):
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(repository_service, "_run_filesystem_scan_step", broken_scan)

    repository_service.run_repository_pipeline(1, run_scan=True, run_analyze=True)

    assert fake_pipeline.repo.status == RepositoryStatus.FAILED
    assert fake_pipeline.repo.error_message == "Scanning failed: disk exploded"
    assert "analyze" not in fake_pipeline.calls
    assert fake_pipeline.session.rolled_back
    assert fake_pipeline.session.closed


def test_pipeline_analysis_failure_names_the_stage(fake_pipeline, monkeypatch):
    def broken_analyze(db, repo):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(repository_service, "analyze_repository", broken_analyze)

    repository_service.run_repository_pipeline(1, run_scan=True, run_analyze=True)

    assert fake_pipeline.repo.error_message == "Analysis failed: LLM down"


def test_pipeline_missing_repo_does_nothing(fake_pipeline, monkeypatch):
    monkeypatch.setattr(repository_service, "get_repository_by_id", lambda db, rid: None)

    repository_service.run_repository_pipeline(1, run_scan=True, run_analyze=True)

    assert fake_pipeline.calls == []
    assert fake_pipeline.session.closed


@pytest.mark.parametrize("status", [RepositoryStatus.SCANNING, RepositoryStatus.ANALYZING])
def test_guard_blocks_while_processing(status):
    repo = SimpleNamespace(status=status)

    with pytest.raises(HTTPException) as exc_info:
        repository_service._ensure_not_processing(repo)

    assert exc_info.value.status_code == 409


@pytest.mark.parametrize(
    "status",
    [s for s in RepositoryStatus if s not in (RepositoryStatus.SCANNING, RepositoryStatus.ANALYZING)],
)
def test_guard_allows_other_statuses(status):
    repository_service._ensure_not_processing(SimpleNamespace(status=status))
