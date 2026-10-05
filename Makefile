.PHONY: api-check web-check check api-dev web-dev

# Same commands as CI (.github/workflows/ci.yml).
api-check:
	cd services/api && uv sync --frozen \
		&& uv run ruff format --check . ../../evals \
		&& uv run ruff check . ../../evals --config pyproject.toml \
		&& uv run mypy \
		&& uv run pytest \
		&& uv run python ../../evals/runner.py --suite _smoke

web-check:
	pnpm install --frozen-lockfile
	pnpm --filter web lint
	pnpm --filter web format
	pnpm --filter web typecheck
	pnpm --filter web test
	pnpm --filter web build

check: api-check web-check

api-dev:
	cd services/api && uv run uvicorn app.main:app --reload

web-dev:
	pnpm --filter web dev
