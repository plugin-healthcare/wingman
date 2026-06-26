---
description: "Fix ruff lint and format errors in Python files. Use after running ruff check to resolve violations."
agent: agent
tools: [read, edit, execute]
---

Fix all ruff lint and formatting issues in the provided Python code.

1. Run `uv run ruff check --output-format=concise` to see current violations.
2. Fix each violation. For non-obvious fixes, leave a brief inline comment explaining the change.
3. Run `uv run ruff format` to apply formatting.
4. Re-run `uv run ruff check` to confirm zero violations.

Do NOT suppress rules with `# noqa` unless the violation is a known false positive — fix the code instead.
