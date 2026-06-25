"""Tests for the check gate loader."""

from __future__ import annotations

import pytest

from wingman import check


def test_load_bundled_python_checks(repo):
    checks = check.load_checks("python")
    names = [c.name for c in checks]
    assert names == ["lint", "format", "test"]


def test_local_checks_override_bundled(repo):
    local = repo / ".wingman"
    local.mkdir()
    (local / "checks.toml").write_text('[[check]]\nname = "custom"\ncmd = "echo hi"\n')
    checks = check.load_checks("python")
    assert len(checks) == 1
    assert checks[0].name == "custom"


def test_unknown_stack_raises(repo):
    with pytest.raises(FileNotFoundError):
        check.load_checks("haskell")


def test_run_checks_stops_on_failure(repo):
    local = repo / ".wingman"
    local.mkdir()
    (local / "checks.toml").write_text(
        '[[check]]\nname = "fail"\ncmd = "false"\n'
        '[[check]]\nname = "after"\ncmd = "true"\n'
    )
    results = check.run_checks("python", fail_fast=True)
    assert len(results) == 1
    assert results[0].passed is False


def test_run_checks_all_pass(repo):
    local = repo / ".wingman"
    local.mkdir()
    (local / "checks.toml").write_text('[[check]]\nname = "ok"\ncmd = "true"\n')
    results = check.run_checks("python")
    assert results[0].passed is True
