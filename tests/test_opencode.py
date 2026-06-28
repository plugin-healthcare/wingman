"""Tests for opencode support: core writers, agent translation, command generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wingman import core, opencode, skills

# ── core writers ──────────────────────────────────────────────────────────────


def test_write_agents_md(repo):
    core.write_agents_md("python", dry_run=False)
    path = repo / core.OPENCODE_AGENTS_MD
    assert path.is_file()
    text = path.read_text()
    assert "Python" in text or "Core" in text


def test_write_opencode_config(repo):
    core.write_opencode_config("python", dry_run=False)
    path = repo / core.OPENCODE_CONFIG
    assert path.is_file()
    data = json.loads(path.read_text())
    assert "instructions" in data
    assert str(core.OPENCODE_AGENTS_MD) in data["instructions"]
    assert str(core.COPILOT_INSTRUCTIONS) in data["instructions"]
    assert "mcp" in data


def test_write_opencode_config_dry_run(repo):
    line = core.write_opencode_config("python", dry_run=True)
    assert "[dry-run]" in line
    assert not (repo / core.OPENCODE_CONFIG).exists()


def test_assemble_opencode_config_has_schema(repo):
    cfg = core.assemble_opencode_config(None)
    assert cfg["$schema"] == "https://opencode.ai/config.json"


# ── agent translation ─────────────────────────────────────────────────────────


def _make_agent(tmp_path: Path, name: str, tools: str = "read, search") -> Path:
    src = tmp_path / f"{name}.agent.md"
    src.write_text(
        f"---\n"
        f'description: "The {name} agent."\n'
        f"tools: [{tools}]\n"
        f"user-invocable: true\n"
        f"---\n\n"
        f"Body of {name}.\n"
    )
    return src


def test_translate_agent_strips_copilot_frontmatter(tmp_path):
    src = _make_agent(tmp_path, "yoda")
    result = opencode.translate_agent(src)
    assert "user-invocable" not in result
    assert "tools:" not in result


def test_translate_agent_sets_mode_subagent(tmp_path):
    src = _make_agent(tmp_path, "yoda")
    result = opencode.translate_agent(src)
    assert "mode: subagent" in result


def test_translate_agent_denies_edit_and_bash_for_read_only(tmp_path):
    src = _make_agent(tmp_path, "yoda", tools="read, search")
    result = opencode.translate_agent(src)
    assert "edit: deny" in result
    assert "bash: deny" in result


def test_translate_agent_allows_edit_when_write_tool_present(tmp_path):
    src = _make_agent(tmp_path, "builder", tools="read, write, search")
    result = opencode.translate_agent(src)
    assert "edit: deny" not in result


def test_translate_agent_allows_bash_when_bash_tool_present(tmp_path):
    src = _make_agent(tmp_path, "runner", tools="read, bash")
    result = opencode.translate_agent(src)
    assert "bash: deny" not in result


def test_translate_agent_preserves_description(tmp_path):
    src = _make_agent(tmp_path, "yoda")
    result = opencode.translate_agent(src)
    assert "The yoda agent." in result


def test_translate_agent_preserves_body(tmp_path):
    src = _make_agent(tmp_path, "yoda")
    result = opencode.translate_agent(src)
    assert "Body of yoda." in result


# ── write_opencode_agents ─────────────────────────────────────────────────────


def test_write_opencode_agents_no_agents_returns_empty(repo):
    lines = opencode.write_opencode_agents()
    assert lines == []


def test_write_opencode_agents_translates_installed_agents(repo):
    agents_dir = repo / ".github" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "yoda.agent.md").write_text(
        "---\n"
        'description: "Mentor."\n'
        "tools: [read, search]\n"
        "user-invocable: true\n"
        "---\n\n"
        "Yoda body.\n"
    )
    lines = opencode.write_opencode_agents()
    assert len(lines) == 1
    dest = repo / ".opencode" / "agents" / "yoda.md"
    assert dest.is_file()
    content = dest.read_text()
    assert "mode: subagent" in content
    assert "Yoda body." in content


def test_write_opencode_agents_dry_run(repo):
    agents_dir = repo / ".github" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "yoda.agent.md").write_text(
        "---\n"
        'description: "Mentor."\n'
        "tools: [read]\n"
        "user-invocable: true\n"
        "---\n\n"
        "body\n"
    )
    lines = opencode.write_opencode_agents(dry_run=True)
    assert "[dry-run]" in lines[0]
    assert not (repo / ".opencode" / "agents" / "yoda.md").exists()


# ── write_opencode_commands ───────────────────────────────────────────────────


def test_write_opencode_commands_creates_files(repo):
    lines = opencode.write_opencode_commands()
    assert any("check.md" in line for line in lines)
    assert any("review.md" in line for line in lines)
    assert (repo / ".opencode" / "commands" / "check.md").is_file()
    assert (repo / ".opencode" / "commands" / "review.md").is_file()


def test_write_opencode_commands_skips_existing(repo):
    cmd_dir = repo / ".opencode" / "commands"
    cmd_dir.mkdir(parents=True)
    (cmd_dir / "check.md").write_text("custom content\n")
    opencode.write_opencode_commands()
    assert (cmd_dir / "check.md").read_text() == "custom content\n"


def test_write_opencode_commands_dry_run(repo):
    lines = opencode.write_opencode_commands(dry_run=True)
    assert all("[dry-run]" in line for line in lines)
    assert not (repo / ".opencode" / "commands" / "check.md").exists()


# ── dual-target skill install ─────────────────────────────────────────────────


def test_skill_add_installs_to_both_dirs(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref, agent="all")
    assert (repo / skills.COPILOT_SKILLS_DIR / "demo" / "SKILL.md").is_file()
    assert (repo / skills.OPENCODE_SKILLS_DIR / "demo" / "SKILL.md").is_file()


def test_skill_add_copilot_only(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref, agent="copilot")
    assert (repo / skills.COPILOT_SKILLS_DIR / "demo" / "SKILL.md").is_file()
    assert not (repo / skills.OPENCODE_SKILLS_DIR / "demo").exists()


def test_skill_add_opencode_only(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref, agent="opencode")
    assert not (repo / skills.COPILOT_SKILLS_DIR / "demo").exists()
    assert (repo / skills.OPENCODE_SKILLS_DIR / "demo" / "SKILL.md").is_file()


def test_skill_remove_all_cleans_both_dirs(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref, agent="all")
    skills.remove("demo", agent="all")
    assert not (repo / skills.COPILOT_SKILLS_DIR / "demo").exists()
    assert not (repo / skills.OPENCODE_SKILLS_DIR / "demo").exists()
    assert "demo" not in skills.read_manifest()


def test_skill_remove_copilot_only_preserves_opencode(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref, agent="all")
    skills.remove("demo", agent="copilot")
    assert not (repo / skills.COPILOT_SKILLS_DIR / "demo").exists()
    assert (repo / skills.OPENCODE_SKILLS_DIR / "demo" / "SKILL.md").is_file()
    # Manifest kept because only one target removed
    assert "demo" in skills.read_manifest()


def test_list_skills_reports_both_targets(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref, agent="all")
    rows = skills.list_skills()
    assert rows[0]["installed"] is True
    assert rows[0]["opencode_installed"] is True


@pytest.mark.parametrize("agent", ["copilot", "opencode"])
def test_list_skills_partial_install(repo, skill_source, agent):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref, agent=agent)
    rows = skills.list_skills()
    assert rows[0]["installed"] is (agent == "copilot")
    assert rows[0]["opencode_installed"] is (agent == "opencode")
