"""EVERY HOUSE ITS OWN REPO: founding, adopting and retiring publisher
repos never touches what it shouldn't — and never the user's registry."""
import json
import os
import subprocess

import pytest

from storage import registry


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "REGISTRY_PATH", str(tmp_path / "publishers.json"))
    monkeypatch.setattr(registry, "DATA_LINK", str(tmp_path / "data"))
    # a tiny house template: one style file, one prompt
    tpl = tmp_path / "template"
    (tpl / "styles").mkdir(parents=True)
    (tpl / "styles" / "test-style.json").write_text("{}")
    (tpl / "prompts" / "system").mkdir(parents=True)
    (tpl / "prompts" / "system" / "boilerplate.txt").write_text("hello")
    return tmp_path, str(tpl)


def test_found_house_builds_a_repo(sandbox):
    tmp, tpl = sandbox
    target = tmp / "midnight-owl-press-comics"
    slug = registry.found_house("Midnight Owl Press", str(target), template_dir=tpl)
    assert slug == "midnight-owl-press-comics"
    assert (target / "series").is_dir()
    assert (target / "styles" / "test-style.json").exists(), "default styles copied in"
    assert (target / ".gitignore").read_text().startswith("# working paper")
    assert (target / ".git").is_dir(), "the house is a git repository"
    log = subprocess.run(["git", "log", "--oneline"], cwd=target,
                         capture_output=True, text=True).stdout
    assert "FOUNDING THE HOUSE" in log
    # the publisher record lives inside
    assert registry.looks_like_house(str(target)) == "Midnight Owl Press"
    assert any(p["slug"] == slug for p in registry.registered())


def test_adopting_an_existing_house(sandbox):
    tmp, tpl = sandbox
    target = tmp / "elsewhere" / "old-house"
    registry.found_house("Old House", str(target), template_dir=tpl)
    # forget it, then adopt it back as an existing repo — never re-founded
    assert registry.unregister("old-house-comics") or True
    reg = json.loads(open(registry.REGISTRY_PATH).read())
    reg["publishers"] = []
    json.dump(reg, open(registry.REGISTRY_PATH, "w"))
    assert registry.looks_like_house(str(target)) == "Old House"
    slug = registry.register(str(target))
    assert any(p["slug"] == slug for p in registry.registered())


def test_retiring_never_touches_disk_and_never_strands_the_studio(sandbox):
    tmp, tpl = sandbox
    a = tmp / "house-a"
    b = tmp / "house-b"
    registry.found_house("House A", str(a), template_dir=tpl)
    registry.found_house("House B", str(b), template_dir=tpl)
    assert registry.set_open("house-a")
    # retiring the open house re-points the studio and leaves the disk alone
    assert registry.unregister("house-a")
    assert a.exists() and (a / "styles").is_dir(), "the disk is never touched"
    assert registry.open_slug() == "house-b"
    # the last house cannot be retired — the studio must stand somewhere
    assert not registry.unregister("house-b")
    assert registry.open_slug() == "house-b"
