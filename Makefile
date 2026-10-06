.PHONY: api-check check api-dev

# Same commands as CI (.github/workflows/ci.yml).
api-check:
	cd services/api && uv sync --frozen \
		&& uv run ruff format --check . ../../evals \
		&& uv run ruff check . ../../evals --config pyproject.toml \
		&& uv run mypy \
		&& uv run pytest \
		&& uv run python ../../evals/runner.py --suite _smoke

check: api-check

api-dev:
	cd services/api && uv run uvicorn app.main:app --reload
