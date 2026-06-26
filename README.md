# Wingman

A GitHub Copilot guardrail toolkit. Wingman is a small Python CLI you install in a
repo to set up Copilot the way you would: it writes the instruction and MCP files
Copilot reads, fetches and updates reusable skills, scaffolds prompts and agents,
and runs a check gate that "programs and checks like me".

Wingman is Python + uv focused and **GitHub Copilot only**.

## What Wingman is (and is not)

There is a clean split between the two halves of the workflow:

- **Wingman (this CLI) does setup and management.** It is a normal command-line
  tool. It writes files into your repo, fetches skills from git, audits those
  files for best practices, and runs your lint/format/test gate. It does not talk
  to a model at runtime (except `audit --deep`, which shells out to the Copilot
  CLI for an optional content review).
- **GitHub Copilot does the runtime work.** Copilot reads the files Wingman writes
  (`.github/copilot-instructions.md`, `.github/skills/`, `.github/agents/`,
  `.github/prompts/`, `.mcp.json`) while you code. Wingman never replaces
  Copilot; it just gets the guardrails in place and keeps them healthy.

In short: **Wingman installs and maintains the guardrails, Copilot uses them.**

## Install

Run it without installing:

```bash
uvx wingman init
```

Or add it as a dev dependency of your project:

```bash
uv add --dev wingman
uv run wingman init
```

Every command operates on the current working directory (the repo you are in).

## Quick start

```bash
wingman init            # write copilot-instructions.md + .mcp.json, then pick artifacts
wingman list            # show the Copilot triggers active in this repo
wingman check           # run the lint/format/test gate
wingman audit           # lint your skills/agents/instructions for best practices
```

## Commands

| Command | What it does |
| --- | --- |
| `wingman init [stack]` | Write `.github/copilot-instructions.md` and `.mcp.json`, then open a menu to pick skill themes, agents, prompts, instructions, and MCP servers. Stack defaults to `python`. |
| `wingman add` | Re-open the catalog menu to install more artifacts. |
| `wingman sync [--all] [--no-docs]` | Discover skills bundled in installed packages and copy them in; for packages with a known skill theme, fetch those; for the rest, probe PyPI for an `llms.txt` and wire it into the `docs` MCP server. |
| `wingman list` | Show what Copilot will pick up: always-on instructions, scoped instructions, slash-command prompts, agents, and skills. |
| `wingman skill add <theme\|git-url>` | Fetch skills into `.github/skills/<name>/`. Use a **theme** name (e.g. `duckdb`) to install all its skills, or a git URL with `--path` (and optional `--ref`) for a one-off. |
| `wingman skill list` | List installed skills. Add `--all` to also show available themes. |
| `wingman skill update [name]` | Re-fetch one or all skills to their latest commit. |
| `wingman skill remove <name>` | Delete a skill from disk and the manifest. |
| `wingman agent list` | List bundled agents and whether each is installed in this repo. |
| `wingman agent add <name>` | Install a bundled agent (e.g. `yoda`, `marvin`) into `.github/agents/`. |
| `wingman check [stack]` | Run the lint/format/test gate. |
| `wingman audit [paths…]` | Lint guardrail artifacts. `--deep` adds an LLM content review via the Copilot CLI; `--strict` fails on warnings too. |
| `wingman new prompt\|agent\|doc …` | Scaffold a prompt, agent, or document from a template. |

## What gets written into your repo

```
.github/
  copilot-instructions.md          # always-on instructions Copilot reads
  instructions/*.instructions.md   # scoped instructions (applyTo globs)
  skills/<name>/SKILL.md           # fetched skills (+ references/, assets/)
  agents/<name>.agent.md           # custom agents
  prompts/<name>.prompt.md         # slash-command prompts
.mcp.json                          # MCP servers (Copilot CLI "mcpServers" schema)
.wingman/
  skills.toml                      # skill manifest (source of truth)
  skills.lock                      # pinned commits
  checks.toml                      # optional: override the check gate
  instructions.local.md            # optional: appended to copilot-instructions.md
  mcp.local.json                   # optional: merged into .mcp.json
```

## MCP setup

Wingman writes the repo-root `.mcp.json` (the editor-agnostic location the
**GitHub Copilot CLI** reads, using a top-level `mcpServers` object). MCP servers
are **opt-in**: `wingman init` / `wingman add` show a picker so you choose which to
wire in (a couple are pre-checked as sensible defaults). Selecting a server merges
it into `.mcp.json`, keeping any servers already there. Available servers:

| Server | Transport | Default | What it gives Copilot |
| --- | --- | --- | --- |
| `github` | http (`api.githubcopilot.com`) | ✓ | Issues, PRs, repos, code search |
| `git` | stdio (`uvx mcp-server-git`) | ✓ | Git operations on the current repo |
| `polars` | http (`mcp.pola.rs`) | — | Polars API and docs knowledge |
| `likec4` | stdio (`npx @likec4/mcp`) | — | Query your LikeC4 architecture model |

Enabling a non-default `[remote]` server (e.g. `polars`) prints a warning that its
request payload, which the model composes and may pack with your data, goes to a
third party. See [`docs/mcp.md`](docs/mcp.md) for the full privacy breakdown.

