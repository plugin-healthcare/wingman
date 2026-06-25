"""Audit Copilot guardrail artifacts (skills, agents, instructions) for best practices.

This is the deterministic linter behind ``wingman audit``. It checks the things
that make a skill or instruction file effective for an agent: a clear name, a
description that says *when* to use it, frontmatter completeness, and a body that
isn't bloated. For deeper, subjective review, use the bundled ``skill-reviewer``
agent (``.github/agents/skill-reviewer.agent.md``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from wingman.core import repo_root

ERROR = "error"
WARNING = "warning"
INFO = "info"

_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_BLOCK_SCALAR = re.compile(r"^[|>][+-]?\d*$")
# Phrases that signal a description explains *when* to trigger the skill.
_TRIGGER_HINTS = (
    "use when",
    "use for",
    "use this",
    "use before",
    "use to",
    "gebruik bij",
    "gebruik voor",
    "when ",
)
# Action verbs that signal an imperative description (says what the skill does,
# which implicitly tells the agent when to reach for it). Matched on the first
# word, so "Run SQL queries…" or "Convert between formats…" count as a trigger.
_IMPERATIVE_VERBS = frozenset(
    {
        "run",
        "read",
        "write",
        "create",
        "edit",
        "build",
        "install",
        "convert",
        "attach",
        "explore",
        "query",
        "look",
        "find",
        "fetch",
        "generate",
        "review",
        "refactor",
        "debug",
        "test",
        "analyze",
        "analyse",
        "validate",
        "check",
        "search",
        "load",
        "export",
        "import",
        "deploy",
        "scaffold",
        "set",
        "configure",
        "manage",
        "add",
        "remove",
        "update",
        "render",
        "parse",
        "format",
        "compute",
        "calculate",
        "preview",
        "inspect",
        "list",
        "show",
        "get",
        "lint",
    }
)


@dataclass
class Finding:
    path: Path
    level: str
    message: str


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(repo_root()))
    except ValueError:
        return str(path)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split a markdown file into (frontmatter scalars, body).

    Simple top-level ``key: value`` scalars are parsed, plus YAML block scalars
    (``key: >`` folded and ``key: |`` literal), which official skills use for
    multi-line descriptions. That covers the frontmatter wingman cares about
    (name, description, …). Returns an empty dict if there is no ``---``
    delimited frontmatter block.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text
    fm: dict[str, str] = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if _BLOCK_SCALAR.match(value):
            folded = value[0] == ">"
            i += 1
            block: list[str] = []
            while i < end:
                cont = lines[i]
                if cont.strip() and not cont[:1].isspace():
                    break  # next top-level key ends the block
                block.append(cont.strip())
                i += 1
            while block and not block[0]:
                block.pop(0)
            while block and not block[-1]:
                block.pop()
            fm[key] = (" " if folded else "\n").join(block)
            continue
        if value == "" and i + 1 < end and lines[i + 1][:1].isspace():
            # Empty value followed by indented lines: an implicit plain
            # multiline scalar (folded) or a nested list/mapping we skip.
            i += 1
            block = []
            is_list = False
            while i < end:
                cont = lines[i]
                if cont.strip() and not cont[:1].isspace():
                    break  # next top-level key ends the block
                stripped = cont.strip()
                if stripped.startswith("- ") or stripped.startswith("-"):
                    is_list = True
                block.append(stripped)
                i += 1
            while block and not block[0]:
                block.pop(0)
            while block and not block[-1]:
                block.pop()
            fm[key] = "" if is_list else " ".join(block)
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        fm[key] = value
        i += 1
    body = "\n".join(lines[end + 1 :]).strip()
    return fm, body


def _has_trigger(description: str) -> bool:
    low = description.lower()
    if any(hint in low for hint in _TRIGGER_HINTS):
        return True
    first = re.sub(r"[^a-z]", "", low.split()[0]) if low.split() else ""
    return first in _IMPERATIVE_VERBS


# ── Rules per artifact type ───────────────────────────────────────────────────


def audit_skill(path: Path) -> list[Finding]:
    out: list[Finding] = []
    text = path.read_text()
    fm, body = parse_frontmatter(text)

    if not fm:
        out.append(Finding(path, ERROR, "missing YAML frontmatter (--- … ---)"))
        return out

    name = fm.get("name")
    if not name:
        out.append(Finding(path, ERROR, "frontmatter missing 'name'"))
    else:
        folder = path.parent.name
        if name != folder:
            out.append(Finding(path, ERROR, f"name '{name}' != folder '{folder}'"))
        if not _KEBAB.match(name):
            out.append(Finding(path, WARNING, f"name '{name}' is not kebab-case"))

    desc = fm.get("description", "")
    if not desc:
        out.append(Finding(path, ERROR, "frontmatter missing 'description'"))
    else:
        if len(desc) < 40:
            out.append(
                Finding(
                    path,
                    WARNING,
                    "description is very short; say what it does and when to use it",
                )
            )
        if len(desc) > 1024:
            out.append(
                Finding(path, WARNING, "description is over 1024 chars; tighten it")
            )
        if not _has_trigger(desc):
            out.append(
                Finding(
                    path,
                    WARNING,
                    "description should say *when* to use it (e.g. 'Use when …')",
                )
            )

    if len(body) < 80:
        out.append(
            Finding(
                path, WARNING, "body is nearly empty; a skill needs usable instructions"
            )
        )

    line_count = text.count("\n") + 1
    if line_count > 500:
        out.append(
            Finding(
                path,
                WARNING,
                f"SKILL.md is {line_count} lines; move detail into references/",
            )
        )
    return out


def audit_agent(path: Path) -> list[Finding]:
    out: list[Finding] = []
    fm, body = parse_frontmatter(path.read_text())
    if not fm:
        out.append(Finding(path, ERROR, "missing YAML frontmatter (--- … ---)"))
        return out
    desc = fm.get("description", "")
    if not desc:
        out.append(Finding(path, ERROR, "frontmatter missing 'description'"))
    elif not _has_trigger(desc):
        out.append(
            Finding(
                path, INFO, "description could name trigger phrases for auto-selection"
            )
        )
    if "tools" not in fm:
        out.append(
            Finding(path, INFO, "no 'tools' listed; agent gets the default tool set")
        )
    if len(body) < 80:
        out.append(Finding(path, WARNING, "agent body is nearly empty"))
    return out


def audit_instructions(path: Path) -> list[Finding]:
    out: list[Finding] = []
    text = path.read_text().strip()
    if not text:
        out.append(Finding(path, ERROR, "instructions file is empty"))
        return out
    line_count = text.count("\n") + 1
    if line_count > 400:
        out.append(
            Finding(
                path,
                WARNING,
                f"{line_count} lines; long instructions dilute attention",
            )
        )
    if "#" not in text:
        out.append(
            Finding(path, INFO, "no headings; structure helps the agent navigate")
        )
    return out


# ── Discovery + orchestration ─────────────────────────────────────────────────


def discover(root: Path | None = None) -> list[tuple[Path, str]]:
    """Find auditable artifacts under a repo. Returns (path, kind) pairs."""
    base = root or repo_root()
    found: list[tuple[Path, str]] = []
    skills = base / ".github" / "skills"
    if skills.is_dir():
        found += [(p, "skill") for p in sorted(skills.glob("*/SKILL.md"))]
    agents = base / ".github" / "agents"
    if agents.is_dir():
        found += [(p, "agent") for p in sorted(agents.glob("*.agent.md"))]
    ci = base / ".github" / "copilot-instructions.md"
    if ci.is_file():
        found.append((ci, "instructions"))
    scoped = base / ".github" / "instructions"
    if scoped.is_dir():
        found += [(p, "instructions") for p in sorted(scoped.glob("*.instructions.md"))]
    return found


_AUDITORS = {
    "skill": audit_skill,
    "agent": audit_agent,
    "instructions": audit_instructions,
}


def audit_path(path: Path, kind: str | None = None) -> list[Finding]:
    if kind is None:
        if path.name == "SKILL.md":
            kind = "skill"
        elif path.name.endswith(".agent.md"):
            kind = "agent"
        else:
            kind = "instructions"
    return _AUDITORS[kind](path)


def audit_all(root: Path | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for path, kind in discover(root):
        findings += audit_path(path, kind)
    return findings


def format_findings(findings: list[Finding]) -> list[str]:
    return [f"  [{f.level}] {_rel(f.path)}: {f.message}" for f in findings]
