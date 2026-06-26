"""Tests for the catalog and the `agent` command group helpers."""

from __future__ import annotations

from wingman import catalog


def test_catalog_lists_bundled_agents(repo):
    names = [it.name for it in catalog.catalog(["agents"])["agents"]]
    assert "yoda.agent.md" in names
    assert "marvin.agent.md" in names


def test_find_agent_by_short_name(repo):
    item = catalog.find_agent("yoda")
    assert item is not None
    assert item.name == "yoda.agent.md"
    assert item.kind == "agent"


def test_find_agent_by_filename(repo):
    item = catalog.find_agent("yoda.agent.md")
    assert item is not None
    assert item.name == "yoda.agent.md"


def test_find_agent_unknown_returns_none(repo):
    assert catalog.find_agent("does-not-exist") is None


def test_install_agent_copies_into_repo(repo):
    item = catalog.find_agent("yoda")
    catalog.install_item(item)
    installed = repo / ".github" / "agents" / "yoda.agent.md"
    assert installed.is_file()
    assert "Yoda" in installed.read_text()


def test_catalog_lists_mcp_servers(repo):
    items = catalog.catalog(["mcp"])["mcp"]
    names = [it.name for it in items]
    assert "github" in names
    assert "likec4" in names
    # github is a sensible default and should be pre-checked
    assert next(it for it in items if it.name == "github").checked is True
    assert next(it for it in items if it.name == "likec4").checked is False


def test_install_mcp_merges_into_vscode_config(repo):
    import json

    from wingman import core

    core.write_mcp("python", dry_run=False)  # seed an empty servers map
    item = next(it for it in catalog.catalog(["mcp"])["mcp"] if it.name == "likec4")
    catalog.install_item(item)

    data = json.loads((repo / core.MCP_CONFIG).read_text())
    assert "likec4" in data["mcpServers"]
    assert data["mcpServers"]["likec4"]["command"] == "npx"
    assert data["mcpServers"]["likec4"]["args"] == ["-y", "@likec4/mcp"]
    # No VS Code-only ${workspaceFolder}: LikeC4 defaults to the launch cwd.
    assert "env" not in data["mcpServers"]["likec4"]


def test_install_third_party_mcp_warns(repo):
    from wingman import core

    core.write_mcp("python", dry_run=False)
    item = next(it for it in catalog.catalog(["mcp"])["mcp"] if it.name == "polars")
    status = catalog.install_item(item)
    # Opt-in remote server: the user must be warned the payload goes off-machine.
    assert "\u26a0" in status
    assert "third party" in status


def test_install_default_mcp_does_not_warn(repo):
    from wingman import core

    core.write_mcp("python", dry_run=False)
    # github is remote but Copilot-hosted and a curated default: no warning.
    item = next(it for it in catalog.catalog(["mcp"])["mcp"] if it.name == "github")
    assert "\u26a0" not in catalog.install_item(item)
    # git is a local default: no warning either.
    item = next(it for it in catalog.catalog(["mcp"])["mcp"] if it.name == "git")
    assert "\u26a0" not in catalog.install_item(item)