> **Using VS Code?** VS Code's Copilot does **not** read the root `.mcp.json` — it
> only reads `.vscode/mcp.json`, which uses a different top-level key (`servers`
> instead of `mcpServers`). To use these servers inside the VS Code editor, copy the
> server entries into `.vscode/mcp.json` under a `servers` key, or run **MCP: Add
> Server** from the Command Palette and choose **Workspace**. The Copilot CLI and the
> Copilot coding agent do not need this; only the VS Code editor does.

stdio servers operate on their **launch directory** (the repo), so they work outside
VS Code too. Wingman deliberately avoids the VS Code-only `${workspaceFolder}`
variable: `mcp-server-git` and `@likec4/mcp` both default to the current directory,
which the MCP host sets to your repo root.

Add repo-local servers in `.wingman/mcp.local.json`; Wingman merges them in. The
`docs` server (`uvx mcpdoc`) is wired in on demand by `wingman sync --docs`, which
probes packages for an `llms.txt` and serves it over MCP. Other optional servers that
need a token include [`pydantic/logfire-mcp`](https://github.com/pydantic/logfire-mcp)
and [`motherduckdb/mcp-server-motherduck`](https://github.com/motherduckdb/mcp-server-motherduck).

Note: the **Copilot coding agent** (the cloud agent) reads its MCP configuration
from your repository's Copilot settings on GitHub, not from a committed file.
Wingman cannot write that for you; configure it in the repo settings UI.

## Skills

Skills are grouped into **themes** in the `wingman init` / `wingman add` picker:
pick a theme and all of its skills install at once. List them with
`wingman skill list --all`, or install one directly with `wingman skill add <theme>`.
The index currently ships:

- **duckdb** (from [`duckdb/duckdb-skills`](https://github.com/duckdb/duckdb-skills)):
  every official DuckDB skill (`query`, `read-file`, `attach-db`, `convert-file`,
  `s3-explore`, `spatial`, …).
- **streamlit** (from [`streamlit/agent-skills`](https://github.com/streamlit/agent-skills)):
  building, styling, and deploying Streamlit apps.
- **dagster** (from [`dagster-io/skills`](https://github.com/dagster-io/skills)):
  `dagster-expert` (Dagster + `dg` CLI guidance) and `dignified-python`
  (opinionated production Python standards).
- **agent-tooling** (from [`anthropics/skills`](https://github.com/anthropics/skills)):
  `skill-creator` and `mcp-builder`.
- **developing** (from [`anthropics/skills`](https://github.com/anthropics/skills)):
  `webapp-testing` (Playwright-driven web app testing).
- **likec4** (from [`likec4/likec4`](https://github.com/likec4/likec4)):
  `likec4-dsl` reference for `.c4`/`.likec4` files.


```bash
wingman skill add query           # one skill, from the index
wingman skill add duckdb           # a whole set (all DuckDB skills at once)
wingman skill add streamlit        # the official Streamlit skill
wingman skill add https://github.com/org/repo --path skills/foo --ref main
```

**Sets** bundle every skill under a directory so you can grab them in one go.
`wingman skill add duckdb` clones [`duckdb/duckdb-skills`](https://github.com/duckdb/duckdb-skills)
once and installs all its skills (minus the Claude-Code-only `read-memories`),
recording each individually so `skill list`, `update`, and `remove` still work
per-skill. See sets at the bottom of `wingman skill list --all`.

Not every popular library has an official skill. FastAPI, Pydantic, and Polars
ship no official `SKILL.md`; Polars is covered through its MCP server above, and
Pydantic through the `docs` MCP server (its `llms.txt`). Add your own to
`.wingman/skills.toml` (or the index) any time.

## The check gate

`wingman check` runs the commands in `.wingman/checks.toml`, or the bundled
defaults for your stack. The Python default is:

```toml
[[check]]
name = "lint"
cmd = "uv run ruff check"

[[check]]
name = "format"
cmd = "uv run ruff format --check"

[[check]]
name = "test"
cmd = "uv run pytest --tb=short"
```

It stops on the first failure (use `--no-fail-fast` to run them all) and exits
non-zero if any check fails, so it works as a pre-commit or CI gate.

## Auditing guardrails

`wingman audit` is a deterministic linter for the files Copilot consumes. It
checks the mechanical things that make a skill or instruction effective: a
kebab-case name that matches its folder, a description that says *when* to use it,
complete frontmatter, and a body that is neither empty nor bloated.

For the subjective half (is this skill actually well written?), `--deep` hands the
files to the Copilot CLI using the bundled `skill-reviewer` agent. The mechanical
audit always runs; the deep review is opt-in because it costs a model call.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
uv run ruff format
```

## Credits

Projects we borrowed ideas from or built on top of:

- **[library-skills](https://github.com/tiangolo/library-skills)** by tiangolo: the convention of shipping `SKILL.md` files inside Python packages under `.agents/skills/`. `wingman sync` scans installed packages using that standard and brings discovered skills into `.github/skills/` for Copilot.
- **[ponytail](https://github.com/DietrichGebert/ponytail)** by DietrichGebert: a "write only what the task needs" ruleset for AI agents. Informed the thinking behind Wingman's default instructions and check gate philosophy.
