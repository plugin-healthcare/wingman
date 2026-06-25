"""The check gate: run a project's lint/format/test commands in order.

Wingman is Python + uv focused, so the bundled default gate runs ``uv run ruff``
and ``uv run pytest``. Override per-repo with ``.wingman/checks.toml``.
"""

from __future__ import annotations

import shlex
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from wingman.core import data_path, repo_root

LOCAL_CHECKS = Path(".wingman") / "checks.toml"
DEFAULT_STACK = "python"


@dataclass
class Check:
    name: str
    cmd: str


@dataclass
class CheckResult:
    name: str
    cmd: str
    returncode: int

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def _parse(text: str) -> list[Check]:
    raw = tomllib.loads(text).get("check", [])
    return [Check(name=c["name"], cmd=c["cmd"]) for c in raw]


def load_checks(stack: str | None) -> list[Check]:
    """Repo-local ``.wingman/checks.toml`` wins; else bundled stack defaults."""
    local = repo_root() / LOCAL_CHECKS
    if local.exists():
        return _parse(local.read_text())
    bundled = data_path() / "checks" / f"{stack or DEFAULT_STACK}.toml"
    if not bundled.exists():
        raise FileNotFoundError(
            f"no checks defined for stack '{stack or DEFAULT_STACK}' "
            f"(create {LOCAL_CHECKS} to define your own)"
        )
    return _parse(bundled.read_text())


def run_checks(stack: str | None, fail_fast: bool = True) -> list[CheckResult]:
    """Run each check in CWD, streaming output. Stop on first failure if fail_fast."""
    results: list[CheckResult] = []
    for check in load_checks(stack):
        proc = subprocess.run(shlex.split(check.cmd), cwd=repo_root())
        results.append(CheckResult(check.name, check.cmd, proc.returncode))
        if fail_fast and proc.returncode != 0:
            break
    return results
