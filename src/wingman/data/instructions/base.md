# Core — Generic DevOps Cycle

These instructions apply to all projects regardless of stack.

## Workflow

- Before implementing anything non-trivial, draft a plan and confirm it.
- Work in small, reviewable increments. One logical change per commit.
- Always run tests and lint before marking work done.
- When blocked, say so — don't silently guess.

## Git

- Commit messages: imperative mood, max 72 chars subject line.
- Never commit secrets, credentials, or local config files.
- Branch names: `<type>/<short-description>` (e.g. `feat/add-auth`, `fix/null-pointer`).

## Code Review

- Prefer clear over clever. Code is read more than written.
- Flag todos and tech debt with `# TODO(name): reason` so they're searchable.
- Tests are not optional — new behaviour without tests is not done.

## CI / Build

- A failing build or test suite must be fixed before adding new work.
- If a CI step is flaky, flag it — don't re-run until it passes by luck.
- Keep build times fast: avoid unnecessary dependencies.

## Communication

- Surface ambiguity early. Wrong assumptions compound.
- Document decisions that aren't obvious from the code (why, not what).
