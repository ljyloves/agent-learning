# FlowGate Working Agreement

## Start Here

- Read `FlowGate_PROJECT_HANDOFF.md` before changing code.
- Treat migrations, tests, running services, and Git history as stronger evidence than chat summaries.
- The project runs in WSL `Ubuntu-24.04` at `/home/lijinyang/FlowGate`.

## Required Checks

Before implementing a new BIO task, inspect:

```bash
docker compose ps
docker compose exec backend alembic current
docker compose exec backend alembic check
docker compose exec backend python -m unittest discover -s tests -v
```

After implementation, rerun the relevant checks and record the result in `FlowGate_PROJECT_HANDOFF.md`.

## Engineering Rules

- Preserve existing user changes and keep each BIO task scoped to its acceptance criteria.
- Use Alembic for every persistent schema or seed-data change.
- Keep question, source, resource, taxonomy, and paper-job data traceable through explicit database relations.
- Add focused tests for schemas, migrations, persistence, APIs, and workflow behavior according to change risk.
- Do not commit `.env`, credentials, API keys, database dumps, generated caches, or build output.
- Keep `.env.example` usable with placeholder values only.
- Do not treat local Docker volumes as the only copy of important seed or acceptance data.

## Progress Protocol

- Do not invent the next BIO task ID or acceptance criteria.
- At the end of each accepted task, update the status table, technical baseline, validation results, risks, and next decision point in `FlowGate_PROJECT_HANDOFF.md`.
- Prefer one small Git commit per accepted BIO task once version control is initialized.
