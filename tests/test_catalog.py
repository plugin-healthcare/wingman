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
