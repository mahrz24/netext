sync-env ENV:
    uv sync --group {{ENV}} --all-extras
    uv pip install -e .

serve-docs: (sync-env "docs")
    uv run mkdocs serve

lint *FILES: (sync-env "linting")
    uv run ruff format {{FILES}}
    uv run ruff check --fix {{FILES}}

test: (sync-env "testing")
    uv run pytest tests --benchmark-skip

benchmark: (sync-env "testing")
    uv run pytest tests  --benchmark-only
