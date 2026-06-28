"""opencode support: agent translation and command generation.

Translates installed GitHub Copilot agents (``.github/agents/*.agent.md``) to
opencode format (``.opencode/agents/*.md``) and generates starter opencode
commands in ``.opencode/commands/``.

Translation rules (Copilot → opencode frontmatter):
- ``description``      → kept as-is
- ``tools``            → ``mode: subagent`` + deny permissions for missing capabilities
- ``user-invocable``   → dropped (opencode subagents are always @ mentionable)
- body                 → copied unchanged
"""

from __future__ import annotations

import re
from pathlib import Path

from wingman.audit import parse_frontmatter
from wingman.core import repo_root

COPILOT_AGENTS_DIR = Path(".github") / "agents"
OPENCODE_AGENTS_DIR = Path(".opencode") / "agents"
OPENCODE_COMMANDS_DIR = Path(".opencode") / "commands"

# Tools that imply write access in Copilot agent definitions.
_WRITE_TOOLS = frozenset({"write", "create", "edit", "apply_patch", "patch"})
# Tools that imply bash/shell access.
_BASH_TOOLS = frozenset({"bash", "shell", "terminal", "run", "execute"})

# ── Starter commands ───────────────────────────────────────────────────────────

_COMMANDS: dict[str, str] = {
    "check.md": (
        "---\n"
        'description: "Run lint and test gate (ruff + pytest)"\n'
        "---\n\n"
        "Run the project check gate:\n\n"
        "!`uv run ruff check --fix && uv run ruff format && uv run pytest`\n\n"
        "Report any failures and suggest fixes.\n"
    ),
    "review.md": (
        "---\n"
        'description: "Review staged or recent changes for quality issues"\n'
        "---\n\n"
        "@gilfoyle Review the staged changes for quality, correctness, and"
        " performance issues.\n\n"
        "!`git diff --staged`\n"
    ),
}


# ── Frontmatter serialisation ─────────────────────────────────────────────────


def _parse_tools(raw: str) -> list[str]:
    """Parse a YAML inline list or space-separated string into a list of tool names."""
    raw = raw.strip()
    if raw.startswith("["):
        raw = raw.strip("[]")
    return [t.strip().lower() for t in re.split(r"[,\s]+", raw) if t.strip()]


def _build_opencode_frontmatter(copilot_fm: dict[str, str]) -> str:
    """Return the opencode YAML frontmatter block (without the ``---`` delimiters)."""
    lines: list[str] = []

    description = copilot_fm.get("description", "")
    if description:
        # Preserve quoting for multi-word descriptions.
        if '"' not in description:
            lines.append(f'description: "{description}"')
        else:
            description_escaped = description.replace('"', '\\"')
            lines.append(f'description: "{description_escaped}"')

    lines.append("mode: subagent")

    tools = _parse_tools(copilot_fm.get("tools", ""))
    deny: list[str] = []
    if not any(t in _WRITE_TOOLS for t in tools):
        deny.append("edit: deny")
    if not any(t in _BASH_TOOLS for t in tools):
        deny.append("bash: deny")
    if deny:
        lines.append("permissions:")
        for d in deny:
            lines.append(f"  {d}")

    return "\n".join(lines)


# ── Public API ─────────────────────────────────────────────────────────────────


def translate_agent(source: Path) -> str:
    """Translate a Copilot ``.agent.md`` file to opencode agent markdown.

    Returns the full opencode markdown string ready to be written to disk.
    """
    text = source.read_text()
    fm, body = parse_frontmatter(text)
    oc_fm = _build_opencode_frontmatter(fm)
    return f"---\n{oc_fm}\n---\n{body}"


def write_opencode_agents(dry_run: bool = False) -> list[str]:
    """Translate all installed ``.github/agents/*.agent.md`` to ``.opencode/agents/``.

    Returns a list of status lines (one per agent).  Agents already present in
    ``.opencode/agents/`` are overwritten so the translation stays in sync.
    """
    root = repo_root()
    src_dir = root / COPILOT_AGENTS_DIR
    if not src_dir.is_dir():
        return []

    lines: list[str] = []
    for src in sorted(src_dir.glob("*.agent.md")):
        name = src.stem.removesuffix(".agent")
        dest = root / OPENCODE_AGENTS_DIR / f"{name}.md"
        rel = dest.relative_to(root)
        if dry_run:
            lines.append(f"  [dry-run] {rel}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(translate_agent(src))
        lines.append(f"  wrote {rel}")
    return lines


def write_opencode_commands(dry_run: bool = False) -> list[str]:
    """Write starter opencode commands to ``.opencode/commands/``.

    Existing command files are left untouched so users can customise them freely.
    Returns a list of status lines.
    """
    root = repo_root()
    cmd_dir = root / OPENCODE_COMMANDS_DIR
    lines: list[str] = []
    for filename, content in _COMMANDS.items():
        dest = cmd_dir / filename
        rel = dest.relative_to(root)
        if dest.exists():
            lines.append(f"  exists  {rel}")
            continue
        if dry_run:
            lines.append(f"  [dry-run] {rel}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        lines.append(f"  wrote {rel}")
    return lines
