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


def test_state_write_merges_the_one_thread(tmp_path, monkeypatch):
    """THE STUDIO REMEMBERS from every window: writes union the ONE thread
    by entry id — two windows appending at once both survive."""
    import json as j
    import types
    import gui.state as gs
    monkeypatch.setattr(gs, 'STATE_FILEPATH', str(tmp_path / 'state.json'))
    j.dump({"thread": [{"id": "theirs", "ts": 2.0, "t": "user", "text": "THEIRS"}],
            "selection": [], "dark_mode": True}, open(gs.STATE_FILEPATH, 'w'))
    dummy = types.SimpleNamespace(
        thread=[{"id": "mine", "ts": 1.0, "t": "user", "text": "MINE"}],
        agent_thread=[], selection=[], dark_mode=False)
    gs.APPState.write(dummy)
    data = j.load(open(gs.STATE_FILEPATH))
    texts = [e["text"] for e in data["thread"]]
    assert texts == ["MINE", "THEIRS"], "union by id, ordered by ts — both survive"
    # idempotent: writing again never duplicates
    gs.APPState.write(dummy)
    data = j.load(open(gs.STATE_FILEPATH))
    assert [e["text"] for e in data["thread"]] == ["MINE", "THEIRS"]


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
    original's alpha outside the healed patch — never an opaque slab.  The
    heal lands as a NEW file beside the original (nothing the author made
    is ever overwritten); the original acetate survives verbatim."""
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
        storage=SimpleNamespace(base_path=str(tmp_path)),
        history=None, refresh_details=lambda: None)
    monkeypatch.setattr("gui.light_table.table_receipt", lambda *a, **k: None)
    ch._apply(state)

    # the original acetate is untouched — the heal is a NEW sibling file
    kept = Image.open(original).convert("RGBA")
    assert kept.getpixel((50, 50))[:3] == (200, 30, 30), "the original survives verbatim"
    healed_files = [f for f in os.listdir(tmp_path) if f.startswith("healed-")]
    assert healed_files, "the healed art landed beside the original"
    out = Image.open(str(tmp_path / healed_files[0])).convert("RGBA")
    assert out.getpixel((5, 5))[3] == 0, "outside the patch stays CLEAR"
    assert out.getpixel((50, 50))[3] == 255, "inside the patch takes the heal"
    assert out.getpixel((50, 50))[:3] == (10, 200, 10), "the healed pixels are the take's"


def test_error_shaped_results_never_announce_done():
    """A tool body that returns 'Prompt file not found.' must be announced
    as a failure — the author must never be told phantom work is done."""
    import re
    pat = r"^(cannot|no |nothing to|unknown |missing )|not found|failed"
    errors = ["Prompt file not found.", "Cannot generate logo image.  There is no logo description.",
              "No reference art for 'rugor' in the Watercolor style yet",
              "Nothing to bind yet: no rendered covers or panels.",
              "Style with ID vintage not found."]
    successes = ["Rendered the panel to data/series/x/panel.jpg",
                 "Bound 24 pages to exports/issue.pdf",
                 "Generated 4 takes.  NOTE: the marquee was empty",
                 "Healed the patch on the acetate"]
    for e in errors:
        assert re.search(pat, e[:120], re.I), f"missed error: {e}"
    for ok in successes:
        assert not re.search(pat, ok[:120], re.I), f"false failure: {ok}"


def test_panelize_resolves_names_to_ids(storage):
    """create_scene_panels must never store a name-keyed cast ref — the
    Squonk dangler at panel scope."""
    import asyncio, json as _json
    from types import SimpleNamespace
    from agentic.tools.creator import create_scene_panels
    from schema import SceneModel, Panel
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    sc = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})[0]
    state = SimpleNamespace(storage=storage, is_dirty=False, selection=[])
    out = str(asyncio.run(create_scene_panels.on_invoke_tool(
        SimpleNamespace(context=state), _json.dumps({
            "series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id,
            "panels": [{"name": "Dangler Test", "beat": "b", "description": "d",
                        "aspect": "landscape",
                        "characters": [{"series_id": WL, "character_id": "Ezra",
                                        "variant_id": "base"}],
                        "narration": [], "dialogue": []}]}))))
    assert "Created 1 panels" in out and "(id: " in out, out
    pnl = next(p for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id})
        if p.name == "Dangler Test")
    assert pnl.character_references and pnl.character_references[0].character_id == "ezra", \
        "the display name resolved to the roster id"


# ---------------------------------------------------------------------------
# THE MASK CONTRACT: the images/edits docs demand the edit target and the
# mask share FORMAT and SIZE (a JPEG take beside a PNG mask had the mask
# silently ignored) — and gpt-image follows a mask only loosely, so the
# darkroom composites the original's exact pixels back where they rule.
# ---------------------------------------------------------------------------
def test_png_for_edit_matches_the_mask_format(tmp_path):
    from PIL import Image
    from agentic.tools.imaging import _png_for_edit
    jpg = str(tmp_path / "take.jpg")
    Image.new("RGB", (60, 40), (200, 10, 10)).save(jpg, "JPEG")
    png_target = _png_for_edit(jpg)
    assert png_target != jpg and png_target.endswith(".png")
    assert Image.open(png_target).size == (60, 40)
    os.remove(png_target)
    png = str(tmp_path / "sheet.png")
    Image.new("RGBA", (60, 40)).save(png)
    assert _png_for_edit(png) == png, "a PNG rides as itself — nothing to clean"


def test_honor_patch_keeps_the_original_outside_the_marquee(tmp_path):
    from io import BytesIO
    from PIL import Image
    from agentic.tools.imaging import _honor_patch
    original = str(tmp_path / "take.jpg")
    Image.new("RGB", (100, 100), (200, 10, 10)).save(original, "JPEG")   # red
    buf = BytesIO()
    Image.new("RGB", (1024, 1024), (10, 200, 10)).save(buf, "PNG")       # green
    region = {"x": 30, "y": 30, "width": 40, "height": 40}
    out_bytes = _honor_patch(original, region, buf.getvalue())
    out = Image.open(BytesIO(out_bytes)).convert("RGB")
    assert out.size == (100, 100)
    assert out.getpixel((5, 5))[0] > 150, "far outside the patch: the original's red"
    assert out.getpixel((50, 50))[1] > 150, "the patch centre: the take's green"


def test_honor_frame_keeps_the_art_in_its_berth(tmp_path):
    from io import BytesIO
    from PIL import Image
    from agentic.tools.imaging import _honor_frame
    original = str(tmp_path / "take.png")
    Image.new("RGB", (100, 100), (200, 10, 10)).save(original)           # red
    buf = BytesIO()
    Image.new("RGB", (1024, 1024), (10, 10, 200)).save(buf, "PNG")       # blue
    padding = {"top": 256, "bottom": 256, "left": 256, "right": 256}
    out_bytes = _honor_frame(original, padding, buf.getvalue())
    out = Image.open(BytesIO(out_bytes)).convert("RGB")
    assert out.size == (612, 612), "the paper grew by the padding"
    assert out.getpixel((306, 306))[0] > 150, "the art's centre survives verbatim"
    assert out.getpixel((10, 10))[2] > 150, "the margins are the model's to paint"
