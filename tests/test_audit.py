"""Tests for the deterministic guardrail auditor."""

from __future__ import annotations

from wingman import audit


def test_parse_frontmatter_scalars():
    fm, body = audit.parse_frontmatter(
        '---\nname: demo\ndescription: "Use when testing."\n---\n\n# Demo\nbody\n'
    )
    assert fm["name"] == "demo"
    assert fm["description"] == "Use when testing."
    assert body.startswith("# Demo")


def test_parse_frontmatter_none():
    fm, body = audit.parse_frontmatter("# No frontmatter\nbody\n")
    assert fm == {}
    assert "No frontmatter" in body


def test_parse_frontmatter_folded_block_scalar():
    text = (
        "---\n"
        "name: query\n"
        "description: >\n"
        "  Run SQL queries against DuckDB.\n"
        "  Accepts raw SQL or questions.\n"
        "argument-hint: <SQL>\n"
        "---\n\nbody\n"
    )
    fm, _ = audit.parse_frontmatter(text)
    assert fm["name"] == "query"
    expected = "Run SQL queries against DuckDB. Accepts raw SQL or questions."
    assert fm["description"] == expected
    assert fm["argument-hint"] == "<SQL>"


def test_parse_frontmatter_literal_block_scalar():
    text = "---\ndescription: |\n  line one\n  line two\n---\n\nbody\n"
    fm, _ = audit.parse_frontmatter(text)
    assert fm["description"] == "line one\nline two"


def test_parse_frontmatter_implicit_plain_multiline():
    text = (
        "---\n"
        "name: dagster-expert\n"
        "description:\n"
        "  Expert guidance for Dagster.\n"
        "  ALWAYS use before data pipeline tasks.\n"
        "references:\n"
        "  - dagster-core\n"
        "  - cli-patterns\n"
        "---\n\nbody\n"
    )
    fm, _ = audit.parse_frontmatter(text)
    assert fm["name"] == "dagster-expert"
    expected = "Expert guidance for Dagster. ALWAYS use before data pipeline tasks."
    assert fm["description"] == expected
    assert fm["references"] == ""  # nested list is skipped, not folded


def _write_skill(repo, name, text):
    folder = repo / ".github" / "skills" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(text)
    return folder / "SKILL.md"


def test_audit_good_skill_is_clean(repo):
    path = _write_skill(
        repo,
        "demo",
        "---\n"
        "name: demo\n"
        'description: "A demo skill. Use when testing wingman auditing behaviour."\n'
        "---\n\n"
        "# Demo\n\n" + ("usable instruction content. " * 10) + "\n",
    )
    findings = audit.audit_skill(path)
    assert findings == []


def test_audit_bad_skill_flags_name_and_description(repo):
    path = _write_skill(
        repo,
        "demo",
        "---\nname: wrong\n---\n\nshort\n",
    )
    findings = audit.audit_skill(path)
    levels = {f.level for f in findings}
    messages = " ".join(f.message for f in findings)
    assert audit.ERROR in levels
    assert "name" in messages
    assert "description" in messages


def test_audit_all_discovers_and_returns_findings(repo):
    _write_skill(repo, "demo", "---\nname: wrong\n---\n\nx\n")
    findings = audit.audit_all()
    assert any(f.level == audit.ERROR for f in findings)


def test_format_findings_includes_level(repo):
    path = _write_skill(repo, "demo", "---\nname: wrong\n---\n\nx\n")
    lines = audit.format_findings(audit.audit_skill(path))
    assert any("[error]" in line for line in lines)
