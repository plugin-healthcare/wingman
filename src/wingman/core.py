"""Core logic: assemble Copilot guardrails + MCP config from packaged defaults.

Wingman is installed per-repo. Every command operates on the current working
directory (the project being set up). Default instructions and MCP servers ship
as package data under ``wingman/data`` and can be extended per-repo via optional
``.wingman/`` override files.
"""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

# Outputs (relative to the repo being set up)
COPILOT_INSTRUCTIONS = Path(".github") / "copilot-instructions.md"
VSCODE_MCP = Path(".vscode") / "mcp.json"


def data_path() -> Path:
    """On-disk path to bundled package data (``wingman/data``)."""
    return Path(str(resources.files("wingman").joinpath("data")))


def repo_root() -> Path:
    """The project wingman is operating on (current working directory)."""
    return Path.cwd()


def available_stacks() -> list[str]:
    """Stacks that have instructions and/or MCP defaults bundled."""
    data = data_path()
    names: set[str] = set()
    for sub in ("instructions", "mcp"):
        folder = data / sub
        if folder.is_dir():
            for f in folder.iterdir():
                if f.name.startswith("base."):
                    continue
                names.add(f.stem)
    return sorted(names)


# ── MCP ───────────────────────────────────────────────────────────────────────


def _load_servers(path: Path) -> dict:
    """Read an MCP server map, accepting both VS Code and legacy schemas."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return raw.get("servers") or raw.get("mcpServers") or {}


def merged_servers(stack: str | None) -> dict:
    """Merge base + optional stack + optional repo-local MCP servers."""
    data = data_path()
    servers = _load_servers(data / "mcp" / "base.json")
    if stack:
        servers |= _load_servers(data / "mcp" / f"{stack}.json")
    servers |= _load_servers(repo_root() / ".wingman" / "mcp.local.json")
    return servers


# ── Instructions ──────────────────────────────────────────────────────────────


def assemble_instructions(stack: str | None) -> str:
    """Merge base + optional stack + optional repo-local instructions."""
    data = data_path()
    parts = [(data / "instructions" / "base.md").read_text()]
    if stack:
        stack_file = data / "instructions" / f"{stack}.md"
        if stack_file.exists():
            parts.append(stack_file.read_text())
    local = repo_root() / ".wingman" / "instructions.local.md"
    if local.exists():
        parts.append(local.read_text())
    return "\n\n---\n\n".join(p.rstrip() for p in parts) + "\n"


# ── Writers (GitHub Copilot only) ─────────────────────────────────────────────


def _write(rel: Path, text: str, dry_run: bool) -> str:
    path = repo_root() / rel
    if dry_run:
        return f"  [dry-run] {rel}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return f"  wrote {rel}"


def write_instructions(stack: str | None, dry_run: bool) -> str:
    return _write(COPILOT_INSTRUCTIONS, assemble_instructions(stack), dry_run)


def write_mcp(stack: str | None, dry_run: bool) -> str:
    content = json.dumps({"servers": merged_servers(stack)}, indent=2) + "\n"
    return _write(VSCODE_MCP, content, dry_run)
