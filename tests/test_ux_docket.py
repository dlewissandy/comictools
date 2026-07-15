"""EVERY BUTTON HAS A UX — the standing gates from the prime-time audit.
Pins the four defect CLASSES the docket found so none can recur:
lost events (B1), stale clobbers (B2/B4), dropped fields (B3/B6), and
undefined names (B5)."""
import re
import subprocess
import sys
from types import SimpleNamespace

WL = "wonders-of-the-witchlight"


def test_no_undefined_names():
    """pyflakes F821 over the app — the class of bug where a handler logs
    (or renders) through a name that doesn't exist and dies at runtime."""
    r = subprocess.run(
        [sys.executable, "-m", "pyflakes",
         "gui/", "helpers/", "agentic/", "main.py", "messaging.py"],
        capture_output=True, text=True)
    bad = [ln for ln in (r.stdout + r.stderr).splitlines()
           if "undefined name" in ln]
    assert not bad, "undefined names (latent NameErrors):\n" + "\n".join(bad)


def test_rough_events_carry_every_board_kind():
    """The JS payloads must carry every id read_board can consume — a
    board kind whose ids never ride the payload loses every drag (B1)."""
    from gui.light_table import DRAG_JS
    for evt in ("rough_block", "stack_reorder"):
        block = DRAG_JS.split(f"emitEvent('{evt}'", 1)[1][:600]
        for key in ("series", "issue", "scene", "panel", "cover",
                    "insert", "artboard", "scope"):
            assert f"{key}:" in block, f"{evt} payload must carry '{key}'"


def test_read_board_resolves_marks_and_never_raises(storage):
    """A rough event from the mark bench lands on its ArtBoard; a
    malformed payload is a no-op, never a KeyError that eats the drag."""
    from gui.light_table import read_board
    from schema import ArtBoard
    b = ArtBoard(board_id="masthead-evt-pin", scope_id=WL,
                 board_kind="masthead", name="event pin")
    storage.create_object(data=b, overwrite=True)
    got = read_board(storage, {"artboard": "masthead-evt-pin", "scope": WL})
    assert got is not None and got.board_id == "masthead-evt-pin"
    # a payload with no resolvable board must return None, not raise
    assert read_board(storage, {"series": WL, "issue": "x"}) is None


def test_fresh_board_syncs_the_words(storage):
    """fresh_board must pull the WORDS too — dblclick-edited balloons and
    the brief persist out-of-band, and a stale copy would clobber them (B2)."""
    from gui.light_table import fresh_board
    from schema import SceneModel, Panel

    issue_id = "witchlight-carnival"
    panel = None
    for sc in storage.read_all_objects(SceneModel, primary_key={
            "series_id": WL, "issue_id": issue_id}):
        ps = storage.read_all_objects(Panel, primary_key={
            "series_id": WL, "issue_id": issue_id, "scene_id": sc.scene_id})
        if ps:
            panel = ps[0]
            break
    assert panel is not None
    stale = storage.read_object(Panel, panel.primary_key)
    live = storage.read_object(Panel, panel.primary_key)
    live.description = "the words the author just typed"
    storage.update_object(live)
    fresh_board(storage, stale)
    assert stale.description == "the words the author just typed", \
        "fresh_board must sync description (and dialogue/narration)"


def test_tilt_and_dress_survive_the_block_handler():
    """Source pins: _on_block persists rot (and clears it on zero), and a
    dress dblclick routes to the conversation, never a discarded edit."""
    src = open("gui/light_table.py").read()
    on_block = src.split("def _on_block", 1)[1].split("ui.on('rough_block'", 1)[0]
    assert 'cur["rot"]' in on_block, "the tilt must persist (B3)"
    assert 'cur.pop("rot"' in on_block, "rot: 0 must CLEAR a tilt"
    from gui.light_table import DRAG_JS
    assert "dress/" in DRAG_JS and "dress_ask" in DRAG_JS, \
        "dress pieces ask the Editor instead of offering a discarded edit (B6)"
    assert "ui.on('dress_ask'" in src


def test_stale_write_sites_fresh_first():
    """The three B4 sites (and the class): every rail handler that does a
    full-object write freshes the live table state first."""
    src = open("gui/light_table.py").read()
    for fn in ("def reassign_balloon", "def ungroup"):
        body = src.split(fn, 1)[1][:400]
        assert "fresh_board(" in body.split("update_object", 1)[0], \
            f"{fn} must fresh_board before writing"
    wear = src.split("def wear_style_on_table", 1)[1][:600]
    assert "fresh_board(" in wear.split("update_object", 1)[0], \
        "wear_style_on_table must sync a board owner before writing"


def test_the_print_brush_rides_the_queue():
    """Q1 ruling: THE PRINT's brush proofs through the render queue (one
    board line, HOLD/STOP) — not a conversational detour."""
    for path in ("gui/panel.py", "gui/cover.py", "gui/insert.py"):
        src = open(path).read()
        assert "'proof'" in src, f"{path}: the brush action uses the proof sentinel"
        assert "I would like to render this" not in src
    lt = open("gui/light_table.py").read()
    assert "proof_flow if handler == 'proof' else handler" in lt


def test_production_doors_land_on_printed_anchors(storage):
    """B7: every scene-row anchor the dashboard emits points at something
    the beats altitude actually prints — panel tiles for paneled scenes,
    the scene slip for bare ones."""
    from helpers.production import production_board
    board = production_board(storage, WL, "witchlight-carnival")
    from schema import Panel
    for story in board.stories:
        for row in story.scenes:
            if row.panels:
                assert row.anchor.startswith("panel-"), \
                    f"paneled scene {row.scene_id} must aim at its first tile"
            else:
                assert row.anchor == f"scene-{row.scene_id}"


def test_wardrobe_swap_knows_inserts(storage):
    """B8: a figure cast on a full-page insert can swap wardrobe — the
    character room resolves insert hosts like panels and covers."""
    src = open("gui/character.py").read()
    assert '"insert"' in src and "insert_id" in src


def test_the_header_and_box_stay_quiet():
    """Author rulings (2026-07-15): no daybook door, no open-in-new, no
    header search button, no paperclip/mic/read-aloud — the conversation
    box is for words; images arrive by drop or paste."""
    import os as _os
    main_src = open("main.py").read()
    for gone in ("open_daybook", "daybook_btn", "attach_file", "attach_upload",
                 "mic_button", "speak_button", "init_speech_support",
                 "palette_btn"):
        assert gone not in main_src, f"'{gone}' should be gone from main.py"
    assert not _os.path.exists("gui/speech.py"), "speech support is retired"
    assert "open_in_new" not in open("gui/state.py").read(), \
        "the open-in-new-window button is gone"
    # the palette still stands behind Ctrl/Cmd-K
    assert "ui.keyboard" in main_src and "build_palette" in main_src
