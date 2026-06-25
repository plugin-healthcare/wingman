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
  `.github/prompts/`, `.vscode/mcp.json`) while you code. Wingman never replaces
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
wingman init            # write copilot-instructions.md + .vscode/mcp.json, then pick artifacts
wingman list            # show the Copilot triggers active in this repo
wingman check           # run the lint/format/test gate
wingman audit           # lint your skills/agents/instructions for best practices
```

## Commands

| Command | What it does |
| --- | --- |
| `wingman init [stack]` | Write `.github/copilot-instructions.md` and `.vscode/mcp.json`, then open a menu to pick skills/agents/prompts/instructions. Stack defaults to `python`. |
| `wingman add` | Re-open the catalog menu to install more artifacts. |
| `wingman list` | Show what Copilot will pick up: always-on instructions, scoped instructions, slash-command prompts, agents, and skills. |
| `wingman skill add <name\|set\|git-url>` | Fetch a skill into `.github/skills/<name>/`. Use a curated short name, a **set** name (e.g. `duckdb`) to install a whole bundle, or a git URL with `--path` (and optional `--ref`). |
| `wingman skill list` | List installed skills. Add `--all` to see every indexed skill marked installed (✓) vs available (—). |
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
.vscode/
  mcp.json                         # MCP servers (VS Code "servers" schema)
.wingman/
  skills.toml                      # skill manifest (source of truth)
  skills.lock                      # pinned commits
  checks.toml                      # optional: override the check gate
  instructions.local.md            # optional: appended to copilot-instructions.md
  mcp.local.json                   # optional: merged into .vscode/mcp.json
```

## MCP setup

Wingman writes `.vscode/mcp.json` using the VS Code schema (a top-level `servers`
object). That file configures MCP servers for Copilot in VS Code. The Python stack
ships these official servers by default:

| Server | Transport | Auth | What it gives Copilot |
| --- | --- | --- | --- |
| `polars` | http (`mcp.pola.rs`) | none | Polars API and docs knowledge |
| `git` | stdio (`uvx mcp-server-git`) | none | Git operations on the workspace |
| `github` | http (`api.githubcopilot.com`) | VS Code GitHub sign-in | Issues, PRs, repos, code search |
| `docs` | stdio (`uvx mcpdoc`) | none | Library docs from `llms.txt` (Pydantic by default) |

The `docs` server uses [`langchain-ai/mcpdoc`](https://github.com/langchain-ai/mcpdoc)
to serve any project's `llms.txt` over MCP. Pydantic ships no official skill or
server, so it is wired in here. Add more sources by appending `Name:URL` pairs to
the `--urls` argument in `.vscode/mcp.json` (for example
`Pydantic:https://docs.pydantic.dev/latest/llms.txt FastAPI:https://fastapi.tiangolo.com/llms.txt`).

Add repo-local servers in `.wingman/mcp.local.json`; Wingman merges them in. Optional
servers that need a token (so they are not defaults) include
[`pydantic/logfire-mcp`](https://github.com/pydantic/logfire-mcp) and
[`motherduckdb/mcp-server-motherduck`](https://github.com/motherduckdb/mcp-server-motherduck)
for MotherDuck. The defaults need only `uv` (for the `git` server); the `http`
servers need no local runtime, and nothing here requires `npx`/Node.

Note: the **Copilot coding agent** (the cloud agent) reads its MCP configuration
from your repository's Copilot settings on GitHub, not from a committed file.
Wingman cannot write that for you; configure it in the repo settings UI.

## Skills

`wingman skill add <name>` resolves a short name from a curated index of official
skills, or takes a git URL with `--path`. See everything on offer with
`wingman skill list --all` (✓ installed, — available). The index currently ships:

- **DuckDB** (from [`duckdb/duckdb-skills`](https://github.com/duckdb/duckdb-skills)):
  `query`, `read-file`, `install-duckdb`, `duckdb-docs`, `attach-db`,
  `convert-file`, `s3-explore`, `spatial`. Set: `duckdb`.
- **Streamlit** (from [`streamlit/agent-skills`](https://github.com/streamlit/agent-skills)):
  `developing-with-streamlit`. Set: `streamlit`.
- **Dagster** (from [`dagster-io/skills`](https://github.com/dagster-io/skills)):
  `dagster-expert` (Dagster + `dg` CLI guidance) and `dignified-python`
  (opinionated production Python standards).
- **General engineering** (from [`anthropics/skills`](https://github.com/anthropics/skills)):
  `skill-creator`, `mcp-builder`, `webapp-testing`.

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
