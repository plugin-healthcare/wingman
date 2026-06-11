"""wingman CLI — agent superpowers for any project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from wingman.core import (
    REPO_ROOT,
    TOOL_TARGETS,
    assemble_agents,
    merged_servers,
    sync_tools,
)

app = typer.Typer(
    name="wingman",
    help="Agent superpowers for any project. Stack-aware setup for Copilot, Claude Code, Cursor, Goose, and opencode.",
    no_args_is_help=True,
)

new_app = typer.Typer(help="Scaffold new prompts, agents, and recipes.")
app.add_typer(new_app, name="new")

StackArg = Annotated[str | None, typer.Argument(help="Stack to activate, e.g. python")]
ToolOption = Annotated[
    list[str] | None,
    typer.Option(
        "--only", "-o", help=f"Limit to specific tools: {', '.join(TOOL_TARGETS)}"
    ),
]
DryRunOption = Annotated[
    bool, typer.Option("--dry-run", help="Preview without writing files.")
]


# ── setup ─────────────────────────────────────────────────────────────────────


@app.command()
def setup(
    stack: StackArg = None,
    only: ToolOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Assemble AGENTS.md + .mcp.json from core + stack, then sync to all tools."""
    _assemble(stack, dry_run)
    servers = merged_servers(stack)
    tools = _resolve_tools(only)
    typer.echo(f"\nSyncing {len(servers)} MCP server(s) → {', '.join(tools)}")
    for line in sync_tools(servers, tools, dry_run):
        typer.echo(line)


# ── assemble ──────────────────────────────────────────────────────────────────


@app.command()
def assemble(
    stack: StackArg = None,
    dry_run: DryRunOption = False,
) -> None:
    """Merge core + stack into root AGENTS.md and .mcp.json (sources of truth)."""
    _assemble(stack, dry_run)


def _assemble(stack: str | None, dry_run: bool) -> None:
    typer.echo(f"Assembling: core{f' + {stack}' if stack else ''}")

    agents_content = assemble_agents(stack)
    agents_path = REPO_ROOT / "AGENTS.md"
    if dry_run:
        typer.echo("  [dry-run] AGENTS.md")
    else:
        agents_path.write_text(agents_content)
        typer.echo("  wrote AGENTS.md")

    servers = merged_servers(stack)
    mcp_path = REPO_ROOT / ".mcp.json"
    mcp_content = json.dumps({"mcpServers": servers}, indent=2) + "\n"
    if dry_run:
        typer.echo("  [dry-run] .mcp.json")
    else:
        mcp_path.write_text(mcp_content)
        typer.echo("  wrote .mcp.json")


# ── sync ──────────────────────────────────────────────────────────────────────


