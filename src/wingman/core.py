"""Core logic: merge configs and write tool-specific outputs."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

TOOL_TARGETS = ["vscode", "cursor", "goose", "opencode"]


# ── MCP config helpers ────────────────────────────────────────────────────────


def load_mcp(path: Path) -> dict:
    return json.loads(path.read_text()).get("mcpServers", {})


def merged_servers(stack: str | None) -> dict:
    """Merge base + optional stack MCP servers."""
    servers = load_mcp(REPO_ROOT / "mcp" / "base.json")
    if stack:
        stack_mcp = REPO_ROOT / "mcp" / f"{stack}.json"
        if stack_mcp.exists():
            servers |= load_mcp(stack_mcp)
    return servers


# ── AGENTS.md assembly ────────────────────────────────────────────────────────


def assemble_agents(stack: str | None) -> str:
    parts = [(REPO_ROOT / "instructions" / "base.md").read_text()]
    if stack:
        stack_instructions = REPO_ROOT / "instructions" / f"{stack}.md"
        if stack_instructions.exists():
            parts.append(stack_instructions.read_text())
    return "\n\n---\n\n".join(parts)


# ── Tool writers ──────────────────────────────────────────────────────────────


def _write(path: Path, text: str, dry_run: bool) -> str:
    rel = path.relative_to(REPO_ROOT)
    if dry_run:
        return f"  [dry-run] {rel}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return f"  wrote {rel}"


def write_vscode(servers: dict, dry_run: bool) -> str:
    content = json.dumps({"mcpServers": servers}, indent=2) + "\n"
    return _write(REPO_ROOT / ".vscode" / "mcp.json", content, dry_run)


def write_cursor(servers: dict, dry_run: bool) -> str:
    content = json.dumps({"mcpServers": servers}, indent=2) + "\n"
    return _write(REPO_ROOT / ".cursor" / "mcp.json", content, dry_run)


def write_goose(servers: dict, dry_run: bool) -> str:
    lines = ["extensions:"]
    for name, cfg in servers.items():
        args = cfg.get("args", [])
        args_yaml = ", ".join(f'"{a}"' for a in args)
        lines += [
            f"  {name}:",
            "    type: stdio",
            f"    cmd: {cfg['command']}",
            f"    args: [{args_yaml}]",
            "    enabled: true",
        ]
    return _write(
        REPO_ROOT / ".goose" / "config.yaml", "\n".join(lines) + "\n", dry_run
    )


def write_opencode(servers: dict, dry_run: bool) -> str:
    path = REPO_ROOT / "opencode.json"
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    mcp = {
        name: {
            "type": "local",
            "command": [cfg["command"]] + cfg.get("args", []),
            "enabled": True,
            **({"environment": cfg["env"]} if "env" in cfg else {}),
        }
        for name, cfg in servers.items()
    }
    merged = {"$schema": "https://opencode.ai/config.json", **existing, "mcp": mcp}
    return _write(path, json.dumps(merged, indent=2) + "\n", dry_run)


WRITERS = {
    "vscode": write_vscode,
    "cursor": write_cursor,
    "goose": write_goose,
    "opencode": write_opencode,
}


def sync_tools(servers: dict, tools: list[str], dry_run: bool) -> list[str]:
    return [WRITERS[t](servers, dry_run) for t in tools]
