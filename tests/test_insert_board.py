"""AN INSERT IS A BOARD: the mailbag, ads and pin-ups ride the same light
table as panels and covers — and their render treats the table's rough as
the pencils."""
import os
from types import SimpleNamespace

from PIL import Image

from schema import Insert

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"


def _pinup(storage, tmp_path):
    ins = Insert(insert_id="test-pinup", issue_id=CARN, series_id=WL, kind="pin-up",
                 name="Test Pinup", description="one glorious drawing",
                 after_scene_number=0, image=None)
    storage.create_object(ins, overwrite=True)
    art = str(tmp_path / "star.png")
    Image.new("RGBA", (300, 300), (250, 210, 40, 255)).save(art)
    ins.figure_images["element/star"] = art
    ins.figure_blocking["element/star"] = {"x": 50, "y": 20, "h": 40, "z": 40}
    storage.update_object(ins)
    return ins


def test_read_board_resolves_inserts(storage, tmp_path):
    from gui.light_table import read_board, is_insert, board_label
    _pinup(storage, tmp_path)
    board = read_board(storage, {"series": WL, "issue": CARN, "insert": "test-pinup"})
    assert board is not None and is_insert(board)
    assert board_label(board) == "the 'Test Pinup' pin-up"


def test_insert_render_treats_the_rough_as_pencils(storage, tmp_path, mock_imaging):
    from agentic.tools.imaging import generate_insert_art_body
    _pinup(storage, tmp_path)
    state = SimpleNamespace(storage=storage, is_dirty=False)
    note = generate_insert_art_body(state, WL, CARN, "test-pinup")
    assert "rendered" in note
    kind, prompt, refs = mock_imaging[-1]
    assert kind == "edit"
    # the composed table rough leads the references — the rough IS the pencils
    assert refs and "rough--" in os.path.basename(refs[0])
    assert "ROUGH" in prompt
    fresh = storage.read_object(cls=Insert, primary_key={
        "series_id": WL, "issue_id": CARN, "insert_id": "test-pinup"})
    assert fresh.image and os.path.exists(fresh.image)


def test_the_flow_can_never_lay_a_full_page():
    """The author's ruling: full pages belong to INSERTS — the panel flow's
    law tops out at the 6×6 square; no shape reaches 6×10."""
    from helpers.stitcher import size_mult, AR, PAGE_UNITS_W, PAGE_UNITS_H
    base = {"square": (2, 2), "landscape": (3, 2), "portrait": (2, 3)}
    for name, (bw, bh) in base.items():
        for m in (1, 2, 3):
            if size_mult(f"{m}x", AR[name]) != m:
                continue
            assert not (bw * m >= PAGE_UNITS_W and bh * m >= PAGE_UNITS_H), \
                f"{name} {m}x would claim a whole page"


def test_located_inserts_take_the_inside_slots(storage):
    """An insert located on the inside-front prints there (indicia stamped
    over it) and leaves the page-turn flow; inside-back likewise."""
    from schema import Insert
    from helpers.binder import reader_sheets

    WLs, C = "wonders-of-the-witchlight", "witchlight-carnival"
    ins = Insert(insert_id="ad-inside-pin", issue_id=C, series_id=WLs,
                 kind="ad", name="Sea-Monkeys Forever", location="inside-back")
    storage.create_object(data=ins, overwrite=True)
    sheets, _missing = reader_sheets(storage, WLs, C)
    labels = [lbl for lbl, _img in sheets]
    assert "inside back cover" in labels, labels
    assert not any("Sea-Monkeys" in lbl for lbl in labels if lbl.startswith("insert")), \
        "a located insert never ALSO prints at a page turn"


def test_the_book_offers_the_page_turn_door():
    """The open book carries the '+ full page here' slip between scenes,
    and the inside-cover ghosts offer both lives (cover art, or an ad/
    mailbag insert living there)."""
    src = open("gui/issue.py").read()
    assert "def insert_door(" in src and "book-turn-door" in src
    assert src.count("insert_door(") >= 4, "the door rides both altitudes"
    assert "_make_insert(k, location=loc)" in src, \
        "inside slots offer the insert kinds"
    lt = open("gui/light_table.py").read()
    assert "inside covers are ad/mailbag surfaces" in lt, \
        "inside covers wear no trade dress"
