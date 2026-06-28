"""Tests for the skill manager: manifest roundtrip and add/update/remove."""

from __future__ import annotations

from wingman import skills


def test_manifest_roundtrip(repo):
    src = {
        "demo": skills.SkillSource(
            name="demo", repo="https://example.com/r.git", path="demo", ref="main"
        )
    }
    skills.write_manifest(src)
    back = skills.read_manifest()
    assert back == src


def test_manifest_without_ref(repo):
    src = {"demo": skills.SkillSource(name="demo", repo="r", path="demo")}
    skills.write_manifest(src)
    back = skills.read_manifest()
    assert back["demo"].ref is None


def test_add_fetches_and_records(repo, skill_source):
    url, ref = skill_source
    source, commit = skills.add(url, path="demo", ref=ref)
    assert source.name == "demo"
    assert commit
    installed = repo / skills.COPILOT_SKILLS_DIR / "demo" / "SKILL.md"
    assert installed.is_file()
    ref_note = repo / skills.COPILOT_SKILLS_DIR / "demo" / "references" / "note.md"
    assert ref_note.is_file()
    assert "demo" in skills.read_manifest()
    assert skills.read_lock()["demo"]["commit"] == commit


def test_list_skills_reports_installed(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref)
    rows = skills.list_skills()
    assert len(rows) == 1
    assert rows[0]["name"] == "demo"
    assert rows[0]["installed"] is True


def test_update_returns_commits(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref)
    results = skills.update("demo")
    assert results[0][0] == "demo"


def test_remove_deletes_skill(repo, skill_source):
    url, ref = skill_source
    skills.add(url, path="demo", ref=ref)
    skills.remove("demo")
    assert "demo" not in skills.read_manifest()
    assert not (repo / skills.COPILOT_SKILLS_DIR / "demo").exists()


def test_add_by_url_requires_path(repo):
    try:
        skills.add("https://example.com/r.git")
    except skills.SkillError as e:
        assert "path" in str(e)
    else:
        raise AssertionError("expected SkillError")


def test_add_set_installs_all_members(repo, skill_set_source, monkeypatch):
    url, ref = skill_set_source
    monkeypatch.setattr(
        skills,
        "resolve_set",
        lambda name: skills.SkillSet(name="demo-set", repo=url, path="skills", ref=ref),
    )
    installed = skills.add_set("demo-set")
    assert sorted(s.name for s, _ in installed) == ["alpha", "beta", "gamma"]
    for m in ("alpha", "beta", "gamma"):
        assert (repo / skills.COPILOT_SKILLS_DIR / m / "SKILL.md").is_file()
    manifest = skills.read_manifest()
    assert set(manifest) == {"alpha", "beta", "gamma"}
    # members are recorded individually so update/remove work per-skill
    assert manifest["beta"].path == "skills/beta"
    skills.remove("beta")
    assert "beta" not in skills.read_manifest()


def test_add_set_respects_exclude(repo, skill_set_source, monkeypatch):
    url, ref = skill_set_source
    monkeypatch.setattr(
        skills,
        "resolve_set",
        lambda name: skills.SkillSet(
            name="demo-set", repo=url, path="skills", ref=ref, exclude=["gamma"]
        ),
    )
    installed = skills.add_set("demo-set")
    assert sorted(s.name for s, _ in installed) == ["alpha", "beta"]
    assert not (repo / skills.COPILOT_SKILLS_DIR / "gamma").exists()


def test_add_set_explicit_members(repo, skill_set_source, monkeypatch):
    # Skills live at unrelated subpaths; an explicit member list picks them out.
    url, ref = skill_set_source
    monkeypatch.setattr(
        skills,
        "resolve_set",
        lambda name: skills.SkillSet(
            name="demo-set",
            repo=url,
            ref=ref,
            members=[
                skills.SkillSetMember(name="alpha", path="skills/alpha"),
                skills.SkillSetMember(name="gamma", path="skills/gamma"),
            ],
        ),
    )
    installed = skills.add_set("demo-set")
    assert sorted(s.name for s, _ in installed) == ["alpha", "gamma"]
    assert not (repo / skills.COPILOT_SKILLS_DIR / "beta").exists()
    manifest = skills.read_manifest()
    assert manifest["gamma"].path == "skills/gamma"
    # recorded path resolves for update/remove
    assert skills.update("alpha")[0][0] == "alpha"


def test_add_set_root_path_normalizes(repo, skill_source, monkeypatch):
    # skill_source repo holds 'demo/SKILL.md' at its root, so path="." finds it.
    url, ref = skill_source
    monkeypatch.setattr(
        skills,
        "resolve_set",
        lambda name: skills.SkillSet(name="root-set", repo=url, path=".", ref=ref),
    )
    installed = skills.add_set("root-set")
    assert [s.name for s, _ in installed] == ["demo"]
    # path is normalized ('demo', not './demo') so update/remove resolve correctly
    assert skills.read_manifest()["demo"].path == "demo"
    assert skills.update("demo")[0][0] == "demo"
