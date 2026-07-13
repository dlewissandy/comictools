"""THE CREATE DIALOG: three paths for every asset, and the look composer —
each hands the coauthor one well-formed instruction."""
from types import SimpleNamespace

import gui.create_asset as ca


class _State:
    def __init__(self):
        self.posted = []


def _capture(monkeypatch):
    posts = []
    monkeypatch.setattr(ca, "post_user_message", lambda state, msg: posts.append(msg))
    return posts


def test_from_scratch_speaks_each_kind(monkeypatch):
    posts = _capture(monkeypatch)
    st = _State()
    ca._create_from_scratch(st, "character", "Vera Kell", "a tired PI")
    ca._create_from_scratch(st, "setting", "The Office", "rain-soaked")
    ca._create_from_scratch(st, "prop", "Brass Key", "worn")
    ca._create_from_scratch(st, "outfit", "Trench Coat", "grey wool")
    assert "character named 'Vera Kell'" in posts[0] and "BASE look" in posts[0]
    assert "setting named 'The Office'" in posts[1] and "master background" in posts[1]
    assert "prop named 'Brass Key'" in posts[2]
    assert "outfit" in posts[3] and "Trench Coat" in posts[3]


def test_from_image_carries_the_reference_and_notes(monkeypatch):
    posts = _capture(monkeypatch)
    ca._create_from_image(_State(), "character", "Vera", "/data/up/x.png", "older, grey hair")
    assert "![reference](/data/up/x.png)" in posts[0]
    assert "older, grey hair" in posts[0]
    assert "BASE identity" in posts[0]


def test_copy_derives_characters_and_copies_the_rest(monkeypatch):
    posts = _capture(monkeypatch)
    ca._create_by_copy(_State(), "character", "vera", "Vera Kell", "Nora Kell", "her sister")
    ca._create_by_copy(_State(), "outfit", "trench", "Trench", "Raincoat", "yellow")
    assert "Derive a new character named 'Nora Kell' from 'Vera Kell'" in posts[0]
    assert "her sister" in posts[0]
    assert "copying the outfit 'Trench'" in posts[1] and "Raincoat" in posts[1]


def test_kinds_are_complete():
    assert set(ca._KIND) == {"character", "setting", "prop", "outfit"}
