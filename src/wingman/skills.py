"""Skill manager: fetch, install, and update Copilot skills.

A skill is a folder containing a ``SKILL.md`` (plus optional ``references/``,
``assets/`` …). Skills are fetched from a git source (repo + subpath + ref),
unpacked into ``.github/skills/<name>/``, and recorded in a manifest so they
can be listed and updated later.

Sources:
- a curated short name resolved from the bundled ``data/skills/index.toml``
- a direct git URL with ``--path`` pointing at the skill folder inside the repo
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from wingman.core import data_path, repo_root

SKILLS_DIR = Path(".github") / "skills"
MANIFEST = Path(".wingman") / "skills.toml"
LOCK = Path(".wingman") / "skills.lock"


class SkillError(RuntimeError):
    """Raised for recoverable skill-management failures."""


@dataclass
class SkillSource:
    name: str
    repo: str
    path: str
    ref: str | None = None
    packages: list[str] = field(default_factory=list)


@dataclass
class SkillSetMember:
    """One skill in a set, at an explicit subpath inside the repo."""

    name: str
    path: str


@dataclass
class SkillSet:
    """A named theme: a bundle of skills fetched from one git repo.

    Members are resolved either by globbing ``*/SKILL.md`` under ``path`` (with
    optional ``include``/``exclude``), or, when ``members`` is given, from the
    explicit subpaths listed there (for repos where skills live at unrelated
    locations).
    """

    name: str
    repo: str
    path: str = ""
    ref: str | None = None
    include: list[str] | None = None
    exclude: list[str] | None = None
    members: list[SkillSetMember] | None = None
    description: str = ""
    packages: list[str] = field(default_factory=list)


# ── Manifest + lock ───────────────────────────────────────────────────────────


def _manifest_path() -> Path:
    return repo_root() / MANIFEST


def _lock_path() -> Path:
    return repo_root() / LOCK


def read_manifest() -> dict[str, SkillSource]:
    path = _manifest_path()
    if not path.exists():
        return {}
    raw = tomllib.loads(path.read_text()).get("skills", {})
    return {
        name: SkillSource(
            name=name,
            repo=entry["repo"],
            path=entry["path"],
            ref=entry.get("ref"),
        )
        for name, entry in raw.items()
    }


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def write_manifest(skills: dict[str, SkillSource]) -> None:
    lines: list[str] = []
    for name in sorted(skills):
        s = skills[name]
        lines.append(f"[skills.{name}]")
        lines.append(f'repo = "{_esc(s.repo)}"')
        lines.append(f'path = "{_esc(s.path)}"')
        if s.ref:
            lines.append(f'ref = "{_esc(s.ref)}"')
        lines.append("")
    path = _manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n" if lines else "")


def read_lock() -> dict[str, dict]:
    path = _lock_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def write_lock(lock: dict[str, dict]) -> None:
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")


# ── Curated index ─────────────────────────────────────────────────────────────


def resolve_index(name: str) -> SkillSource | None:
    index_file = data_path() / "skills" / "index.toml"
    if not index_file.exists():
        return None
    entry = tomllib.loads(index_file.read_text()).get("skills", {}).get(name)
    if not entry:
        return None
    return SkillSource(
        name=name,
        repo=entry["repo"],
        path=entry["path"],
        ref=entry.get("ref"),
        packages=entry.get("packages", []),
    )


def read_sets_index() -> dict[str, SkillSet]:
    """All skill sets declared in the bundled index."""
    index_file = data_path() / "skills" / "index.toml"
    if not index_file.exists():
        return {}
    sets = tomllib.loads(index_file.read_text()).get("sets", {})
    return {
        name: SkillSet(
            name=name,
            repo=entry["repo"],
            path=entry.get("path", ""),
            ref=entry.get("ref"),
            include=entry.get("include"),
            exclude=entry.get("exclude"),
            members=[
                SkillSetMember(name=m["name"], path=m["path"]) for m in entry["members"]
            ]
            if entry.get("members")
            else None,
            description=entry.get("description", ""),
            packages=entry.get("packages", []),
        )
        for name, entry in sets.items()
    }


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def indexed_for_packages(installed: set[str]) -> list[str]:
    """Return set/skill names from the index whose packages overlap with installed.

    Skips entries that are already installed on disk.
    Returns set names first (preferred over individual skills for the same package),
    then individual skill names not already covered by a matched set.
    """
    normalized = {_normalize(p) for p in installed}
    manifest = read_manifest()

    matched_sets: list[str] = []
    covered_packages: set[str] = set()
    for set_name, sset in read_sets_index().items():
        if any(_normalize(p) in normalized for p in sset.packages):
            covered_packages.update(_normalize(p) for p in sset.packages)
            # Skip if all members already installed
            if set_name not in manifest:
                matched_sets.append(set_name)

    matched_skills: list[str] = []
    index_file = data_path() / "skills" / "index.toml"
    if index_file.exists():
        skills_raw = tomllib.loads(index_file.read_text()).get("skills", {})
        for skill_name, entry in skills_raw.items():
            pkgs = entry.get("packages", [])
            if not any(_normalize(p) in normalized for p in pkgs):
                continue
            if any(_normalize(p) in covered_packages for p in pkgs):
                continue  # already handled by a matched set
            if skill_name not in manifest:
                matched_skills.append(skill_name)

    return matched_sets + matched_skills


def resolve_set(name: str) -> SkillSet | None:
    return read_sets_index().get(name)


# ── Git fetch + unpack ────────────────────────────────────────────────────────


def _git(args: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SkillError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _clone(repo: str, ref: str | None, dest: str) -> str:
    """Clone ``repo`` (at ``ref``) into ``dest``; return the checked-out commit SHA."""
    clone = ["clone", "--depth", "1"]
    if ref:
        clone += ["--branch", ref]
    try:
        _git([*clone, repo, dest])
    except SkillError:
        # ref is a commit SHA (or shallow branch clone unsupported): full clone
        shutil.rmtree(dest, ignore_errors=True)
        Path(dest).mkdir(parents=True, exist_ok=True)
        _git(["clone", repo, dest])
        if ref:
            _git(["checkout", ref], cwd=dest)
    return _git(["rev-parse", "HEAD"], cwd=dest)


def fetch_skill(source: SkillSource, dest: Path) -> str:
    """Clone the source, copy its skill subfolder to ``dest``; return the commit SHA."""
    with tempfile.TemporaryDirectory() as tmp:
        commit = _clone(source.repo, source.ref, tmp)
        src = Path(tmp) / source.path
        if not (src / "SKILL.md").is_file():
            raise SkillError(f"no SKILL.md found at '{source.path}' in {source.repo}")
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
    return commit


# ── Public operations ─────────────────────────────────────────────────────────


def _record(source: SkillSource, commit: str) -> None:
    skills = read_manifest()
    skills[source.name] = source
    write_manifest(skills)

    lock = read_lock()
    lock[source.name] = {
        "repo": source.repo,
        "path": source.path,
        "ref": source.ref,
        "commit": commit,
    }
    write_lock(lock)


def add(
    target: str,
    path: str | None = None,
    ref: str | None = None,
    name: str | None = None,
) -> tuple[SkillSource, str]:
    """Add a skill by curated name or by git URL (with ``path``)."""
    if "://" in target or target.endswith(".git") or "@" in target:
        if not path:
            raise SkillError("--path is required when adding a skill by git URL")
        skill_name = name or Path(path.rstrip("/")).name
        source = SkillSource(name=skill_name, repo=target, path=path, ref=ref)
    else:
        source = resolve_index(target)
        if source is None:
            raise SkillError(
                f"'{target}' is not in the skill index; pass a git URL with --path"
            )
        if name:
            source.name = name
        if ref:
            source.ref = ref

    dest = repo_root() / SKILLS_DIR / source.name
    commit = fetch_skill(source, dest)
    _record(source, commit)
    return source, commit


def add_set(name: str) -> list[tuple[SkillSource, str]]:
    """Install every skill in a named theme, recording each one individually."""
    sset = resolve_set(name)
    if sset is None:
        raise SkillError(f"'{name}' is not a skill set")
    with tempfile.TemporaryDirectory() as tmp:
        commit = _clone(sset.repo, sset.ref, tmp)

        if sset.members is not None:
            members = [(m.name, m.path) for m in sset.members]
        else:
            base = Path(tmp) / sset.path
            if not base.is_dir():
                raise SkillError(f"set path '{sset.path}' not found in {sset.repo}")
            names = sorted(p.parent.name for p in base.glob("*/SKILL.md"))
            if sset.include is not None:
                names = [n for n in names if n in sset.include]
            if sset.exclude:
                names = [n for n in names if n not in sset.exclude]
            members = [
                (n, n if sset.path in (".", "") else f"{sset.path}/{n}") for n in names
            ]
        if not members:
            raise SkillError(f"no skills found for set '{name}' in {sset.repo}")

        installed: list[tuple[SkillSource, str]] = []
        for member_name, member_path in members:
            src = Path(tmp) / member_path
            if not (src / "SKILL.md").is_file():
                raise SkillError(f"no SKILL.md found at '{member_path}' in {sset.repo}")
            dest = repo_root() / SKILLS_DIR / member_name
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
            source = SkillSource(
                name=member_name,
                repo=sset.repo,
                path=member_path,
                ref=sset.ref,
            )
            _record(source, commit)
            installed.append((source, commit))
    return installed


def list_skills() -> list[dict]:
    manifest = read_manifest()
    lock = read_lock()
    rows: list[dict] = []
    for name in sorted(manifest):
        s = manifest[name]
        installed = (repo_root() / SKILLS_DIR / name / "SKILL.md").is_file()
        rows.append(
            {
                "name": name,
                "repo": s.repo,
                "path": s.path,
                "ref": s.ref or "(default)",
                "commit": lock.get(name, {}).get("commit", "")[:12],
                "installed": installed,
            }
        )
    return rows


def update(name: str | None = None) -> list[tuple[str, str, str]]:
    """Re-fetch one or all skills. Returns (name, old_commit, new_commit) tuples."""
    manifest = read_manifest()
    if not manifest:
        raise SkillError("no skills in manifest")
    targets = [name] if name else list(manifest)
    lock = read_lock()
    results: list[tuple[str, str, str]] = []
    for n in targets:
        source = manifest.get(n)
        if source is None:
            raise SkillError(f"'{n}' is not in the manifest")
        old = lock.get(n, {}).get("commit", "")
        commit = fetch_skill(source, repo_root() / SKILLS_DIR / n)
        _record(source, commit)
        results.append((n, old[:12], commit[:12]))
    return results


def remove(name: str) -> None:
    manifest = read_manifest()
    if name not in manifest:
        raise SkillError(f"'{name}' is not in the manifest")
    dest = repo_root() / SKILLS_DIR / name
    if dest.exists():
        shutil.rmtree(dest)
    del manifest[name]
    write_manifest(manifest)
    lock = read_lock()
    lock.pop(name, None)
    write_lock(lock)
