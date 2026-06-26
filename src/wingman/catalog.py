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
from wingman.core import add_mcp_server, data_path, repo_root

GITHUB = Path(".github")


@dataclass
class CatalogItem:
    name: str
    kind: str  # skill | agent | prompt | instructions | mcp
    description: str
    source: Path | None = None  # package-data path for bundled items
    is_set: bool = False  # skill themes that install a bundle of skills
    checked: bool = False  # pre-selected in the picker (e.g. default MCP servers)


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
    """Skill themes offered in the picker, one entry per theme (set).

    Selecting a theme installs all of its skills. Any loose ``[skills.*]`` index
    entries not covered by a theme are appended as individual selectable items.
    """
    items: list[CatalogItem] = []
    for name, sset in skills.read_sets_index().items():
        items.append(
            CatalogItem(
                name=name, kind="skill", description=sset.description, is_set=True
            )
        )

    index = data_path() / "skills" / "index.toml"
    if index.exists():
        loose = tomllib.loads(index.read_text()).get("skills", {})
        for name, entry in loose.items():
            items.append(
                CatalogItem(
                    name=name,
                    kind="skill",
                    description=entry.get("description", ""),
                )
            )
    return items


def _mcp_catalog_raw() -> dict:
    path = data_path() / "mcp" / "catalog.toml"
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text()).get("servers", {})


def _is_remote(config: dict) -> bool:
    """True for http endpoints whose request payload leaves the machine."""
    return "url" in config or config.get("type") == "http"


def catalog_mcp() -> list[CatalogItem]:
    """Optional MCP servers offered in the picker, one entry per server.

    Each description is prefixed with where the server runs and whether data
    leaves the machine: ``[local]`` (stdio subprocess, files stay on disk) or
    ``[remote]`` (http endpoint, queries go to a third party).
    """
    items: list[CatalogItem] = []
    for name, entry in _mcp_catalog_raw().items():
        config = entry.get("config", {})
        tag = "[remote]" if _is_remote(config) else "[local]"
        description = f"{tag} {entry.get('description', '')}".strip()
        items.append(
            CatalogItem(
                name=name,
                kind="mcp",
                description=description,
                checked=bool(entry.get("default", False)),
            )
        )
    return items


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
    if "mcp" in kinds:
        out["mcp"] = catalog_mcp()
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
        if item.is_set:
            installed = skills.add_set(item.name)
            names = ", ".join(s.name for s, _ in installed)
            return f"  theme   {item.name} ({len(installed)} skills: {names})"
        source, commit = skills.add(item.name)
        return f"  skill   {source.name} @ {commit[:12]}"

    if item.kind == "mcp":
        entry = _mcp_catalog_raw().get(item.name)
        if entry is None:
            raise ValueError(f"unknown MCP server '{item.name}'")
        config = entry.get("config", {})
        line = add_mcp_server(item.name, config)
        # Opt-in remote servers send the model's tool-call arguments to a
        # third party. The curated defaults (Copilot-hosted github, local git)
        # stay within the trust boundary, so only warn for the rest.
        if _is_remote(config) and not entry.get("default", False):
            line += (
                f"\n  \u26a0 {item.name} is a remote server: the model composes "
                "the request, so your queries (and any data, schema, or code it "
                "embeds) are sent to a third party. Enable only for non-sensitive "
                "work (see docs/mcp.md)."
            )
        return line

    assert item.source is not None
    dest = repo_root() / _DEST[item.kind] / item.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(item.source, dest)
    return f"  {item.kind:7s} {item.name}"
