---
description: "Add type hints to Python functions and variables. Use on a file or selected functions missing annotations."
agent: agent
tools: [read, edit, search]
---

Add type hints to the provided Python code:

1. Annotate all function parameters and return types.
2. Add variable annotations where the type is not obvious from assignment.
3. Use `from __future__ import annotations` at the top of each file if not present.
4. Prefer built-in generics (`list[str]`, `dict[str, int]`) over `typing.List` / `typing.Dict` (Python 3.9+).
5. Use `X | None` over `Optional[X]` (Python 3.10+).
6. Do NOT change any logic — only add annotations.

After editing, verify with: `uv run mypy <file>` or `uv run ty check`.
