# MCP servers in wingman

MCP lets Copilot call external tools (git, GitHub, docs lookups, and so on).
wingman can wire these servers into a repo. This doc covers where the config
goes, the servers wingman offers, and what each one does with your code.

## Where the config goes

wingman writes the repo-root `.mcp.json` using the `mcpServers` key. That is the
file the GitHub Copilot CLI reads. Servers are opt-in: `wingman init` and
`wingman add` show a picker, with a couple pre-checked as defaults.

There is no single MCP file shared by every Copilot surface:

| Surface | Reads from | Top-level key | wingman writes it |
| --- | --- | --- | --- |
| Copilot CLI (terminal) | repo-root `.mcp.json` | `mcpServers` | yes |
| VS Code editor | `.vscode/mcp.json` | `servers` | no |
| Copilot coding agent (cloud) | repo Settings UI on GitHub | not a file | no |

VS Code does not read the root `.mcp.json`. To use these servers in the VS Code
editor, copy the entries into `.vscode/mcp.json` under a `servers` key, or run
"MCP: Add Server" then "Workspace" from the Command Palette. The coding agent is
configured in the repo's Copilot settings on GitHub, not from a file.

## Transport: local vs remote

The picker tags each server:

- `[local]` (stdio): runs as a subprocess on your machine, with its working
  directory set to your repo. Files stay on disk. Examples: `git`, `likec4`, `docs`.
- `[remote]` (http): an http endpoint hosted by a vendor. The request goes to a
  third party. Examples: `github`, `polars`.

wingman avoids the VS Code-only `${workspaceFolder}` variable. Stdio servers
already launch in your repo, so `mcp-server-git` runs with no `--repository` and
`@likec4/mcp` with no `LIKEC4_WORKSPACE`. This works in the CLI, the coding agent,
and VS Code.

## Privacy

Local stdio servers (`git`, `likec4`, `docs`) do not upload your code. `mcpdoc`
only fetches a public docs URL.

Remote http servers (`github`, `polars`) send the tool-call arguments to a third
party, and the model composes those arguments. Even a generic question can carry
your data, since the model may include column names, schema, a sample row, or a
code snippet to get a better answer:

- `github` goes to `api.githubcopilot.com`, which already hosts your code, so
  nothing new leaves your trust boundary.
- `polars` goes to `mcp.pola.rs`, a hosted docs assistant backed by Kapa.ai. It
  cannot run locally, is opt-in (off by default), and prints a warning when you
  enable it.

Separately, the model itself is a remote service. Whatever a tool returns and the
model reads (a git diff, a snippet) goes to Copilot's backend, the same as any
Copilot use. Local servers keep file access local, but what the model consumes
still reaches the model provider. For private repos, prefer local servers and
check your Copilot plan's data policy.

## Available servers

| Server | Transport | Default | Where data goes | What it gives Copilot |
| --- | --- | --- | --- | --- |
| `github` | http | yes | GitHub (already hosts your code) | Issues, PRs, repos, code search |
| `git` | stdio | yes | stays local | Git history, blame, diff on the current repo |
| `polars` | http | no | Polars/Kapa.ai | Polars API and docs knowledge |
| `likec4` | stdio | no | stays local | Query your LikeC4 architecture model |
| `docs` (mcpdoc) | stdio | added by `wingman sync --docs` | fetches a public `llms.txt` | Library docs from an `llms.txt` |

Servers are defined in `src/wingman/data/mcp/catalog.toml`. Add repo-local servers
in `.wingman/mcp.local.json` and wingman merges them in.
