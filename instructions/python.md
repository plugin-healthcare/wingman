# Python Stack

Additional instructions for Python projects. Applied on top of `core/AGENTS.md`.

## Package Management

- Use `uv` for all dependency and environment management (`uv add`, `uv run`, `uv sync`).
- Never use `pip install` directly in a project with a `pyproject.toml`.
- Pin Python version in `.python-version`.

## Code Style

- Formatter and linter: `ruff` — run with `uv run ruff check --fix && uv run ruff format`.
- Type hints on all public functions and methods. Use `ty` or `mypy` to check.
- Prefer `pathlib.Path` over `os.path`.
- No bare `except:` — always catch specific exceptions.

## Data

- Prefer `polars` over `pandas` for all tabular data work.
- Use lazy evaluation (`pl.LazyFrame`) by default; collect only when needed.
- When in doubt about Polars API or syntax, use the `ask_polars` MCP tool.

## Testing

- Framework: `pytest`. Run with `uv run pytest`.
- Test files mirror source layout: `src/foo/bar.py` → `tests/foo/test_bar.py`.
- Use `pytest.mark.parametrize` for data-driven cases.
- Mock external I/O — tests must be runnable offline.

## Project Layout

```
src/<package>/    ← application code
tests/            ← mirrors src/ layout
pyproject.toml    ← single source of truth for metadata + deps
.python-version   ← pinned Python version for uv
```
