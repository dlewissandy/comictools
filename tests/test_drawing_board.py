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
