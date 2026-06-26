"""Library-skill sync: discover skills bundled in installed Python packages.

Scans the project's virtual environment for packages that ship agent skills
under ``.agents/skills/<name>/SKILL.md`` (the standard set by library-skills.io)
and copies them into ``.github/skills/`` so GitHub Copilot can use them.

Uses ``uv run python`` with ``importlib.metadata`` to query the project's own
environment — no manual dist-info or RECORD file parsing needed.

By default only packages listed as direct dependencies in ``pyproject.toml``
are considered. Pass ``all_packages=True`` to include transitive dependencies.

Tracks synced skills in ``.wingman/library-skills.json`` (separate from the
git-sourced manifest) so the command is idempotent and can report changes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from wingman.audit import parse_frontmatter
from wingman.core import repo_root
from wingman.skills import SKILLS_DIR

LIBRARY_SKILLS_LOCK = Path(".wingman") / "library-skills.json"

# Script run inside the project's uv environment via `uv run python -c`.
# Returns a JSON array of {name, version, skill_md} objects — one per
# SKILL.md found across all installed distributions.
_DISCOVER_SCRIPT = """
import importlib.metadata, json
from pathlib import Path

results = []
for dist in importlib.metadata.distributions():
    files = dist.files
    if not files:
        continue
    meta = dist.metadata
    pkg_name = meta["Name"] or ""
    pkg_version = meta["Version"] or ""
    for f in files:
        parts = f.parts
        for i, part in enumerate(parts):
            if (
                part == ".agents"
                and len(parts) > i + 3
                and parts[i + 1] == "skills"
                and parts[-1] == "SKILL.md"
            ):
                skill_md = dist.locate_file(f).resolve()
                results.append({
                    "package": pkg_name,
                    "version": pkg_version,
                    "skill_md": str(skill_md),
                })
                break

print(json.dumps(results))
"""


@dataclass
class LibrarySkill:
    name: str
    description: str
    package: str
    version: str
    source_dir: Path


# ── Direct-dependency filter ──────────────────────────────────────────────────


def normalize_package_name(name: str) -> str:
    """PEP 503 normalization: lowercase + collapse [-_.] to -."""
    return re.sub(r"[-_.]+", "-", name).lower()


def direct_deps(root: Path) -> set[str] | None:
    """Return normalized direct-dependency names from pyproject.toml.

    Returns None if no pyproject.toml is found, so callers can fall back to
    scanning all packages.
    """
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return None

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None

    deps: set[str] = set()
    project = cast("dict", data.get("project", {}))

    for spec in project.get("dependencies", []):
        if isinstance(spec, str):
            pkg = re.split(r"[~>=<!\[;,\s]", spec)[0].strip()
            if pkg:
                deps.add(normalize_package_name(pkg))

    for group in cast("dict", project.get("optional-dependencies", {})).values():
        for spec in group:
            if isinstance(spec, str):
                pkg = re.split(r"[~>=<!\[;,\s]", spec)[0].strip()
                if pkg:
                    deps.add(normalize_package_name(pkg))

    # PEP 735 dependency-groups (dev, test, …)
    for group in cast("dict", data.get("dependency-groups", {})).values():
        for spec in group:
            if isinstance(spec, str):
                pkg = re.split(r"[~>=<!\[;,\s]", spec)[0].strip()
                if pkg:
                    deps.add(normalize_package_name(pkg))

    return deps


# ── Discovery via uv ──────────────────────────────────────────────────────────


def _discover(root: Path) -> tuple[list[dict], str | None]:
    """Run the discovery script inside the project's uv env.

    Returns (raw_results, warning_or_None).
    """
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-c", _DISCOVER_SCRIPT],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return [], "uv not found — install uv or activate a virtualenv first"
    except subprocess.TimeoutExpired:
        return [], "uv run timed out"

    if result.returncode != 0:
        msg = result.stderr.strip() or "uv run failed"
        return [], msg

    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return [], "unexpected output from discovery script"


# ── SKILL.md parsing ──────────────────────────────────────────────────────────


def _parse_skill(skill_md: Path) -> LibrarySkill | None:
    """Parse SKILL.md frontmatter; return a LibrarySkill or None if invalid."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None
    fm, _ = parse_frontmatter(text)
    name = fm.get("name", "").strip()
    description = fm.get("description", "").strip()
    if not name:
        return None
    return LibrarySkill(
        name=name,
        description=description,
        package="",
        version="",
        source_dir=skill_md.parent,
    )


# ── Lock file ─────────────────────────────────────────────────────────────────


def _lock_path() -> Path:
    return repo_root() / LIBRARY_SKILLS_LOCK


def read_lock() -> dict[str, dict]:
    path = _lock_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_lock(lock: dict[str, dict]) -> None:
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


# ── Install / remove ──────────────────────────────────────────────────────────


def _dest(skill_name: str) -> Path:
    return repo_root() / SKILLS_DIR / skill_name


def _install_skill(skill: LibrarySkill) -> None:
    dest = _dest(skill.name)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill.source_dir, dest)


def _remove_skill(skill_name: str) -> None:
    dest = _dest(skill_name)
    if dest.exists():
        shutil.rmtree(dest)


# ── Public sync entry point ───────────────────────────────────────────────────


@dataclass
class SyncResult:
    added: list[str]
    updated: list[str]
    removed: list[str]
    unchanged: list[str]
    warnings: list[str]


def sync(root: Path | None = None, all_packages: bool = False) -> SyncResult:
    """Scan the project's uv env and sync library skills into .github/skills/.

    By default only direct dependencies from pyproject.toml are considered.
    Set ``all_packages=True`` to include transitive dependencies as well.

    Returns a SyncResult describing what changed.
    """
    root = root or repo_root()
    result = SyncResult(added=[], updated=[], removed=[], unchanged=[], warnings=[])

    raw, warning = _discover(root)
    if warning:
        result.warnings.append(warning)
        return result

    # Optionally restrict to direct deps from pyproject.toml.
    allowed: set[str] | None = None
    if not all_packages:
        allowed = direct_deps(root)
        if allowed is None:
            result.warnings.append(
                "No pyproject.toml found — scanning all installed packages. "
                "Use --all to silence this warning."
            )

    # Build a map of skill_name -> LibrarySkill from the discovered SKILL.md paths.
    found: dict[str, LibrarySkill] = {}
    for entry in raw:
        if allowed is not None and normalize_package_name(entry["package"]) not in (
            allowed
        ):
            continue
        skill_md = Path(entry["skill_md"])
        skill = _parse_skill(skill_md)
        if skill is None:
            result.warnings.append(f"Skipping invalid SKILL.md: {skill_md}")
            continue
        skill.package = entry["package"]
        skill.version = entry["version"]
        found[skill.name] = skill

    lock = read_lock()

    # Remove skills whose library was uninstalled (or filtered out).
    for name in list(lock):
        if name not in found:
            _remove_skill(name)
            del lock[name]
            result.removed.append(name)

    # Add or update.
    for name, skill in found.items():
        existing = lock.get(name)
        if existing is None:
            _install_skill(skill)
            lock[name] = {"package": skill.package, "version": skill.version}
            result.added.append(name)
        elif existing.get("version") != skill.version:
            _install_skill(skill)
            lock[name] = {"package": skill.package, "version": skill.version}
            result.updated.append(name)
        else:
            result.unchanged.append(name)

    write_lock(lock)
    return result
