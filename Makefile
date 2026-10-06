.PHONY: api-check check api-dev

# Same commands as CI (.github/workflows/ci.yml).
api-check:
	cd services/api && uv sync --frozen \
		&& uv run ruff format --check . \
		&& uv run ruff check . --config pyproject.toml \
		&& uv run mypy app tests \
		&& uv run pytest

check: api-check

api-dev:
	cd services/api && uv run uvicorn app.main:app --reload
