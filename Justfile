# Wingman — agent setup task runner
# Requires: just (https://just.systems), uv (https://github.com/astral-sh/uv)
#
# Canonical sources (edit these):
#   instructions/base.md + instructions/<stack>.md  →  assembled into root AGENTS.md
#   mcp/base.json + mcp/<stack>.json                →  assembled into root .mcp.json
#
# Generated outputs (gitignored, recreate with `just sync`):
#   .vscode/mcp.json, .cursor/mcp.json, .goose/config.yaml, opencode.json

default:
    @just --list

# Install the wingman CLI
install:
    uv sync

# ── Setup: assemble + sync in one command ─────────────────────────────────────

# Set up everything for a stack and optional tool
# Usage: just setup python
#        just setup python --only vscode
setup *args:
    uv run wingman setup {{args}}

# ── Assemble root files from core + stack ─────────────────────────────────────

# Merge core + stack into root AGENTS.md and .mcp.json
# Usage: just assemble python
assemble *args:
    uv run wingman assemble {{args}}

# ── Sync root .mcp.json to tool-specific configs ──────────────────────────────

# Sync to all tools (or pass --only vscode|cursor|goose|opencode)
sync *args:
    uv run wingman sync {{args}}

# Preview what would change without writing
dry-run stack="":
    uv run wingman setup {{stack}} --dry-run

# ── Scaffolding ───────────────────────────────────────────────────────────────

# Scaffold agent primitives:  just new prompt review
#                             just new agent data-analyst
#                             just new recipe nightly-pipeline
new kind name:
    uv run wingman new {{kind}} {{name}}

# Create a document from a template:  just doc adr "use postgres"
#                                     just doc story "enable SSO login"
#                                     just doc post-mortem "db outage"
doc kind +title:
    uv run wingman new doc {{kind}} "{{title}}"
