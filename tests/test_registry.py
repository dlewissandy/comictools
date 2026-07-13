"""MOUNT ALL THE HOUSES: founding, adopting and retiring publisher repos
never touches what it shouldn't — and every registered house is mounted
at data/<slug> simultaneously (no open-house switching to foul up)."""
import json
import os
import subprocess

import pytest

from storage import registry


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "REGISTRY_PATH", str(tmp_path / "publishers.json"))
    monkeypatch.setattr(registry, "DATA_DIR", str(tmp_path / "data"))
    # a tiny house template: one style file, one prompt
    tpl = tmp_path / "template"
    (tpl / "styles" / "test-style").mkdir(parents=True)
    (tpl / "styles" / "test-style" / "style.json").write_text("{}")
    (tpl / "prompts" / "system").mkdir(parents=True)
    (tpl / "prompts" / "system" / "boilerplate.txt").write_text("hello")
    return tmp_path, str(tpl)


def test_found_house_builds_and_mounts_a_repo(sandbox):
    tmp, tpl = sandbox
    target = tmp / "midnight-owl-press-comics"
    registry.mount_all()
    slug = registry.found_house("Midnight Owl Press", str(target), template_dir=tpl)
    assert slug == "midnight-owl-press-comics"
    assert (target / "series").is_dir()
    assert (target / "styles" / "test-style" / "style.json").exists(), "default styles copied in"
    assert (target / ".gitignore").read_text().startswith("# working paper")
    assert (target / ".git").is_dir(), "the house is a git repository"
    log = subprocess.run(["git", "log", "--oneline"], cwd=target,
                         capture_output=True, text=True).stdout
    assert "FOUNDING THE HOUSE" in log
    # the publisher record lives inside
    assert registry.looks_like_house(str(target)) == "Midnight Owl Press"
    assert any(p["slug"] == slug for p in registry.registered())
    # THE MOUNT: founding puts the house on the rack immediately
    at = registry.mount_path(slug)
    assert os.path.islink(at) and os.path.realpath(at) == os.path.realpath(str(target))


def test_adopting_an_existing_house(sandbox):
    tmp, tpl = sandbox
    target = tmp / "elsewhere" / "old-house"
    registry.mount_all()
    registry.found_house("Old House", str(target), template_dir=tpl)
    # forget it, then adopt it back as an existing repo — never re-founded
    assert registry.unregister("old-house") or True
    reg = json.loads(open(registry.REGISTRY_PATH).read())
    reg["publishers"] = []
    json.dump(reg, open(registry.REGISTRY_PATH, "w"))
    assert registry.looks_like_house(str(target)) == "Old House"
    slug = registry.register(str(target))
    assert any(p["slug"] == slug for p in registry.registered())
    assert os.path.islink(registry.mount_path(slug)), "adoption mounts the house"


def test_retiring_unmounts_but_never_touches_disk(sandbox):
    tmp, tpl = sandbox
    a = tmp / "house-a"
    b = tmp / "house-b"
    registry.mount_all()
    registry.found_house("House A", str(a), template_dir=tpl)
    registry.found_house("House B", str(b), template_dir=tpl)
    assert os.path.islink(registry.mount_path("house-a"))
    assert os.path.islink(registry.mount_path("house-b"))
    # retiring removes the mount and leaves the disk alone
    assert registry.unregister("house-a")
    assert a.exists() and (a / "styles").is_dir(), "the disk is never touched"
    assert not os.path.exists(registry.mount_path("house-a"))
    assert os.path.islink(registry.mount_path("house-b")), "the other house stays mounted"
    # an empty rack is legal — the wall renders its founding card
    assert registry.unregister("house-b")
    assert registry.registered() == []
    assert b.exists()


def test_mount_all_migrates_the_legacy_symlink_and_prunes_strays(sandbox):
    tmp, tpl = sandbox
    home = tmp / "solo-house"
    (home / "series").mkdir(parents=True)
    # the OLD layout: data itself is a symlink to the one open house
    os.symlink(str(home), registry.DATA_DIR)
    registry.register(str(home), slug="solo-house")
    houses = registry.mount_all()
    assert [h["slug"] for h in houses] == ["solo-house"]
    assert os.path.isdir(registry.DATA_DIR) and not os.path.islink(registry.DATA_DIR)
    assert os.path.islink(registry.mount_path("solo-house"))
    # a stray symlink is pruned; a REAL directory is never touched
    os.symlink(str(tpl), os.path.join(registry.DATA_DIR, "stray"))
    real = os.path.join(registry.DATA_DIR, "hands-off")
    os.makedirs(real)
    registry.mount_all()
    assert not os.path.exists(os.path.join(registry.DATA_DIR, "stray"))
    assert os.path.isdir(real), "mount_all never deletes a real directory"
    # the retired open-house key is dropped on the next save
    reg = json.loads(open(registry.REGISTRY_PATH).read())
    assert "open" not in reg


def test_house_of_resolvers(sandbox):
    tmp, tpl = sandbox
    registry.mount_all()
    a = tmp / "alpha-comics"
    registry.found_house("Alpha", str(a), template_dir=tpl)
    (a / "series" / "the-strip").mkdir(parents=True)
    from schema.publisher import Publisher
    pid = registry.storage_for("alpha-comics").read_all_objects(Publisher)[0].publisher_id
    assert registry.house_of_publisher(pid) == "alpha-comics"
    assert registry.house_of_series("the-strip") == "alpha-comics"
    assert registry.house_of_style("test-style") == "alpha-comics"
    assert registry.house_of_series("nowhere") is None


