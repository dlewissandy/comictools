"""THE CLONE DOOR: a co-author's house (or the studio's example repo)
arrives straight from its repository — cloned to a staging sibling, proved
to be a comics house, then moved into place and adopted.  A failed or
foreign clone never leaves debris at the destination."""
import json
import os
import subprocess

import pytest

from helpers.house_git import clone_house

_GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@test.local"]


def _scratch_house(root, name="Old Press", inline_prose=True):
    """A committed house repo the way a co-author would publish one —
    pre-ruling inline prose included, so adoption must migrate it."""
    pub_dir = os.path.join(root, "publishers", "old-press")
    os.makedirs(pub_dir)
    # git tracks files, not bare dirs — a real house always ships styles
    style_dir = os.path.join(root, "styles", "plain")
    os.makedirs(style_dir)
    with open(os.path.join(style_dir, "style.json"), "w") as f:
        json.dump({"style_id": "plain", "name": "Plain"}, f)
    desc = "Founded before the ruling." if inline_prose else ""
    with open(os.path.join(pub_dir, "publisher.json"), "w") as f:
        json.dump({"publisher_id": "old-press", "name": name,
                   "description": desc, "logo": None, "image": None}, f, indent=2)
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", *_GIT_ID, "commit", "-q", "-m", "founding"],
                   cwd=root, check=True)
    return root


def test_clone_lands_and_names_the_publisher(tmp_path):
    src = _scratch_house(str(tmp_path / "src"))
    dest = str(tmp_path / "landed" / "old-press-comics")

    assert clone_house(src, dest) == "Old Press"
    assert os.path.isdir(os.path.join(dest, ".git"))
    assert not [d for d in os.listdir(os.path.dirname(dest))
                if ".cloning-" in d], "no staging debris"


def test_a_registered_clone_migrates_on_arrival(tmp_path):
    """register() runs the prose walk — the sidecar marker lives in .git/
    and is never committed, so a fresh clone always converts itself."""
    from storage import registry
    src = _scratch_house(str(tmp_path / "src"))
    dest = str(tmp_path / "landed" / "old-press-comics")
    clone_house(src, dest)

    registry.register(dest)
    pub_dir = os.path.join(dest, "publishers", "old-press")
    assert open(os.path.join(pub_dir, "description.md")).read() == "Founded before the ruling."
    assert json.load(open(os.path.join(pub_dir, "publisher.json")))["description"] == "description.md"
    assert os.path.isfile(os.path.join(dest, ".git", "comic-prose-v2"))


def test_clone_refuses_an_occupied_destination(tmp_path):
    src = _scratch_house(str(tmp_path / "src"))
    dest = str(tmp_path / "occupied")
    os.makedirs(dest)
    with pytest.raises(RuntimeError, match="already exists"):
        clone_house(src, dest)


def test_a_foreign_repo_is_refused_and_leaves_nothing(tmp_path):
    """A repo that isn't a comics house (the not-yet-published example
    stub, someone's dotfiles) is refused plainly and the destination
    stays empty — nothing half-adopted, nothing to clean up."""
    src = str(tmp_path / "stub")
    os.makedirs(src)
    open(os.path.join(src, "README.md"), "w").write("not a house\n")
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=src, check=True)
    subprocess.run(["git", "add", "-A"], cwd=src, check=True)
    subprocess.run(["git", *_GIT_ID, "commit", "-q", "-m", "stub"], cwd=src, check=True)
    dest = str(tmp_path / "landed" / "stub")

    with pytest.raises(RuntimeError, match="isn't a comics house"):
        clone_house(src, dest)
    assert not os.path.exists(dest)
    assert not [d for d in os.listdir(os.path.dirname(dest))
                if ".cloning-" in d], "the staging clone was cleaned up"


def test_an_unreachable_url_fails_fast_with_advice(tmp_path):
    with pytest.raises(RuntimeError, match="couldn't clone"):
        clone_house(str(tmp_path / "no-such-repo"), str(tmp_path / "landed" / "x"))


def test_register_refuses_a_slug_collision(tmp_path):
    """One slug, one house: a second path under the same folder name must
    refuse loudly instead of silently shadowing the first mount."""
    from storage import registry
    a = str(tmp_path / "one" / "same-name-comics")
    b = str(tmp_path / "two" / "same-name-comics")
    for p in (a, b):
        os.makedirs(p)
    registry.register(a)
    with pytest.raises(ValueError, match="already hangs on the wall"):
        registry.register(b)
    assert registry.register(a) == "same-name-comics", "re-adopting the same path stays idempotent"
