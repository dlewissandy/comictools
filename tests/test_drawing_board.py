"""NOTHING BLOCKS THE BRUSH: paint stays off the event loop, the queue
carries UI epilogues, and the spend meter counts every image."""
import asyncio
import json
import os
from types import SimpleNamespace

import pytest


def test_imaging_tools_stay_registered_and_threaded():
    """The async wrappers kept their tool schemas; every heavy tool has a
    sync twin that runs in a worker thread."""
    from agentic.tools import imaging as im
    for name in ['generate_panel_image', 'generate_cover_image',
                 'generate_setting_background',
                 'create_styled_image_for_character_variant',
                 'split_layer', 'generate_insert_art',
                 'generate_character_exemplar', 'export_issue_pdf',
                 'export_issue_cbz', 'stitch_issue_pages']:
        tool = getattr(im, name)
        assert hasattr(tool, 'params_json_schema'), f'{name} lost its tool schema'
        assert getattr(im, f'_{name}_sync', None) is not None, f'{name} has no sync twin'
    props = im.generate_panel_image.params_json_schema.get('properties', {})
    assert 'panel_id' in props and 'takes' in props, 'panel tool schema kept its params'


@pytest.mark.asyncio
async def test_render_queue_epilogue_runs_on_the_loop(tmp_path, monkeypatch):
    import helpers.render_queue as rq
    monkeypatch.setattr(rq, 'QUEUE_DIR', str(tmp_path / '.queue'))
    state = SimpleNamespace(refresh_details=lambda: None)
    got, loop_ok = [], []
    main_loop = asyncio.get_running_loop()

    def after(result):
        got.append(result)
        loop_ok.append(asyncio.get_running_loop() is main_loop)
    task = rq.enqueue_renders(state, [("a paint job", lambda: "ok note", after)])
    await task
    assert got == ["ok note"]
    assert loop_ok == [True], "the epilogue must run back on the event loop"
    assert not any(f.endswith('.json') for f in os.listdir(str(tmp_path / '.queue'))), \
        "the slip is burned when the job lands"


def test_spend_counts_every_image(tmp_path, monkeypatch):
    import helpers.generator as g
    monkeypatch.setattr(g, 'SPEND_LEDGER', str(tmp_path / '.spend.json'))
    g.record_spend('high', images=4)
    g.record_spend('high')
    n, cost = g.spend_today()
    assert n == 5, "a four-take heal counts four images, not one call"
    assert abs(cost - 5 * g.EST_COST['high']) < 1e-9


def test_resolve_cast_names_become_ids(storage):
    """The Editor sometimes casts by NAME; the records speak in ids — the
    resolver translates, falls back to an only-variant, and reports (never
    stores) danglers.  (The Squonk-posed-as-Rugor bug.)"""
    from agentic.tools.updater import resolve_cast
    from schema import CharacterRef, CharacterModel, CharacterVariant
    WL = "wonders-of-the-witchlight"
    chars = storage.read_all_objects(CharacterModel, primary_key={"series_id": WL})
    ezra = next(c for c in chars if c.name.strip().lower() == "ezra")
    variants = storage.read_all_objects(CharacterVariant, primary_key={
        "series_id": WL, "character_id": ezra.character_id})
    problems = []
    cast = [CharacterRef(series_id=WL, character_id="Ezra", variant_id=variants[0].id),
            CharacterRef(series_id=WL, character_id="nobody-real", variant_id="x")]
    out = resolve_cast(storage, WL, cast, problems)
    assert len(out) == 1 and out[0].character_id == ezra.character_id
    assert problems and "nobody-real" in problems[0]


def test_panel_face_is_brief_rough_or_print(storage):
    """THE PANEL'S TRUEST FACE: nothing on the table -> no rough face (the
    brief shows); acetates on the table -> a cached rough face; the cache
    key follows the arrangement."""
    from helpers.rough_face import rough_face, rough_signature
    from schema import SceneModel, Panel
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    scenes = {sc.scene_id: sc for sc in storage.read_all_objects(
        SceneModel, {"series_id": WL, "issue_id": CARN})}
    panels = [p for sid in scenes for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sid})]
    import os
    dressed = next(p for p in panels
                   if any(pth and os.path.exists(pth) for pth in (p.figure_images or {}).values()))
    bare = next((p for p in panels if not (p.figure_images or {})), None)

    sig = rough_signature(dressed, scenes[dressed.scene_id])
    assert sig, "a dressed table has a rough signature"
    face = rough_face(storage, dressed, scenes[dressed.scene_id])
    assert face and os.path.exists(face) and sig in face
    assert rough_face(storage, dressed, scenes[dressed.scene_id]) == face, "cached"
    if bare is not None:
        assert rough_signature(bare, scenes[bare.scene_id]) is None, "a bare table shows the brief"


