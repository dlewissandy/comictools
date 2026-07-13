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


def test_from_image_keeps_exemplar_and_carries_notes(monkeypatch):
    posts = _capture(monkeypatch)
    ca._create_from_image(_State(), "character", "Vera", "/data/up/x.png", "older, grey hair")
    # routes to the exemplar-keeping tool with the image path and notes
    assert "create_variant_from_image" in posts[0] and "/data/up/x.png" in posts[0]
    assert "older, grey hair" in posts[0]
    for kind, tool in (("setting", "create_setting_from_image"),
                       ("prop", "create_prop_from_image"),
                       ("outfit", "create_outfit_from_image")):
        posts.clear()
        ca._create_from_image(_State(), kind, "X", "/data/up/y.png", "")
        assert tool in posts[0] and "EXEMPLAR" in posts[0] and "/data/up/y.png" in posts[0]


def test_copy_derives_characters_and_copies_the_rest(monkeypatch):
    posts = _capture(monkeypatch)
    ca._create_by_copy(_State(), "character", "vera", "Vera Kell", "Nora Kell", "her sister")
    ca._create_by_copy(_State(), "outfit", "trench", "Trench", "Raincoat", "yellow")
    assert "Derive a new character named 'Nora Kell' from 'Vera Kell'" in posts[0]
    assert "her sister" in posts[0]
    assert "copying the outfit 'Trench'" in posts[1] and "Raincoat" in posts[1]


def test_kinds_are_complete():
    assert set(ca._KIND) == {"character", "setting", "prop", "outfit"}


def test_asset_drop_saves_to_the_house_and_posts_create(storage, monkeypatch, tmp_path):
    """A dropped image lands in the series' house uploads and starts a
    create-from-image — even when the series lives in a house the root
    storage can't see (mount-all)."""
    import base64, os
    from PIL import Image
    posts = []
    monkeypatch.setattr(ca, "post_user_message", lambda state, msg: posts.append(msg))
    # a tiny png as a data URL
    p = tmp_path / "x.png"; Image.new("RGB", (8, 8), (1, 2, 3)).save(p)
    b64 = base64.b64encode(p.read_bytes()).decode()

    class _State:
        def __init__(self, storage): self.storage = storage
    st = _State(storage)
    # storage fixture is the house storage itself (base_path = the house)
    from schema import Series
    ser = storage.read_all_objects(Series)[0]
    ca.handle_asset_drop(st, {"kind": "setting", "series": ser.series_id,
                              "character": "", "name": "Rainy Alley.png",
                              "data": f"data:image/png;base64,{b64}"})
    up = os.path.join(str(storage.base_path), "series", ser.series_id, "uploads")
    assert os.path.isdir(up) and os.listdir(up), "the image landed in the house uploads"
    assert posts and "setting" in posts[0].lower() and "reference image" in posts[0].lower()