@app.command()
def sync(
    stack: StackArg = None,
    only: ToolOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Sync root .mcp.json to tool-specific config files."""
    servers = merged_servers(stack)
    tools = _resolve_tools(only)
    typer.echo(f"Syncing {len(servers)} MCP server(s) → {', '.join(tools)}")
    for line in sync_tools(servers, tools, dry_run):
        typer.echo(line)


# ── new ───────────────────────────────────────────────────────────────────────


@new_app.command("prompt")
def new_prompt(
    name: Annotated[str, typer.Argument(help="Prompt name, e.g. 'review'")],
) -> None:
    """Scaffold a new .prompt.md file."""
    path = REPO_ROOT / ".github" / "prompts" / f"{name}.prompt.md"
    _scaffold(
        path,
        '---\ndescription: "TODO: describe when to use this"\nagent: agent\n---\n\nTODO: prompt body\n',
    )


@new_app.command("agent")
def new_agent(
    name: Annotated[str, typer.Argument(help="Agent name, e.g. 'data-analyst'")],
) -> None:
    """Scaffold a new .agent.md custom agent file."""
    path = REPO_ROOT / ".github" / "agents" / f"{name}.agent.md"
    _scaffold(
        path,
        '---\ndescription: "TODO: Use when ... (include trigger phrases)"\ntools: [read, search]\nuser-invocable: true\n---\n\nYou are a specialist at TODO.\n\n## Constraints\n- Only do TODO.\n\n## Output Format\nTODO\n',
    )


@new_app.command("recipe")
def new_recipe(
    name: Annotated[str, typer.Argument(help="Recipe name, e.g. 'nightly-pipeline'")],
) -> None:
    """Scaffold a new Goose recipe YAML file."""
    path = REPO_ROOT / "recipes" / f"{name}.yaml"
    _scaffold(
        path,
        f"version: 1.0.0\ntitle: {name}\ndescription: TODO\nprompt: |\n  TODO: describe the task for Goose.\n",
    )
    typer.echo(f"  run with: goose run recipes/{name}.yaml")


# ── document templates ────────────────────────────────────────────────────────

_TEMPLATE_MAP = {
    "story": ("templates/agile/story.md", "docs/stories", "{slug}.md"),
    "epic": ("templates/agile/epic.md", "docs/epics", "{slug}.md"),
    "bug": ("templates/agile/bug.md", "docs/bugs", "{slug}.md"),
    "spike": ("templates/agile/spike.md", "docs/spikes", "{slug}.md"),
    "adr": ("templates/decisions/adr.md", "docs/decisions", "{number:04d}-{slug}.md"),
    "post-mortem": (
        "templates/engineering/post-mortem.md",
        "docs/post-mortems",
        "{slug}.md",
    ),
    "runbook": ("templates/engineering/runbook.md", "docs/runbooks", "{slug}.md"),
}


@new_app.command("doc")
def new_doc(
    kind: Annotated[
        str, typer.Argument(help=f"Document type: {', '.join(_TEMPLATE_MAP)}")
    ],
    title: Annotated[
        str, typer.Argument(help="Title, e.g. 'use postgres over mongodb'")
    ],
) -> None:
    """Create a new document from a template (story, epic, bug, spike, adr, post-mortem, runbook)."""
    if kind not in _TEMPLATE_MAP:
        typer.echo(
            f"Unknown kind '{kind}'. Choose from: {', '.join(_TEMPLATE_MAP)}", err=True
        )
        raise typer.Exit(1)

    template_rel, dest_dir, filename_pattern = _TEMPLATE_MAP[kind]
    template_path = REPO_ROOT / template_rel
    slug = title.lower().replace(" ", "-").replace("/", "-")
    today = __import__("datetime").date.today().isoformat()

    dest = REPO_ROOT / dest_dir
    if "{number" in filename_pattern:
        # Auto-number: count existing files with numeric prefix
        dest.mkdir(parents=True, exist_ok=True)
        existing = sorted(dest.glob("[0-9]*.md"))
        number = len(existing) + 1
        filename = filename_pattern.format(number=number, slug=slug)
    else:
        filename = filename_pattern.format(slug=slug)

    out_path = dest / filename
    content = template_path.read_text()
    content = (
        content.replace("{title}", title)
        .replace("{date}", today)
        .replace("{number}", f"{number:04d}" if "{number" in filename_pattern else "")
    )

    _scaffold(out_path, content)


def _scaffold(path: Path, content: str) -> None:
    if path.exists():
        typer.echo(f"Already exists: {path.relative_to(REPO_ROOT)}", err=True)
        raise typer.Exit(1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    typer.echo(f"Created {path.relative_to(REPO_ROOT)}")


# ── helpers ───────────────────────────────────────────────────────────────────


def _resolve_tools(only: list[str] | None) -> list[str]:
    if not only:
        return TOOL_TARGETS
    invalid = set(only) - set(TOOL_TARGETS)
    if invalid:
        typer.echo(
            f"Unknown tools: {', '.join(invalid)}. Valid: {', '.join(TOOL_TARGETS)}",
            err=True,
        )
        raise typer.Exit(1)
    return list(only)
