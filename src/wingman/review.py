"""Deep, content-based review of artifacts by delegating to the Copilot CLI.

The deterministic :mod:`wingman.audit` covers mechanical checks. This module
hands the subjective, content-based review (is the description a good trigger?
are the instructions actionable and correct for this repo?) to the ``copilot``
CLI in non-interactive, read-only mode, using the bundled ``skill-reviewer``
rubric.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from wingman.core import data_path, repo_root


class ReviewUnavailable(RuntimeError):
    """Raised when the Copilot CLI needed for deep review is not available."""


def reviewer_rubric() -> str:
    from wingman.audit import parse_frontmatter

    agent = data_path() / "catalog" / "agents" / "skill-reviewer.agent.md"
    _, body = parse_frontmatter(agent.read_text())
    return body


def build_prompt(paths: list[Path]) -> str:
    file_list = "\n".join(f"- {p}" for p in paths)
    return (
        f"{reviewer_rubric()}\n\n"
        "Review ONLY the files listed below. Do not edit anything; this is a "
        "read-only review. Report findings per file.\n\n"
        f"Files:\n{file_list}\n"
    )


def deep_review(paths: list[Path]) -> int:
    """Run the Copilot CLI to review the given artifact paths. Returns its exit code."""
    if not shutil.which("copilot"):
        raise ReviewUnavailable(
            "the `copilot` CLI is not installed; install GitHub Copilot CLI "
            "(https://github.com/github/copilot-cli) to use --deep"
        )
    cmd = [
        "copilot",
        "-p",
        build_prompt(paths),
        "--allow-tool",
        "read",
        "--allow-tool",
        "search",
    ]
    return subprocess.run(cmd, cwd=repo_root()).returncode
