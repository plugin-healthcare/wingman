"""The catalog: bundled agents/prompts/instructions plus indexed skills.

Drives the interactive ``wingman init`` / ``wingman add`` selection. Skills are
fetched from git via :mod:`wingman.skills`; agents, prompts, and scoped
instructions are copied from package data into the repo's ``.github/``.
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from wingman import skills
from wingman.core import data_path, repo_root

GITHUB = Path(".github")


@dataclass
class CatalogItem:
    name: str
    kind: str  # skill | agent | prompt | instructions
    description: str
    source: Path | None = None  # package-data path for bundled items


# ── Discovery ─────────────────────────────────────────────────────────────────


def _first_paragraph(text: str) -> str:
    from wingman.audit import parse_frontmatter

    fm, body = parse_frontmatter(text)
    if fm.get("description"):
        return fm["description"]
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return ""


def _bundled(kind: str, folder: str, pattern: str) -> list[CatalogItem]:
    base = data_path() / "catalog" / folder
    if not base.is_dir():
        return []
    items: list[CatalogItem] = []
    for path in sorted(base.glob(pattern)):
        rel = path.relative_to(base)
        items.append(
            CatalogItem(
                name=str(rel),
                kind=kind,
                description=_first_paragraph(path.read_text()),
                source=path,
            )
        )
    return items


def catalog_skills() -> list[CatalogItem]:
    index = data_path() / "skills" / "index.toml"
    if not index.exists():
        return []
    entries = tomllib.loads(index.read_text()).get("skills", {})
    return [
        CatalogItem(name=name, kind="skill", description=entry.get("description", ""))
        for name, entry in entries.items()
    ]


def catalog(kinds: list[str]) -> dict[str, list[CatalogItem]]:
    out: dict[str, list[CatalogItem]] = {}
    if "skills" in kinds:
        out["skills"] = catalog_skills()
    if "agents" in kinds:
        out["agents"] = _bundled("agent", "agents", "*.agent.md")
    if "prompts" in kinds:
        out["prompts"] = _bundled("prompt", "prompts", "**/*.prompt.md")
    if "instructions" in kinds:
        out["instructions"] = _bundled(
            "instructions", "instructions", "*.instructions.md"
        )
    return out


def find_agent(name: str) -> CatalogItem | None:
    """Resolve a catalog agent by short name ('yoda') or filename ('yoda.agent.md')."""
    filename = name if name.endswith(".agent.md") else f"{name}.agent.md"
    return next(
        (it for it in catalog(["agents"])["agents"] if it.name == filename), None
    )


# ── Install ───────────────────────────────────────────────────────────────────

_DEST = {
    "agent": GITHUB / "agents",
    "prompt": GITHUB / "prompts",
    "instructions": GITHUB / "instructions",
}


def install_item(item: CatalogItem) -> str:
    """Install one catalog item into the repo. Returns a status line."""
    if item.kind == "skill":
        source, commit = skills.add(item.name)
        return f"  skill   {source.name} @ {commit[:12]}"

    assert item.source is not None
    dest = repo_root() / _DEST[item.kind] / item.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(item.source, dest)
    return f"  {item.kind:7s} {item.name}"
