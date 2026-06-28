---
description: "Review code for correctness, clarity, and conventions. Use on a file, function, or diff."
agent: agent
tools: [read, search]
---

Review the provided code and give structured feedback across these dimensions:

**Correctness** — bugs, edge cases, error handling gaps  
**Clarity** — naming, complexity, readability  
**Conventions** — does it follow project patterns (see .github/copilot-instructions.md)  
**Tests** — missing coverage for the changed behaviour  
**Security** — any obvious OWASP Top 10 concerns  

Format as a prioritised list: `[blocker]`, `[suggestion]`, `[nit]`.  
End with a one-line summary verdict.
