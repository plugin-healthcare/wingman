# Core — Generic DevOps Cycle

These instructions apply to all projects regardless of stack.

## Workflow

- Before implementing anything non-trivial, draft a plan and confirm it.
- Work in small, reviewable increments. One logical change per commit.
- Always run tests and lint before marking work done.
- When blocked, say so — don't silently guess.

## Git

- Commit messages: imperative mood, max 72 chars subject line.
- Never commit secrets, credentials, or local config files.
- Branch names: `<type>/<short-description>` (e.g. `feat/add-auth`, `fix/null-pointer`).

## Code Review

- Prefer clear over clever. Code is read more than written.
- Flag todos and tech debt with `# TODO(name): reason` so they're searchable.
- Tests are not optional — new behaviour without tests is not done.

## CI / Build

- A failing build or test suite must be fixed before adding new work.
- If a CI step is flaky, flag it — don't re-run until it passes by luck.
- Keep build times fast: avoid unnecessary dependencies.

## Communication

- Surface ambiguity early. Wrong assumptions compound.
- Document decisions that aren't obvious from the code (why, not what).

---

# Python Stack

Additional instructions for Python projects. Applied on top of the base instructions.

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
- When in doubt about Polars API or syntax, use the `polars` MCP server.

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