def test_locators_translate_at_the_storage_boundary(sandbox):
    """Repos stay self-contained: on disk 'data/…', in the studio
    'data/<slug>/…' — and a write puts the repo form back."""
    from storage.local import LocalStorage
    from schema.publisher import Publisher

    tmp, _tpl = sandbox
    repo = tmp / "repo"
    (repo / "publishers" / "solo").mkdir(parents=True)
    (repo / "publishers" / "solo" / "publisher.json").write_text(json.dumps({
        "publisher_id": "solo", "name": "Solo",
        "description": None, "logo": None,
        "image": "data/publishers/solo/logo.png"}))
    os.makedirs(registry.DATA_DIR, exist_ok=True)
    mount = registry.mount_path("repo")
    os.symlink(str(repo), mount)

    st = LocalStorage(base_path=mount)
    pub = st.read_object(Publisher, primary_key={"publisher_id": "solo"})
    assert pub.image == os.path.join(mount, "publishers", "solo", "logo.png"), \
        "read translates the locator into the mount"
    pub.name = "Solo Act"
    st.update_object(pub)
    raw = json.loads((repo / "publishers" / "solo" / "publisher.json").read_text())
    assert raw["image"] == "data/publishers/solo/logo.png", \
        "the repo keeps its own self-contained locator"
    assert raw["name"] == "Solo Act"
    # the identity case: a plain 'data' root never rewrites
    plain = LocalStorage(base_path="data")
    assert plain._rewrite_locators({"x": "data/series/a.png"}, outbound=False) \
        == {"x": "data/series/a.png"}


def test_cross_house_style_edits_stay_home(sandbox):
    """Default styles share ids across houses — the trail's publisher must
    pick the repo that gets written."""
    from gui.selection import house_for_selection, SelectionItem, SelectedKind

    tmp, tpl = sandbox
    registry.mount_all()
    registry.found_house("Alpha", str(tmp / "alpha-comics"), template_dir=tpl)
    registry.found_house("Beta", str(tmp / "beta-comics"), template_dir=tpl)
    from schema.publisher import Publisher
    beta_pid = registry.storage_for("beta-comics").read_all_objects(Publisher)[0].publisher_id

    trail = [SelectionItem(name="Publishers", id=None, kind=SelectedKind.ALL_PUBLISHERS),
             SelectionItem(name="Beta", id=beta_pid, kind=SelectedKind.PUBLISHER),
             SelectionItem(name="Test", id="test-style", kind=SelectedKind.STYLE)]
    assert house_for_selection(trail) == "beta-comics", \
        "the publisher in the trail names the house, not the shared style id"
    bare = [SelectionItem(name="Test", id="test-style", kind=SelectedKind.STYLE)]
    assert house_for_selection(bare) in ("alpha-comics", "beta-comics"), \
        "a bare style id still finds a holder (first mounted hit)"


def test_founding_falls_back_to_the_app_bundle(sandbox, tmp_path, monkeypatch):
    """A FRESH MACHINE: no ~/.comic-studio template, no sister house — the
    app's own bundled template dresses the first house, never styleless."""
    tmp, _tpl = sandbox
    monkeypatch.setattr(registry, "HOUSE_TEMPLATE", str(tmp_path / "no-such-template"))
    target = tmp / "first-house-comics"
    registry.mount_all()
    slug = registry.found_house("First House", str(target))
    assert slug
    styles = list((target / "styles").glob("*/style.json"))
    assert styles, "the bundled template dressed the house"
    import json as _json
    d = _json.load(open(styles[0]))
    assert d.get("image") in ({}, None), "no dangling art paths in a fresh house"
    assert (target / "prompts").is_dir(), "prompts ride along"


def test_founding_refuses_loudly_without_any_styles_source(sandbox, tmp_path, monkeypatch):
    tmp, _tpl = sandbox
    monkeypatch.setattr(registry, "HOUSE_TEMPLATE", str(tmp_path / "no-such-template"))
    # blind the app bundle too by pointing __file__-derived path away
    real = os.path.isdir
    def fake_isdir(p):
        if os.path.join("templates", "house") in str(p):
            return False
        return real(p)
    monkeypatch.setattr(os.path, "isdir", fake_isdir)
    with pytest.raises(RuntimeError, match="cannot found a house without its styles"):
        registry.found_house("Styleless House", str(tmp / "styleless-comics"))


def test_founding_survives_a_missing_git_identity(sandbox, tmp_path, monkeypatch):
    """A first-time author has no user.name/user.email — the founding commit
    falls back to a studio identity instead of failing raw."""
    tmp, tpl = sandbox
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "empty-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "empty-gitconfig2"))
    target = tmp / "anon-house-comics"
    registry.mount_all()
    slug = registry.found_house("Anon House", str(target), template_dir=tpl)
    assert slug
    log = subprocess.run(["git", "log", "--oneline"], cwd=target,
                         capture_output=True, text=True)
    assert "FOUNDING THE HOUSE" in log.stdout, "the founding commit landed"
