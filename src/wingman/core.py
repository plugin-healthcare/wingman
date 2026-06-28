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
# Root .mcp.json (the editor-agnostic location the Copilot CLI reads). Uses the
# `mcpServers` schema key. Not VS Code's `.vscode/mcp.json`.
MCP_CONFIG = Path(".mcp.json")

# opencode outputs (relative to the repo being set up)
OPENCODE_AGENTS_MD = Path("AGENTS.md")
OPENCODE_CONFIG = Path("opencode.json")


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
    """Read an MCP server map, accepting both the CLI and VS Code schema keys."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return raw.get("mcpServers") or raw.get("servers") or {}


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
    content = json.dumps({"mcpServers": merged_servers(stack)}, indent=2) + "\n"
    return _write(MCP_CONFIG, content, dry_run)


# ── opencode writers ──────────────────────────────────────────────────────────


def assemble_opencode_config(stack: str | None) -> dict:
    """Build the opencode.json content dict.

    Merges MCP servers (under ``mcp.servers``) and lists both instruction files
    so opencode picks up the same context as GitHub Copilot.
    """
    servers = merged_servers(stack)
    return {
        "$schema": "https://opencode.ai/config.json",
        "instructions": [
            str(OPENCODE_AGENTS_MD),
            str(COPILOT_INSTRUCTIONS),
        ],
        "mcp": {"servers": servers} if servers else {},
    }


def write_agents_md(stack: str | None, dry_run: bool) -> str:
    """Write AGENTS.md with the same assembled content as copilot-instructions.md."""
    return _write(OPENCODE_AGENTS_MD, assemble_instructions(stack), dry_run)


def write_opencode_config(stack: str | None, dry_run: bool) -> str:
    """Write opencode.json with MCP servers and instruction file references."""
    content = json.dumps(assemble_opencode_config(stack), indent=2) + "\n"
    return _write(OPENCODE_CONFIG, content, dry_run)


def read_mcp_servers() -> dict:
    """Current servers in the repo's .mcp.json (base + local if absent)."""
    path = repo_root() / MCP_CONFIG
    if not path.exists():
        return dict(merged_servers(None))
    return _load_servers(path)


def add_mcp_server(name: str, config: dict, dry_run: bool = False) -> str:
    """Merge one MCP server into .mcp.json, keeping existing servers."""
    if dry_run:
        return f"  [dry-run] mcp {name}"
    servers = read_mcp_servers()
    servers[name] = config
    content = json.dumps({"mcpServers": servers}, indent=2) + "\n"
    return _write(MCP_CONFIG, content, dry_run)
