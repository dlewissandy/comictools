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