def test_state_write_merges_conversations(tmp_path, monkeypatch):
    """THE STUDIO REMEMBERS from every window: writes merge conversations
    by object key — one window can never clobber another's chats."""
    import json as j
    import types
    import gui.state as gs
    monkeypatch.setattr(gs, 'STATE_FILEPATH', str(tmp_path / 'state.json'))
    j.dump({"conversations": {"other-window": [{"name": "You", "text_html": "THEIRS"}]},
            "selection": [], "dark_mode": True}, open(gs.STATE_FILEPATH, 'w'))
    dummy = types.SimpleNamespace(
        conversations={"mine": [{"name": "You", "text_html": "MINE"}]},
        selection=[], dark_mode=False,
        get_transcript=lambda: [],
        conversation_key=lambda sel: "home")
    gs.APPState.write(dummy)
    data = j.load(open(gs.STATE_FILEPATH))
    assert data["conversations"]["other-window"][0]["text_html"] == "THEIRS"
    assert data["conversations"]["mine"][0]["text_html"] == "MINE"
    assert "home" in data["conversations"]


def test_swatch_book_matches_the_catalog():
    """THE LAYOUT SWATCH BOOK reproduces the author's catalog exactly:
    1125 raw exact tilings of the 6x10 page, 354 unique modulo mirrors
    and 180-degree rotation, every piece speaking the panel vocabulary."""
    from helpers.tilings import swatch_book, swatches_for, PIECE_PANEL, _enumerate_raw
    assert len(_enumerate_raw()) == 1125
    book = swatch_book()
    assert len(book) == 354
    for entry in book:
        area = sum(w * h for _x, _y, w, h in entry["pieces"])
        assert area == 60, "every swatch fills the page exactly"
        for _x, _y, w, h in entry["pieces"]:
            assert (w, h) in PIECE_PANEL, "every piece speaks panel vocabulary"
    assert len(swatches_for(15)) == 1      # the all-squares page
    assert swatches_for(3) == []           # no exact fill below four panels


def test_clear_acetate_apply_keeps_transparency(tmp_path, monkeypatch):
    """CLEAR ACETATE: applying a heal to a transparent acetate restores the
    original's alpha outside the healed patch — never an opaque slab."""
    from types import SimpleNamespace
    from PIL import Image
    import json as j
    import gui.image_editor_choices as ch

    original = str(tmp_path / "acetate.png")
    chosen = str(tmp_path / "take.png")
    src = Image.new("RGBA", (100, 100), (0, 0, 0, 0))          # clear sheet
    for x in range(40, 60):
        for y in range(40, 60):
            src.putpixel((x, y), (200, 30, 30, 255))           # a red figure
    src.save(original)
    Image.new("RGB", (100, 100), (10, 200, 10)).save(chosen)   # opaque take
    j.dump({"image": original, "choices": [chosen], "session_id": "s1",
            "region": {"x": 45, "y": 45, "width": 10, "height": 10}},
           open(tmp_path / ".choices-s1.json", "w"))

    notifications = []
    monkeypatch.setattr(ch.ui, "notify", lambda *a, **k: notifications.append(a))
    state = SimpleNamespace(
        image_editor_choice_selected=chosen,
        image_editor_original_image=original,
        image_editor_image=original,
        image_editor_session_id="s1",
        image_editor_choices=[chosen],
        is_dirty=False,
        selection=[],
        change_selection=lambda new: None,
        history=None, refresh_details=lambda: None)
    monkeypatch.setattr("gui.light_table.table_receipt", lambda *a, **k: None)
    ch._apply(state)

    out = Image.open(original).convert("RGBA")
    assert out.getpixel((5, 5))[3] == 0, "outside the patch stays CLEAR"
    assert out.getpixel((50, 50))[3] == 255, "inside the patch takes the heal"
    assert out.getpixel((50, 50))[:3] == (10, 200, 10), "the healed pixels are the take's"
