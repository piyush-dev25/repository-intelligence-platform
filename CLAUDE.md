# CLAUDE.md — Repository Intelligence Platform

## What this project is
A resume/learning project: users upload a public GitHub repo or zip; the platform
analyzes it (Tree-sitter structure, dependency graph, LLM summaries, embeddings),
shows a repo dashboard with an interactive dependency graph, and offers a chat
that answers architecture / search / dependency / impact questions with file+line
citations. Not a startup — prefer simple, working solutions over scale.

Full plan and locked design decisions: `docs/roadmap/v1.md`. Follow it.
If a task seems to need a decision the roadmap doesn't cover, STOP and ask —
do not decide it yourself.

## Stack
- Backend: FastAPI (Python), sync SQLAlchemy 2.0, Alembic, PostgreSQL, Qdrant
- LLM: Groq via `app/services/llm_service.py` (all LLM calls go through it)
- Parsing: Tree-sitter, one extractor per language in `app/services/extractors/`
- Frontend: Next.js + TypeScript + Tailwind (+ shadcn/ui), React Flow for the graph
- Infra: Docker Compose (Postgres + Qdrant)

## Backend conventions (match existing code)
- Layering: `api/` (thin routers) → `services/` (logic) → `data_access/` (DB queries).
  Routers never query the DB directly.
- Models: SQLAlchemy 2.0 `Mapped[...]` / `mapped_column(...)` style.
- Pydantic schemas live in `app/schemas/`. Config/env vars only via `app/core/config.py`.
- Every schema change = a NEW Alembic migration. Never edit existing migrations.
- Plain-English comment above each function explaining what it does and why.
- Tests: pytest in `backend/tests/`. New logic (esp. import resolution, chunking,
  context recipes) ships with tests.

## Guardrails
- NO GIT. Never run any git command (no add, commit, push, pull, checkout,
  branch, reset, stash — nothing). Piyush handles all version control himself.
- Plan first. Present the plan, wait for approval, then edit.
- Stay inside the task's scope. Don't refactor, rename, or "improve" unrelated code.
- Don't add new dependencies without asking.
- Don't touch the frontend in backend tasks, and vice versa.
- Don't modify existing extractor tests unless the task is about extractors.
- Never commit `.env` or secrets.
- When something fails: explain the likely cause first, then propose a fix.
  No sweeping changes to make an error disappear.

## Communication
- Use simple, plain language. If a technical term is needed, explain it in one line.

## After every task
1. STOP after making changes. Do not start the next task — Piyush tests manually first.
2. Give a summary in simple language:
   - **What changed:** each file touched, and why
   - **How to test it manually:** exact steps/commands and what result to expect
   - **Watch out for:** anything risky, unfinished, or assumed
   - **Concepts used:** key ideas/patterns in this change, so Piyush can study them
3. Wait for Piyush to confirm it works before continuing.
4. Tick the task's checkbox in `docs/roadmap/v1.md` as the last step of the task.

## Commands (verify these match your setup)
- Start services: `docker compose up -d`
- Run backend (from `backend/`): `uvicorn app.main:app --reload`
- Tests (from `backend/`): `pytest`
- New migration: `alembic revision --autogenerate -m "<message>"`
- Apply migrations: `alembic upgrade head`