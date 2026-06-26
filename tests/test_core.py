"""Tests for core assembly and Copilot output writers."""

from __future__ import annotations

import json

from wingman import core


def test_assemble_instructions_merges_base_and_stack(repo):
    text = core.assemble_instructions("python")
    assert "Core" in text or "Workflow" in text
    assert "Python" in text


def test_assemble_instructions_appends_local_override(repo):
    local = repo / ".wingman"
    local.mkdir()
    (local / "instructions.local.md").write_text("# Local Rule\nbe nice\n")
    text = core.assemble_instructions(None)
    assert "Local Rule" in text


def test_write_instructions_and_mcp(repo):
    core.write_instructions("python", dry_run=False)
    core.write_mcp("python", dry_run=False)

    ci = repo / core.COPILOT_INSTRUCTIONS
    mcp = repo / core.MCP_CONFIG
    assert ci.is_file()
    data = json.loads(mcp.read_text())
    # Root .mcp.json uses the top-level "mcpServers" key (Copilot CLI schema).
    assert "mcpServers" in data


def test_write_dry_run_writes_nothing(repo):
    line = core.write_instructions("python", dry_run=True)
    assert "[dry-run]" in line
    assert not (repo / core.COPILOT_INSTRUCTIONS).exists()


def test_local_mcp_override_merges(repo):
    local = repo / ".wingman"
    local.mkdir()
    (local / "mcp.local.json").write_text(
        json.dumps({"mcpServers": {"extra": {"command": "echo"}}})
    )
    servers = core.merged_servers(None)
    assert "extra" in servers


def test_available_stacks_includes_python(repo):
    assert "python" in core.available_stacks()
