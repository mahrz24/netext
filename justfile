sync-env ENV:
    uv sync --group {{ENV}} --all-extras
    uv pip install -e .

serve-docs: (sync-env "docs")
    uv run mkdocs serve
