# Orsyn

Orsyn (working name) is an AI-native supply network on verified Indian suppliers. Buyers send an RFQ from a drawing and get verified quotes, documents and delivery handled. Suppliers join free on WhatsApp or web and get a showcase page, an export roadmap with benefits, and AI-drafted quotes.

## Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node 24 and pnpm 10 via corepack (`corepack enable`)

## Run the api locally

```
cd services/api && uv sync && uv run uvicorn app.main:app --reload
```

Health check: http://localhost:8000/health (or `make api-dev`).

## Run the web app locally

```
pnpm install && pnpm --filter web dev
```

Open http://localhost:3000 (or `make web-dev`).

## Tests and checks

`make check` runs everything CI runs. `make api-check` and `make web-check` run one side. The raw commands:

```
# api (from services/api)
uv sync --frozen
uv run ruff format --check . ../../evals
uv run ruff check . ../../evals --config pyproject.toml
uv run mypy
uv run pytest
uv run python ../../evals/runner.py --suite _smoke

# web (from the repo root)
pnpm install --frozen-lockfile
pnpm --filter web lint
pnpm --filter web format
pnpm --filter web typecheck
pnpm --filter web test
pnpm --filter web build
```

## Layout

See `CLAUDE.md` for the repo layout, rules and workflow. Design plans are in `docs/plans/`.

## Repo setup (admin, one-off)

Labels (needs repo admin):

```
gh label create needs-founder --color B42318
gh label create security-review --color B45309
gh label create rules-change --color 1F4FD8
for m in M1 M2 M3 M4 M5; do gh label create "$m" --color 5B6470; done
```

Proposed branch protection for `main` (pending founder confirmation, E0 Q8):

- require status checks `api` and `web`
- 1 approving review (Veeru), dismiss stale reviews
- no force-push
- linear history
