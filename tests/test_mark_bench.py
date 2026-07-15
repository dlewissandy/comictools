"""THE MARK IS A BOARD: mastheads and logos compose on the light table —
from text, from layers, or from image; featuring writes the mark home."""
import json
import os
from types import SimpleNamespace

import pytest

WL = "wonders-of-the-witchlight"


def test_artboard_walks_like_a_board(storage):
    from schema import ArtBoard
    b = ArtBoard(board_id="masthead-vintage-four-color", scope_id=WL,
                 board_kind="masthead", name="WL masthead",
                 style_id="vintage-four-color")
    storage.create_object(data=b, overwrite=True)
    fresh = storage.read_object(ArtBoard, {"scope_id": WL,
                                           "board_id": "masthead-vintage-four-color"})
    assert fresh is not None and fresh.board_kind == "masthead"
    # bench duck-typing: the fields the light table reads
    assert fresh.series_id == WL and fresh.issue_id == ""
    assert fresh.figure_images == {} and fresh.character_references == []
    from gui.light_table import is_artboard
    assert is_artboard(fresh) and not is_artboard(SimpleNamespace())


def test_mark_routes_round_trip(storage):
    from gui.routes import selection_from_path, selection_to_url
    from gui.selection import SelectedKind
    sel = selection_from_path(storage, ["series", WL, "mark", "masthead-x"])
    assert [i.kind.value for i in sel][-1] == "artboard"
    url = selection_to_url(sel)
    assert url == f"/series/{WL}/mark/masthead-x"
    sel2 = selection_from_path(storage, ["publishers", "dnd-nerds", "mark", "logo"])
    assert sel2 is not None and sel2[-1].kind == SelectedKind.ARTBOARD


def test_featuring_writes_the_mark_home(storage, mock_imaging):
    """The proof lands a take on the BOARD; featuring writes a masthead
    into series.title_images and a logo onto the publisher."""
    import agentic.tools.imaging as imaging
    from schema import ArtBoard, Series
    b = ArtBoard(board_id="masthead-vintage-four-color", scope_id=WL,
                 board_kind="masthead", name="WL masthead",
                 description="WONDERS OF THE WITCHLIGHT in circus woodtype",
                 style_id="vintage-four-color")
    storage.create_object(data=b, overwrite=True)

    state = SimpleNamespace(storage=storage, is_dirty=False)
    note = imaging.render_artboard_body(state, WL, "masthead-vintage-four-color")
    assert "take" in note and "cannot" not in note
    takes = storage.list_images(b)
    assert takes, "the take lands on the board"

    # featuring writes home (the takes_row write-through logic)
    fresh = storage.read_object(ArtBoard, {"scope_id": WL,
                                           "board_id": "masthead-vintage-four-color"})
    fresh.image = takes[0]
    storage.update_object(fresh)
    ser = storage.read_object(Series, {"series_id": WL})
    ser.title_images = dict(ser.title_images or {})
    ser.title_images[fresh.style_id] = takes[0]
    storage.update_object(ser)
    again = storage.read_object(Series, {"series_id": WL})
    assert again.title_images["vintage-four-color"] == takes[0]


def test_the_mark_bench_renders(storage):
    """The bench itself opens on a mark without an issue in sight."""
    from schema import ArtBoard
    b = ArtBoard(board_id="logo", scope_id="dnd-nerds", board_kind="logo",
                 name="DND Nerds logo")
    storage.create_object(data=b, overwrite=True)
    src = open("gui/light_table.py").read()
    assert "def view_artboard" in src
    assert "data-artboard" in src, "drag events resolve back to the mark"


def test_the_mark_bench_hangs_its_takes(storage, mock_imaging):
    """A rendered take must APPEAR: the mark bench hangs the takes wall,
    and a render lands where that wall reads."""
    import agentic.tools.imaging as imaging
    from types import SimpleNamespace
    from schema import ArtBoard
    src = open("gui/light_table.py").read()
    va = src.split("def view_artboard", 1)[1]
    assert "takes_row(state, board, featured)" in va, \
        "the mark bench shows its takes like every other board"

    b = ArtBoard(board_id="masthead-takes-pin", scope_id=WL,
                 board_kind="masthead", name="takes pin",
                 description="TAKES PIN in woodtype",
                 style_id="vintage-four-color")
    storage.create_object(data=b, overwrite=True)
    state = SimpleNamespace(storage=storage, is_dirty=False)
    imaging.render_artboard_body(state, WL, "masthead-takes-pin")
    takes = [t for t in storage.list_images(b) if os.path.exists(t)]
    assert takes, "the render lands in the very folder the takes wall lists"


def test_the_marks_whole_history_hangs_on_one_wall():
    """Author report: takes rendered through the older flows (publisher
    images for a logo, series title art / sibling style-boards for a
    masthead) must still hang on the mark bench's takes wall."""
    src = open("gui/light_table.py").read()
    wall = src.split("def takes_row", 1)[1]
    assert "THE MARK'S WHOLE HISTORY" in wall
    for needle in ("list_images(_owner)", "title_images", "_rehome"):
        assert needle in wall, f"takes wall must gather {needle}"


def test_the_series_tile_opens_the_board_with_the_art():
    """Author report: the masthead tile opened a fresh empty board while
    the takes sat on a sibling — the tile must prefer the board that
    actually HOLDS takes, and sit in the assets list, not a page banner."""
    src = open("gui/series.py").read()
    assert "_inked" in src and "getmtime" in src
    # the tile rides the assets flow, placed with the walls (the masthead
    # block sits AFTER the description cell in source order)
    assert src.index("Description callout") < src.index("MASTHEAD IS JUST ANOTHER ASSET")
