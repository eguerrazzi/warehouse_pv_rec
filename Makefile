.PHONY: install lock lint format test

install:
	uv sync

# Update uv.lock and the pip export used by the conda environment (environment.yml).
lock:
	uv lock
	uv export --format requirements-txt --no-hashes --all-extras --all-groups --no-emit-project --quiet -o requirements.lock.txt

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest
