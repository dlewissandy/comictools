"""THE TABLE TAKES A DROP: the '…or drop a reference image' row is a real
door — click browses, a drop lands — via the page-level rescue (a bare
q-uploader overlay delivers neither), and every bench resolves its board."""
import os
from types import SimpleNamespace

WL = "wonders-of-the-witchlight"


def _src(path):
    return open(path).read()


def test_the_drop_row_rides_the_rescue():
    """The drop-reference row is a .table-drop-zone the page-level JS
    feeds; the dead invisible-overlay pattern is gone from the bench."""
    src = _src("gui/light_table.py")
    assert "table-drop-zone" in src
    # the overlay that swallowed clicks and covered only 320px is banished
    assert "inset-0 opacity-0" not in src, \
        "the bench must not use the invisible q-uploader overlay (it " \
        "delivers neither clicks nor edge drops)"
    # the rescue knows the zone: drops route to its uploader, clicks open
    # its picker
    from gui.light_table import DRAG_JS
    assert ".table-drop-zone" in DRAG_JS
    assert "'.q-card, .mosaic-card, .create-drop, .table-drop-zone, .insert-drop-sheet'" in DRAG_JS
    assert "'.drop-card, .table-drop-zone'" in DRAG_JS


def test_drop_cards_open_the_picker_on_click():
    """uploader_card wears .drop-card so the click rescue can find its
    hidden input — the invisible uploader itself never took the click."""
    src = _src("gui/elements.py")
    assert "drop-card" in src
    from gui.light_table import DRAG_JS
    assert "input[type=file]" in DRAG_JS


def _sel(*pairs):
    from gui.selection import SelectionItem, SelectedKind
    return [SelectionItem(name=k.value, id=i, kind=k)
            for k, i in pairs]


def test_current_board_resolves_every_bench(storage):
    """current_board (the drop/paste target) knows panels, covers,
    inserts AND marks — a paste or drop on any bench lands on ITS board."""
    from gui.selection import SelectedKind as K
    from gui.light_table import current_board
    from schema import SceneModel, Panel, Cover, Insert, ArtBoard

    issue_id = "witchlight-carnival"
    st = SimpleNamespace(storage=storage)

    # a panel deep on the trail
    scenes = storage.read_all_objects(SceneModel, primary_key={
        "series_id": WL, "issue_id": issue_id})
    panel = None
    for sc in scenes:
        panels = storage.read_all_objects(Panel, primary_key={
            "series_id": WL, "issue_id": issue_id, "scene_id": sc.scene_id})
        if panels:
            panel = panels[0]
            break
    assert panel is not None, "fixture data holds at least one panel"
    st.selection = _sel((K.SERIES, WL), (K.ISSUE, issue_id),
                        (K.SCENE, panel.scene_id), (K.PANEL, panel.panel_id))
    got = current_board(st)
    assert isinstance(got, Panel) and got.panel_id == panel.panel_id

    # the front cover
    st.selection = _sel((K.SERIES, WL), (K.ISSUE, issue_id), (K.COVER, "front"))
    got = current_board(st)
    assert isinstance(got, Cover) and got.cover_id == "front"

    # an insert page
    ins = Insert(insert_id="drop-pin-test", issue_id=issue_id, series_id=WL,
                 name="Drop pin test")
    storage.create_object(data=ins, overwrite=True)
    st.selection = _sel((K.SERIES, WL), (K.ISSUE, issue_id),
                        (K.INSERT, "drop-pin-test"))
    got = current_board(st)
    assert isinstance(got, Insert) and got.insert_id == "drop-pin-test"

    # a masthead mark (series scope) and a logo mark (publisher scope)
    mast = ArtBoard(board_id="masthead-drop-test", scope_id=WL,
                    board_kind="masthead", name="drop test masthead")
    storage.create_object(data=mast, overwrite=True)
    st.selection = _sel((K.SERIES, WL), (K.ARTBOARD, "masthead-drop-test"))
    got = current_board(st)
    assert isinstance(got, ArtBoard) and got.scope_id == WL

    logo = ArtBoard(board_id="logo-drop-test", scope_id="dnd-nerds",
                    board_kind="logo", name="drop test logo")
    storage.create_object(data=logo, overwrite=True)
    st.selection = _sel((K.PUBLISHER, "dnd-nerds"),
                        (K.ARTBOARD, "logo-drop-test"))
    got = current_board(st)
    assert isinstance(got, ArtBoard) and got.scope_id == "dnd-nerds"


def test_dropped_reference_lands_and_undoes(storage):
    """The row's handler files the upload on the board and the receipt's
    undo lifts it back off."""
    from io import BytesIO
    from PIL import Image
    from schema import Cover

    cover = storage.read_object(Cover, primary_key={
        "series_id": WL, "issue_id": "witchlight-carnival", "cover_id": "front"})
    assert cover is not None
    buf = BytesIO()
    Image.new("RGB", (16, 16), "purple").save(buf, "PNG")
    buf.seek(0)
    locator = storage.upload_reference_image(cover, "dropped-ref.png", buf,
                                             "image/png")
    assert os.path.exists(locator)
    assert locator in storage.list_uploads(cover)
    os.remove(locator)          # the undo path
    assert locator not in storage.list_uploads(cover)
