---
applyTo: "**/*.py"
---

# Python file conventions

- Use native type hints (`str | None`, `list[int]`); annotate public functions.
- Prefer `pathlib.Path` over `os.path`. No bare `except:` — catch specific exceptions.
- Use `logging`, never `print()`, in library/application code.
- Tabular data: prefer `polars` (lazy `pl.LazyFrame`) over `pandas`.
- Run `uv run ruff check --fix && uv run ruff format` before considering a change done.
