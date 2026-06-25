"""Shared pytest fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    """A temporary repo set as the current working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def skill_source(tmp_path) -> tuple[str, str]:
    """A local git repo holding a valid skill at subpath 'demo'. Returns (url, ref)."""
    src = tmp_path / "src-repo"
    skill = src / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        'description: "Demo skill. Use when testing wingman skill fetching."\n'
        "---\n\n"
        "# Demo\n\nEnough body content for the skill to be considered usable.\n"
    )
    (skill / "references").mkdir()
    (skill / "references" / "note.md").write_text("reference material\n")

    _git(["init"], src)
    _git(["config", "user.email", "t@example.com"], src)
    _git(["config", "user.name", "test"], src)
    _git(["add", "-A"], src)
    _git(["commit", "-m", "init"], src)
    return src.as_uri(), "master"


@pytest.fixture
def skill_set_source(tmp_path) -> tuple[str, str]:
    """A local git repo with several skills under 'skills/'. Returns (url, ref)."""
    src = tmp_path / "set-repo"
    for member in ("alpha", "beta", "gamma"):
        skill = src / "skills" / member
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {member}\n"
            f'description: "The {member} skill. Use when testing sets."\n'
            f"---\n\n# {member}\n\nEnough body content to be a usable skill here.\n"
        )

    _git(["init"], src)
    _git(["config", "user.email", "t@example.com"], src)
    _git(["config", "user.name", "test"], src)
    _git(["add", "-A"], src)
    _git(["commit", "-m", "init"], src)
    return src.as_uri(), "master"
