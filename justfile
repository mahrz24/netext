sync-env ENV:
    pixi install -e {{ENV}}

serve-docs: (sync-env "docs")
    pixi run -e docs mkdocs serve

lint *FILES: (sync-env "linting")
    pixi run -e linting ruff format {{FILES}}
    pixi run -e linting ruff check --fix {{FILES}}

test: (sync-env "testing")
    pixi run -e testing pytest tests --benchmark-skip

benchmark: (sync-env "benchmark")
    pixi run -e benchmark pytest tests --benchmark-only
