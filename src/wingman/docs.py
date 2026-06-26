"""Docs fallback: discover llms.txt for installed packages and wire them into
the mcpdoc MCP server in .mcp.json.

For each package that has no embedded skill, we query the PyPI JSON API for its
documentation URL and probe common llms.txt locations. Found URLs are added as
sources to the existing ``docs`` mcpdoc server entry, so Copilot gets up-to-date
library docs even when no SKILL.md exists.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from wingman.core import MCP_CONFIG, repo_root

_PYPI_API = "https://pypi.org/pypi/{package}/json"
_LLMS_PATHS = ("llms.txt", "llms-full.txt")

# Keys in project_urls we try, in preference order.
_DOC_URL_KEYS = ("Documentation", "Docs", "documentation", "Homepage", "homepage")


# ── PyPI lookup ───────────────────────────────────────────────────────────────


def _fetch_json(url: str, timeout: int = 8) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def _candidate_doc_urls(pypi_info: dict) -> list[str]:
    """Return candidate documentation base URLs from PyPI package info."""
    urls: list[str] = []
    project_urls: dict = pypi_info.get("project_urls") or {}
    for key in _DOC_URL_KEYS:
        url = project_urls.get(key, "").rstrip("/")
        if url and url not in urls:
            urls.append(url)
    # Also try the top-level docs_url / home_page fields.
    for field in ("docs_url", "home_page"):
        url = (pypi_info.get(field) or "").rstrip("/")
        if url and url not in urls:
            urls.append(url)
    return urls


def _head_ok(url: str, timeout: int = 6) -> bool:
    """Return True if a HEAD request to url returns 200."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def find_llms_txt(package: str) -> tuple[str, str] | None:
    """Return (label, llms_txt_url) for a package, or None if not found.

    Queries PyPI for the package's documentation URL, then probes for
    llms.txt / llms-full.txt at that location.
    """
    data = _fetch_json(_PYPI_API.format(package=package))
    if data is None:
        return None
    info = data.get("info") or {}
    label = info.get("name") or package

    for base_url in _candidate_doc_urls(info):
        for path in _LLMS_PATHS:
            candidate = f"{base_url}/{path}"
            if _head_ok(candidate):
                return label, candidate

    return None


# ── mcp.json helpers ──────────────────────────────────────────────────────────


def _mcp_path() -> Path:
    return repo_root() / MCP_CONFIG


def read_mcp() -> dict:
    path = _mcp_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _existing_urls(args: list) -> dict[str, str]:
    """Parse existing Name:URL pairs from the mcpdoc args list."""
    try:
        idx = args.index("--urls")
    except ValueError:
        return {}
    if idx + 1 >= len(args):
        return {}
    pairs: dict[str, str] = {}
    for token in args[idx + 1].split():
        if ":" in token:
            label, _, url = token.partition(":")
            pairs[label] = url
    return pairs


def add_llms_sources(new_sources: dict[str, str]) -> dict[str, str]:
    """Merge new_sources into the docs mcpdoc server in .mcp.json.

    Returns a dict of {label: url} entries that were actually added (skips
    labels already present). Does nothing if no docs server is configured.
    """
    if not new_sources:
        return {}

    mcp = read_mcp()
    servers = mcp.get("servers") or mcp.get("mcpServers") or {}
    docs = servers.get("docs")
    if not isinstance(docs, dict):
        return {}

    args: list = docs.get("args") or []
    existing = _existing_urls(args)

    added = {k: v for k, v in new_sources.items() if k not in existing}
    if not added:
        return {}

    merged = {**existing, **added}
    urls_str = " ".join(f"{k}:{v}" for k, v in sorted(merged.items()))

    try:
        idx = args.index("--urls")
        args[idx + 1] = urls_str
    except ValueError:
        args.extend(["--urls", urls_str])

    path = _mcp_path()
    path.write_text(json.dumps(mcp, indent=2) + "\n")
    return added


# ── Public entry point ────────────────────────────────────────────────────────


def sync_docs(packages: list[str]) -> dict[str, str]:
    """For each package, look up llms.txt and add found ones to mcp.json.

    Returns a dict of {label: url} for every source successfully added.
    """
    found: dict[str, str] = {}
    for pkg in packages:
        result = find_llms_txt(pkg)
        if result:
            label, url = result
            found[label] = url
    return add_llms_sources(found)
