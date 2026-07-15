"""THE HOUSE SYNCS LIKE A STUDIO: one glyph commits with a slate message
that names what was inked, pulls, pushes — and speaks plainly without a
remote."""
import os
import subprocess

import pytest


@pytest.fixture()
def house_repo(tmp_path):
    repo = tmp_path / "test-house-comics"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    (repo / "publisher.json").write_text("{}")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "founding"], check=True)
    return str(repo)


def _seed_changes(repo):
    for rel in [
        "series/joey/issues/one/scenes/s1/panels/p1/panel.json",
        "series/joey/issues/one/scenes/s1/panels/p1/images/take.png",
        "series/joey/issues/one/scenes/s1/panels/p2/panel.json",
        "series/joey/issues/one/covers/front/cover.json",
        "series/joey/outfits/cloak/outfit.json",
        "artboards/joey/masthead-x/artboard.json",
    ]:
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("{}")


def test_the_slate_names_what_was_inked(house_repo):
    from helpers.house_git import nice_commit_message
    _seed_changes(house_repo)
    msg = nice_commit_message(house_repo)
    head = msg.splitlines()[0]
    assert head.startswith("STUDIO SYNC:")
    assert "2 panels" in head, f"two panels changed (files fold into objects): {head}"
    assert "1 cover" in head
    assert "1 outfit" in head
    assert "1 mark" in head
    assert "joey" in head, "the slate names the series"


def test_sync_commits_and_speaks_without_a_remote(house_repo):
    from helpers.house_git import sync_house, repo_state
    _seed_changes(house_repo)
    assert repo_state(house_repo, ttl=0)["dirty"] > 0
    receipts = sync_house(house_repo)
    assert any(r.startswith("🗃 committed") for r in receipts), receipts
    assert any("no remote" in r for r in receipts), receipts
    # the commit actually landed with the slate message
    log = subprocess.run(["git", "-C", house_repo, "log", "-1", "--format=%s"],
                         capture_output=True, text=True).stdout.strip()
    assert log.startswith("STUDIO SYNC:")
    assert repo_state(house_repo, ttl=0)["dirty"] == 0
    # a clean re-sync stays honest
    receipts = sync_house(house_repo)
    assert any("nothing new" in r for r in receipts)


def test_the_wall_wears_the_sync_glyph():
    src = open("gui/home.py").read()
    assert "THE SYNC GLYPH" in src
    assert "sync_house" in src and "repo_state" in src
    assert "click.stop" in src.split("THE SYNC GLYPH", 1)[1][:4000], \
        "the sync click must not open the house room"


def test_the_editor_carries_the_wall_everywhere(storage):
    """Author report ('dumber than dirt'): the Editor was name-blind
    outside the lobby.  The brief now carries the wall roster, the
    legible trail, and the object in hand from ANY room."""
    import sys as _sys
    from types import SimpleNamespace
    from gui.selection import SelectionItem, SelectedKind as K
    import agentic.instructions  # noqa: F401 — the package shadows the name
    ins = _sys.modules["agentic.instructions"]
    ins._ROSTER_CACHE["t"] = 0.0
    from schema import SceneModel, Panel
    WL, C = "wonders-of-the-witchlight", "witchlight-carnival"
    sc = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": C})[0]
    p = storage.read_all_objects(Panel, {"series_id": WL, "issue_id": C,
                                         "scene_id": sc.scene_id})[0]
    state = SimpleNamespace(storage=storage, _storage=storage, selection=[
        SelectionItem(name="Series", id=None, kind=K.ALL_SERIES),
        SelectionItem(name="WL", id=WL, kind=K.SERIES),
        SelectionItem(name="C", id=C, kind=K.ISSUE),
        SelectionItem(name=sc.name, id=sc.scene_id, kind=K.SCENE),
        SelectionItem(name=p.name, id=p.panel_id, kind=K.PANEL)])
    out = ins.instructions(SimpleNamespace(context=state),
                           SimpleNamespace(name="the Editor"))
    ins._ROSTER_CACHE["t"] = 0.0     # never leak fixture data across tests
    assert "THE STUDIO WALL" in out, "the roster rides every room"
    assert "WHERE THE AUTHOR STANDS" in out, "the trail prints legibly"
    assert p.panel_id in out.split("WHERE THE AUTHOR STANDS", 1)[1], \
        "the trail carries the bench's ids"
    assert p.panel_id in out.split("OBJECT IN HAND", 1)[-1][:600], \
        "the object in hand is the bench itself"
