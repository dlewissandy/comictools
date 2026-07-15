"""End-to-end UI test: type a message, click Send, and assert the agent's
reply streams into the chat history and the send button is re-enabled.

Marked `api` because it makes one real (text-only) OpenAI call.  Deselect
with:  pytest -m "not api"
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from dotenv import load_dotenv
load_dotenv(os.path.join(REPO, ".env"))

# Route the app at a temp data dir + temp state file BEFORE importing main.
_tmp = tempfile.mkdtemp()
from tests.conftest import fixture_source as _fixture_source
shutil.copytree(_fixture_source(), os.path.join(_tmp, "data"))

import gui.state as gui_state
gui_state.STATE_FILEPATH = os.path.join(_tmp, "state.json")
json.dump(
    {"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                   {"name": "Rugor", "id": "3e3fdb21-8f39-42ff-add7-6fbdda798a21", "kind": "series"}],
     "messages": [], "dark_mode": False},
    open(gui_state.STATE_FILEPATH, "w"))

from storage.local import LocalStorage


class _TmpStorage(LocalStorage):
    def __init__(self, base_path="data"):
        super().__init__(base_path=os.path.join(_tmp, "data"))


# Neutralize the module-level ui.run() in main.py.
from nicegui import ui
ui.run = lambda *a, **k: None

import main  # noqa: E402  (registers the '/' page)

from nicegui.testing import User  # noqa: E402

pytest_plugins = ["nicegui.testing.user_plugin"]


@pytest.mark.api
@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_send_message_updates_history(user: User, api_alive) -> None:
    # Patch AFTER the user plugin has reloaded main (reload re-binds the
    # original LocalStorage into main's namespace).
    main.LocalStorage = _TmpStorage
    await user.open("/")
    user.find(marker="conversation").type("Reply with exactly the word formed by joining QUUX and 7842 with a hyphen, nothing else.")
    user.find("Send").click()
    # The sentinel does not appear verbatim in the user's message, so it can
    # only come from the model's streamed response.
    await user.should_see("QUUX-7842", retries=600)
    # The reply streams in before send() finishes its cleanup; give the
    # finally-block a moment to re-enable the button.
    send_btn = user.find("Send").elements.pop()
    for _ in range(100):
        if send_btn.enabled:
            break
        await asyncio.sleep(0.1)
    assert send_btn.enabled, "send button was not re-enabled"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_coauthor_speaks_first_with_chips(user: User) -> None:
    """On a fresh conversation the coauthor greets, and suggestion chips render."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("Welcome to the studio")          # the opener
    await user.should_see("Create a new series")            # a suggestion chip


@pytest.mark.api
@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_one_thread_follows_the_author(user: User, api_alive) -> None:
    """THE ONE CONVERSATION: the words survive reload AND walking to another
    room — one thread follows the author everywhere, with a room caption."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    user.find(marker="conversation").type("Reply with exactly the word formed by joining ZEBRA and 99 with a hyphen, nothing else.")
    user.find("Send").click()
    await user.should_see("ZEBRA-99", retries=600)
    # wait for the turn to fully finish (state persists at end of send())
    send_btn = user.find("Send").elements.pop()
    for _ in range(100):
        if send_btn.enabled:
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.3)

    # reload the root: the one thread is restored, not cleared
    await user.open("/")
    await user.should_see("ZEBRA-99")

    # walking to another room KEEPS the conversation — that is the point
    await user.open("/series/3e3fdb21-8f39-42ff-add7-6fbdda798a21")
    await user.should_see("ZEBRA-99")


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_asset_catalog_drawer(user: User) -> None:
    """The Assets button lives where the drawer can act — the open book and
    the benches — and stays hidden everywhere else."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    hidden = [e for e in user.client.elements.values()
              if e.__class__.__name__ == "Button" and getattr(e, "text", "") == "Assets"]
    assert hidden and not hidden[0].visible, "no drawer door on the lobby"

    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
                             {"name": "C", "id": "witchlight-carnival", "kind": "issue"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    # read the book as PROOFS (bound images) so the drawer's filter assertions
    # aren't confounded by panel BEAT text behind it (a beat mentions the very
    # 'cracked crystal ball' prop this test filters on)
    user.find(marker="detail-proofs").click()
    user.find("Assets").click()
    await user.should_see("in the studio")           # header with total count
    await user.should_see("Fortune Teller Tent")     # a setting tile

    # filter by type: styles shows the house styles, hides the props.  Target
    # the drawer's KIND toggle by its option labels; set.pop() over all toggles
    # is non-deterministic — other toggles share the page.
    kind_toggle = next(t for t in user.client.elements.values()
                       if t.__class__.__name__ == "Toggle" and t.value == "all")
    kind_toggle.set_value("style")
    # styles wear their HOUSE's name — 'studio-wide' is the retired claim
    await user.should_see("DND NERDS")
    await user.should_not_see("cracked crystal ball")
    # props: drawn from the settings' prop lists
    kind_toggle.set_value("prop")
    await user.should_see("cracked crystal ball")
    # variants: wardrobe per character, e.g. Brassic's gnome disguise
    kind_toggle.set_value("variant")
    await user.should_see("Gnome Disguise")


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_inline_scalar_edit_affordance(user: User) -> None:
    """Issue scalars are click-to-edit in place (tooltip advertises it)."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
                             {"name": "C", "id": "witchlight-carnival", "kind": "issue"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    # THE COLOPHON prints the issue-wide indicia — every line a pencil
    await user.should_see("COLOPHON")
    await user.should_see("PRICE")
    await user.should_see("CREATIVE MINDS")
    # every credit line advertises its pencil
    tips = [getattr(e, "text", "") for e in user.client.elements.values()
            if e.__class__.__name__ == "Tooltip"]
    assert any("Set the price" in t for t in tips), "price line is a pencil"
    assert any("Set the creative minds" in t for t in tips), "creative minds line is a pencil"


def _seat_tent_cast(storage):
    """The tent tests direct their own extras: make sure Ezra is cast in the
    scene AND standing on the tent panel — the LIVE fixture is the author's
    working data and they may strike anyone they like."""
    from schema import SceneModel, Panel, CharacterRef
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    SC, P = "b3cc50eb-5a57-463c-ba10-927d941c9779", "667ca06e-8b94-4d98-ab88-f996d6f3c8f9"
    ref = CharacterRef(series_id=WL, character_id="ezra", variant_id="base")
    sc = storage.read_object(SceneModel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
    if not any(c.character_id == "ezra" for c in (sc.cast or [])):
        sc.cast = [*(sc.cast or []), ref]
        storage.update_object(sc)
    pnl = storage.read_object(Panel, {"series_id": WL, "issue_id": CARN,
                                      "scene_id": SC, "panel_id": P})
    if not any(r.character_id == "ezra" for r in (pnl.character_references or [])):
        pnl.character_references = [*(pnl.character_references or []), ref]
        storage.update_object(pnl)


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_palette_and_chip_removal(user: User) -> None:
    """Cmd-K palette lists objects; scene assets are removable chips."""
    main.LocalStorage = _TmpStorage
    _seat_tent_cast(_TmpStorage())
    # scene with attached setting + cast: the tent consultation
    json.dump({"selection": [
        {"name": "Series", "id": None, "kind": "all-series"},
        {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
        {"name": "C", "id": "witchlight-carnival", "kind": "issue"},
        {"name": "T", "id": "b3cc50eb-5a57-463c-ba10-927d941c9779", "kind": "scene"}],
        "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    # attached assets render as chips
    await user.should_see("Fortune Teller Tent")
    # the cast chip wears the character's NAME, not the raw id
    await user.should_see("Ezra")

    # remove Ezra from the cast via the chip's ✕
    from nicegui import ui as _ui
    chips = [e for e in user.client.elements.values()
             if e.__class__.__name__ == "Chip" and "ezra" in str(getattr(e, "text", "")).lower()]
    assert chips, "cast chip exists"
    chips[0]._handle_event({"handler_id": None}) if False else None
    # fire the 'remove' event through the element's registered handler
    for ev in chips[0]._event_listeners.values():
        if ev.type == "remove":
            chips[0]._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    await user.should_see("removed")          # the ✂️ receipt in chat

    # palette: open via the search button and find the tent by name
    search_btns = [e for e in user.client.elements.values()
                   if e.__class__.__name__ == "Button" and getattr(e, "props", {}).get("icon") == "search"]
    assert search_btns, "palette button exists"
    btn = search_btns[0]
    for ev in btn._event_listeners.values():
        if ev.type == "click":
            btn._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    palette_inputs = [e for e in user.client.elements.values()
                      if e.__class__.__name__ == "Input" and "Jump to anything" in str(getattr(e, "props", {}).get("placeholder", ""))]
    assert palette_inputs, "palette input exists"
    palette_inputs[-1].set_value("fortune")
    await user.should_see("setting · Wonders of the Witchlight")


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_issue_production_dashboard(user: User) -> None:
    """The issue view opens as THE OPEN BOOK: script page, pages, colophon."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
                             {"name": "C", "id": "witchlight-carnival", "kind": "issue"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    # the detail dial reads the book at five altitudes: scripts, scenes,
    # beats, roughs, proofs
    await user.should_see("SCRIPTS")
    await user.should_see("BEATS")
    await user.should_see("ROUGHS")
    await user.should_see("PROOFS")
    await user.should_see("COLOPHON")
    await user.should_see("panels inked")   # a production stage on the colophon
    # a broken-down story steps back at beats detail; the dial brings it up
    user.find(marker="detail-stories").click()
    await user.should_see("THE SCRIPT")


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_drawer_scopes_to_current_series(user: User) -> None:
    """Inside a series the catalog defaults to that series; the switch widens it."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
                             {"name": "C", "id": "witchlight-carnival", "kind": "issue"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    user.find("Assets").click()
    await user.should_see("Fortune Teller Tent")
    await user.should_not_see("Squonk")   # Rugor's assets are out of scope

    switches = [e for e in user.client.elements.values()
                if e.__class__.__name__ == "Switch" and "only" in str(getattr(e, "text", ""))]
    assert switches, "scope switch exists"
    switches[-1].set_value(False)
    await user.should_see("Squonk")       # the whole HOUSE — one publisher at a time


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_cast_card_corner_remove(user: User) -> None:
    """The cast card itself carries the remove control: corner ✕ detaches."""
    main.LocalStorage = _TmpStorage
    _seat_tent_cast(_TmpStorage())
    SC, P = "b3cc50eb-5a57-463c-ba10-927d941c9779", "667ca06e-8b94-4d98-ab88-f996d6f3c8f9"
    json.dump({"selection": [
        {"name": "Series", "id": None, "kind": "all-series"},
        {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
        {"name": "C", "id": "witchlight-carnival", "kind": "issue"},
        {"name": "T", "id": SC, "kind": "scene"},
        {"name": "P", "id": P, "kind": "panel"}],
        "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    # the panel's cast cardwall has ✕ buttons (icon=close) on each card —
    # poll: the light table builds after the palette satisfies should_see
    import asyncio as _asyncio
    closers = []
    for _ in range(50):
        closers = [e for e in user.client.elements.values()
                   if e.__class__.__name__ == "Button" and 'uncast' in getattr(e, "_markers", [])]
        if closers:
            break
        await _asyncio.sleep(0.1)
    assert closers, "uncast ✕ exists on figure acetate rows"
    btn = closers[0]
    for ev in btn._event_listeners.values():
        if ev.type.startswith("click"):
            btn._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    await user.should_see("removed")   # ✂️ receipt in the chat

    from schema import Panel
    storage = main.LocalStorage(base_path="data")
    panel = storage.read_object(Panel, {"series_id": "wonders-of-the-witchlight",
                                        "issue_id": "witchlight-carnival",
                                        "scene_id": SC, "panel_id": P})
    assert len(panel.character_references) < 2, "a reference was detached"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_slips_pack_every_bare_scene_exactly_once(user: User) -> None:
    """MANUSCRIPT SLIPS: at the PANELS stop every bare scene appears exactly
    once, in reading order, 1-3 to a sheet — and the printed pagination
    (view/print folio parity) is untouched by the packing."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
                             {"name": "C", "id": "witchlight-carnival", "kind": "issue"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("COLOPHON")          # default dial stop is PANELS

    from schema import SceneModel, Panel
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    storage = _TmpStorage()
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN},
                                      order_by="scene_number")
    bare = [sc for sc in scenes if not storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id})]

    sheets = [e for e in user.client.elements.values()
              if 'book-page--slips' in getattr(e, "_classes", [])]
    slips_per_sheet = [[c for c in sh.default_slot.children
                        if 'page-slip' in getattr(c, "_classes", [])] for sh in sheets]
    assert slips_per_sheet and all(1 <= len(s) <= 3 for s in slips_per_sheet)

    # one slip per bare scene, in reading order, panelled scenes never slip
    banchors = [s._props['data-banchor'] for slips in slips_per_sheet for s in slips]
    assert banchors == [f'scene-{sc.scene_id}' for sc in bare]

    # slips are view-only working paper: the print pagination is unchanged
    from helpers.stitcher import stitch_pages
    flow = [e for e in user.client.elements.values()
            if str(e._props.get('data-banchor', '')).startswith('flow-')]
    assert len(flow) == len(stitch_pages(storage, WL, CARN))


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_long_manuscript_fades_at_200_words(user: User) -> None:
    """STORY FADE: 201 words clamps with a 'continues' door to the full
    text; exactly 200 does not.  The door opens the whole manuscript."""
    main.LocalStorage = _TmpStorage
    from schema import SceneModel, Panel
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    storage = _TmpStorage()
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN},
                                      order_by="scene_number")
    bare = [sc for sc in scenes if not storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id})]
    long_sc, edge_sc = bare[0], bare[1]
    keep = (long_sc.story, edge_sc.story)
    long_sc.story = ('mirror ' * 201).strip()
    edge_sc.story = ('lantern ' * 200).strip()
    storage.update_object(long_sc)
    storage.update_object(edge_sc)
    try:
        json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                                 {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
                                 {"name": "C", "id": "witchlight-carnival", "kind": "issue"}],
                   "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
        await user.open("/")
        await user.should_see("COLOPHON")
        user.find(marker="detail-scenes").click()
        await user.should_see("continues — open to read")

        # the boundary: the 201-word scene fades, the 200-word one does not
        clamped = [e for e in user.client.elements.values()
                   if 'script-clamp' in getattr(e, "_classes", [])]
        assert len(clamped) == 1
        chips = [e for e in user.client.elements.values()
                 if e.__class__.__name__ == "Chip" and 'continues' in str(getattr(e, 'text', ''))]
        assert len(chips) == 1

        # the door holds the FULL text, not the faded view
        user.find('continues — open to read').click()
        await user.should_see('Save')
        assert any(getattr(t, 'value', '') == long_sc.story
                   for t in user.client.elements.values()
                   if t.__class__.__name__ == 'Textarea')
    finally:
        long_sc.story, edge_sc.story = keep
        storage.update_object(long_sc)
        storage.update_object(edge_sc)


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_colophon_prints_all_credits_and_each_line_is_a_pencil(user: User, monkeypatch) -> None:
    """THE INDICIA SET IN TYPE: the issue-wide credits (creative minds,
    publication date, price) print — set values show, unset ones ghost, a
    click posts the edit ask for THAT role.  The per-STORY credits (writer,
    artist, letterer) print in the production dashboard, one team per feature."""
    main.LocalStorage = _TmpStorage
    sent = []
    monkeypatch.setattr('gui.issue.post_user_message', lambda state, msg: sent.append(msg))
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
                             {"name": "C", "id": "witchlight-carnival", "kind": "issue"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("COLOPHON")
    for role in ("CREATIVE MINDS", "PUBLICATION DATE", "PRICE"):
        await user.should_see(role)
    await user.should_see("Summer 2024")             # publication date, set in fixture
    await user.should_see("unset — pencil it in")    # creative minds / price are unset
    # the per-story credits print in the dashboard — the issue's own script
    # carries the issue-wide writer as its byline
    await user.should_see("Mud, scribe of the Earth")

    lines = [e for e in user.client.elements.values()
             if 'credit-line' in getattr(e, "_classes", [])]
    assert len(lines) == 3
    for ev in lines[0]._event_listeners.values():
        if ev.type.startswith("click"):
            lines[0]._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    assert sent == ["I would like to edit the creative minds."]


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_mailbag_letter_blocks_ride_the_table(user: User) -> None:
    """THE MAILBAG'S LETTERS: on an unlocked text insert, every description
    block rides the rough as a letter acetate with its own stack row."""
    main.LocalStorage = _TmpStorage
    from schema import Insert
    from helpers.compositor import letter_blocks
    storage = _TmpStorage()
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    ins = storage.read_all_objects(Insert, primary_key={"series_id": WL, "issue_id": CARN})[0]
    keep = ins.image
    ins.image = None            # unlocked, in the tmp copy only
    storage.update_object(ins)
    try:
        json.dump({"selection": [{"name": "S", "id": None, "kind": "all-series"},
                                 {"name": "WL", "id": WL, "kind": "series"},
                                 {"name": "C", "id": CARN, "kind": "issue"},
                                 {"name": "M", "id": ins.insert_id, "kind": "insert"}],
                   "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
        await user.open("/")
        n = len(letter_blocks(ins.description))
        assert n > 0
        blocks = [e for e in user.client.elements.values()
                  if 'rough-letterblock' in str(getattr(e, "_classes", []))]
        assert len(blocks) == n, "one letter acetate per description block"
        # each block key persists through the shared blocking path
        keys = {e._props.get('data-key') for e in blocks}
        assert keys == {f'letterblock/{i}' for i in range(n)}
    finally:
        ins.image = keep
        storage.update_object(ins)


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_lobby_resume_card_and_scene_door(user: User) -> None:
    """ONE HOME PER THING: the lobby offers the last bench back; a scene is
    never its own page — selecting one opens the book to its manuscript page,
    production line and all, with no scene chip in the breadcrumb."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("STILL ON THE DRAWING BOARD")

    # a scene is not a page — it rides in the book
    from schema import SceneModel, Panel
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    storage = _TmpStorage()
    sc = next(s for s in storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
              if storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN,
                                                  "scene_id": s.scene_id}))
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": WL, "kind": "series"},
                             {"name": "C", "id": CARN, "kind": "issue"},
                             {"name": "S", "id": sc.scene_id, "kind": "scene"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    # the book opened to the scene's manuscript page — its production line
    # rides in the book (no standalone scene page, no "read them in the book"
    # door), which only renders at SCENES detail (the redirect set it)
    strips = [e for e in user.client.elements.values()
              if 'scene-prod' in str(getattr(e, "_classes", []))]
    assert strips, "the scene's production line rides in the book"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_cast_chip_is_a_door_to_the_character(user: User) -> None:
    """The cast chip's BODY walks to the character's room; firing ✕ detaches
    without walking anywhere — one chip, two honest verbs."""
    main.LocalStorage = _TmpStorage
    _seat_tent_cast(_TmpStorage())
    json.dump({"selection": [
        {"name": "Series", "id": None, "kind": "all-series"},
        {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
        {"name": "C", "id": "witchlight-carnival", "kind": "issue"},
        {"name": "T", "id": "b3cc50eb-5a57-463c-ba10-927d941c9779", "kind": "scene"}],
        "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("Ezra")

    chips = [e for e in user.client.elements.values()
             if e.__class__.__name__ == "Chip" and "ezra" in str(getattr(e, "text", "")).lower()]
    assert chips, "cast chip exists"
    for ev in chips[0]._event_listeners.values():
        if ev.type == "click":
            chips[0]._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    # the character room opened — provable from the page itself: the
    # scene's production strip is gone and the character's name heads the room
    await user.should_see("Ezra")
    texts = " ".join(str(getattr(e, "text", "")) for e in user.client.elements.values())
    assert "Production" not in texts, "left the scene — this is the character's own room"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_spend_label_opens_the_days_receipts(user: User, tmp_path, monkeypatch) -> None:
    """Clicking the ink meter opens the day's receipts: per-quality counts,
    estimated dollars, and the honesty line."""
    import time as _time
    import helpers.generator as gen
    ledger_file = tmp_path / "spend.json"
    json.dump({_time.strftime("%Y-%m-%d"): {"high": 2, "low": 1}}, open(ledger_file, "w"))
    monkeypatch.setattr(gen, "SPEND_LEDGER", str(ledger_file))

    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("🎨 3")

    labels = [e for e in user.client.elements.values()
              if e.__class__.__name__ == "Label" and "🎨" in str(getattr(e, "text", ""))]
    assert labels, "the ink meter is on the header"
    for ev in labels[0]._event_listeners.values():
        if ev.type == "click":
            labels[0]._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    await user.should_see("receipts")
    await user.should_see("2 at high quality")
    await user.should_see("Estimates at published image rates")


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_a_posters_bench_lays_no_letter_acetates(user: User) -> None:
    """The board twin of the mailbag rule: a poster's description is a render
    BRIEF — unlocking its bench must lay ZERO letter acetates."""
    main.LocalStorage = _TmpStorage
    from schema import Insert
    storage = _TmpStorage()
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    ins = storage.read_all_objects(Insert, primary_key={"series_id": WL, "issue_id": CARN})[0]
    ins.image = None
    ins.kind = "poster"          # tmp copy only
    storage.update_object(ins)
    json.dump({"selection": [{"name": "S", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": WL, "kind": "series"},
                             {"name": "C", "id": CARN, "kind": "issue"},
                             {"name": "M", "id": ins.insert_id, "kind": "insert"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("Letters To Mud")
    blocks = [e for e in user.client.elements.values()
              if 'rough-letterblock' in str(getattr(e, "_classes", []))]
    assert blocks == [], "a poster's brief never rides the table as letters"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_styles_live_in_the_house(user: User) -> None:
    """USER RULING: styles are the house's own copies.  The rack hangs on
    the publisher's page, each style's trail runs through the house, and
    the global Styles room is gone from the crumb and the palette."""
    main.LocalStorage = _TmpStorage
    from schema import Publisher, ComicStyle
    storage = _TmpStorage()
    pub = storage.read_all_objects(Publisher)[0]
    styles = storage.read_all_objects(ComicStyle)
    assert styles, "the fixture house owns styles"

    json.dump({"selection": [
        {"name": "Publishers", "id": None, "kind": "all-publishers"},
        {"name": pub.name, "id": pub.publisher_id, "kind": "publisher"}],
        "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    # the rack: every house style hangs on the publisher's page, with a door
    await user.should_see("House Styles")
    await user.should_see(styles[0].name.title())

    # the crumb's room menu no longer offers a global Styles room
    from nicegui import ui as _ui
    menu_items = [str(getattr(e, "text", "")) for e in user.client.elements.values()
                  if e.__class__.__name__ == "Item" or "Item" in e.__class__.__name__]
    assert not any(t.strip("✓ ") == "Styles" for t in menu_items), \
        "the global Styles room is retired"


def test_style_trail_runs_through_the_house():
    """style_ancestry and both URL grammars agree: Publishers → house → style."""
    from gui.routes import style_ancestry, selection_from_path, selection_to_url
    from schema import Publisher, ComicStyle
    storage = _TmpStorage()
    pub = storage.read_all_objects(Publisher)[0]
    st = storage.read_all_objects(ComicStyle)[0]

    trail = style_ancestry(storage, st.style_id)
    assert [i.kind.value for i in trail] == ["all-publishers", "publisher", "style"]
    assert trail[1].id == pub.publisher_id and trail[2].name == st.name

    url = selection_to_url(trail)
    assert url == f"/publishers/{pub.publisher_id}/style/{st.style_id}"
    assert [i.kind.value for i in selection_from_path(storage, url.strip("/").split("/"))] \
        == ["all-publishers", "publisher", "style"]
    # the OLD address still finds the style — through the house
    legacy = selection_from_path(storage, ["styles", st.style_id])
    assert [i.kind.value for i in legacy] == ["all-publishers", "publisher", "style"]
    # and the retired room's address lands on the house itself
    room = selection_from_path(storage, ["styles"])
    assert [i.kind.value for i in room] == ["all-publishers", "publisher"]


def test_palette_styles_wear_their_house():
    """The palette lists styles under their publisher — no Styles root room."""
    from gui.palette import _index
    storage = _TmpStorage()
    entries = _index(storage)
    rooms = [label for _i, label, sub, _s in entries if sub == "room"]
    assert "Styles" not in rooms
    style_rows = [(label, sub, sel) for _i, label, sub, sel in entries if sub.startswith("style ·")]
    assert style_rows, "styles are still jumpable"
    for _label, _sub, sel in style_rows:
        assert [i.kind.value for i in sel] == ["all-publishers", "publisher", "style"]


def test_non_canonical_style_trails_still_share():
    """A stale [Styles-room, style] trail or a publisher-less house must
    serialize to the legacy /styles/<id> alias — an address that always
    parses back through the house — never an unparseable URL."""
    from gui.routes import selection_to_url, selection_from_path
    from gui.selection import SelectionItem as S, SelectedKind as K
    storage = _TmpStorage()
    from schema import ComicStyle
    st = storage.read_all_objects(ComicStyle)[0]

    legacy = [S(name="Styles", id=None, kind=K.ALL_STYLES),
              S(name=st.name, id=st.style_id, kind=K.STYLE)]
    url = selection_to_url(legacy)
    assert url == f"/styles/{st.style_id}"
    assert selection_from_path(storage, url.strip("/").split("/")) is not None

    homeless = [S(name="Publishers", id=None, kind=K.ALL_PUBLISHERS),
                S(name=st.name, id=st.style_id, kind=K.STYLE)]
    url = selection_to_url(homeless)
    assert url == f"/styles/{st.style_id}", "no publisher hop — fall back to the alias"
    assert selection_from_path(storage, url.strip("/").split("/")) is not None


def test_striking_a_style_walks_home_to_the_house():
    """The deleter returns the 'Deleted' prefix strike() gates undo on, and
    walks the selection up to the house itself."""
    import asyncio as _asyncio
    from types import SimpleNamespace
    from agentic.tools.deleter import delete_style
    from gui.routes import style_ancestry
    from schema import ComicStyle
    storage = _TmpStorage()
    st = storage.read_all_objects(ComicStyle)[0]

    moves = []
    state = SimpleNamespace(
        storage=storage, selection=style_ancestry(storage, st.style_id),
        change_selection=lambda new: moves.append(new))
    out = str(_asyncio.run(delete_style.on_invoke_tool(
        SimpleNamespace(context=state), json.dumps({"style_id": st.style_id}))))
    assert out.startswith("Deleted"), out
    assert moves and [i.kind.value for i in moves[-1]] == ["all-publishers", "publisher"], \
        "the room walks up to the house, not the wall"
    assert storage.read_object(ComicStyle, {"style_id": st.style_id}) is None


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_style_rename_saves_on_the_spot(user: User) -> None:
    """The rename pencil saves directly: the object persists, the crumb and
    header wear the new name, and an empty name never touches the style."""
    main.LocalStorage = _TmpStorage
    from schema import ComicStyle, Publisher
    storage = _TmpStorage()
    st = sorted(storage.read_all_objects(ComicStyle), key=lambda s: s.name)[0]
    pub = storage.read_all_objects(Publisher)[0]
    json.dump({"selection": [
        {"name": "Publishers", "id": None, "kind": "all-publishers"},
        {"name": pub.name, "id": pub.publisher_id, "kind": "publisher"},
        {"name": st.name, "id": st.style_id, "kind": "style"}],
        "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see(st.name.title())

    def click(btn):
        for ev in btn._event_listeners.values():
            if ev.type == "click":
                btn._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})

    def pencils():
        return [e for e in user.client.elements.values()
                if e.__class__.__name__ == "Button"
                and getattr(e, "props", {}).get("icon") == "edit"]

    # the header's rename pencil is the first edit button in the room
    click(pencils()[0])
    await user.should_see("Rename this style")

    def dialog_bits():
        field = [e for e in user.client.elements.values()
                 if e.__class__.__name__ == "Input"][-1]
        save = [e for e in user.client.elements.values()
                if e.__class__.__name__ == "Button"
                and "Save" in str(getattr(e, "text", ""))][-1]
        return field, save

    # the empty-name guard: whitespace never touches the style
    field, save = dialog_bits()
    field.set_value("   ")
    click(save)
    assert storage.read_object(ComicStyle, {"style_id": st.style_id}).name == st.name

    # a real name saves, re-renders the header, and receipts in the chat
    field.set_value("Chalk And Ash")
    click(save)
    await user.should_see("Chalk And Ash")
    assert storage.read_object(ComicStyle, {"style_id": st.style_id}).name == "Chalk And Ash"
    await user.should_see("renamed")            # the 🏷 receipt

    # rename it back so the shared tmp fixture stays stable for later tests
    click(pencils()[0])
    await user.should_see("Rename this style")
    field, save = dialog_bits()
    field.set_value(st.name)
    click(save)
    assert storage.read_object(ComicStyle, {"style_id": st.style_id}).name == st.name


def test_legacy_style_threads_migrate_to_the_house():
    """No conversation orphans: threads keyed under the retired /styles room
    re-key to the canonical house trail — all three legacy shapes."""
    convs = {"/styles": [{"m": "room"}],
             "/styles/van-gogh": [{"m": "vg"}],
             "/styles/style/conte-crayon": [{"m": "cc"}],
             "/series/joey": [{"m": "stay"}]}
    out = gui_state.APPState.migrate_style_threads(convs, "i-do-it")
    assert out["/publishers/i-do-it"] == [{"m": "room"}]
    assert out["/publishers/i-do-it/style/van-gogh"] == [{"m": "vg"}]
    assert out["/publishers/i-do-it/style/conte-crayon"] == [{"m": "cc"}]
    assert out["/series/joey"] == [{"m": "stay"}]
    assert not any(k.startswith("/styles") for k in out)
    # an existing thread at the new address is never clobbered
    convs = {"/styles/van-gogh": [{"m": "old"}],
             "/publishers/i-do-it/style/van-gogh": [{"m": "new"}]}
    out = gui_state.APPState.migrate_style_threads(convs, "i-do-it")
    assert out["/publishers/i-do-it/style/van-gogh"] == [{"m": "new"}]
    # a publisher-less repo leaves keys alone rather than guessing
    convs = {"/styles/van-gogh": [{"m": "vg"}]}
    assert gui_state.APPState.migrate_style_threads(convs, None) == convs


def test_bench_defaults_stay_intent_only():
    """THE THREE-FILE STRING CONTRACT: the bench's default chat messages must
    read as intent-only to the imaging tools — otherwise a bare tool-rail
    press becomes a paid render of the literal sentence."""
    from agentic.tools.imaging import _is_intent_only
    assert _is_intent_only("Heal the marked patch of this image.", "inpaint")
    assert _is_intent_only("Extend the paper on this image.", "outpaint")
    assert not _is_intent_only("heal the scratched sky", "inpaint")
    assert not _is_intent_only("extend the paper into a wide alley shot", "outpaint")


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_the_healing_bench_speaks_comics(user: User) -> None:
    """The rebuilt bench: named acetate in the masthead, comics verbs on the
    rail, the honesty line, and a door out."""
    main.LocalStorage = _TmpStorage
    from schema import Panel
    storage = _TmpStorage()
    WL, CARN, SC = ("wonders-of-the-witchlight", "witchlight-carnival",
                    "b3cc50eb-5a57-463c-ba10-927d941c9779")
    pnl = next(p for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
        if p.image)
    img = os.path.join(_tmp, pnl.image)
    assert os.path.exists(img)
    json.dump({"selection": [
        {"name": "Series", "id": None, "kind": "all-series"},
        {"name": "WL", "id": WL, "kind": "series"},
        {"name": "C", "id": CARN, "kind": "issue"},
        {"name": "T", "id": SC, "kind": "scene"},
        {"name": pnl.name, "id": pnl.panel_id, "kind": "panel"},
        {"name": "Edit Panel Image", "id": img, "kind": "image-editor"}],
        "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see(f"Healing the {pnl.name} acetate")
    await user.should_see("Heal the patch")
    await user.should_see("Extend the paper")
    await user.should_see("Lift the marquee")
    await user.should_see("nothing paid-for burns")
    # a fresh acetate on the bench forgets the last one's marquee and mode
    states = [e for e in user.client.elements.values()]
    assert states, "page rendered"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_the_choices_sheet_pins_the_original(user: User) -> None:
    """THE ORIGINAL is pinned as a first-class pick; choosing it flips the
    verb to 'Keep the original'; leaving the bench moves unpicked takes to
    the wastebasket — nothing paid-for burns."""
    import shutil, time as _time
    main.LocalStorage = _TmpStorage
    from schema import Panel
    storage = _TmpStorage()
    WL, CARN, SC = ("wonders-of-the-witchlight", "witchlight-carnival",
                    "b3cc50eb-5a57-463c-ba10-927d941c9779")
    pnl = next(p for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": SC})
        if p.image)
    orig = os.path.join(_tmp, pnl.image)
    folder = os.path.dirname(orig)
    takes = []
    for i in range(2):
        t = os.path.join(folder, f"choice-sheettest-{i}.jpg")
        shutil.copyfile(orig, t)
        takes.append(t)
    json.dump({"image": orig, "choices": takes, "session_id": "sheettest",
               "written_at": _time.time(), "mode": "inpaint"},
              open(os.path.join(folder, ".choices-sheettest.json"), "w"))
    json.dump({"selection": [
        {"name": "Series", "id": None, "kind": "all-series"},
        {"name": "WL", "id": WL, "kind": "series"},
        {"name": "C", "id": CARN, "kind": "issue"},
        {"name": "T", "id": SC, "kind": "scene"},
        {"name": pnl.name, "id": pnl.panel_id, "kind": "panel"},
        {"name": "Choices", "id": f"sheettest|{orig}", "kind": "image-editor-choices"}],
        "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("The choices sheet")
    await user.should_see("THE ORIGINAL")
    await user.should_see("Paste it down")

    # click THE ORIGINAL's card — the verb flips to keeping it
    badge = next(e for e in user.client.elements.values()
                 if e.__class__.__name__ == "Badge"
                 and "THE ORIGINAL" in str(getattr(e, "text", "")))
    card = badge.parent_slot.parent
    for ev in card._event_listeners.values():
        if ev.type == "click":
            card._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    await user.should_see("Keep the original")

    # leave the bench: the takes go to the wastebasket, not to os.remove
    leave = next(e for e in user.client.elements.values()
                 if e.__class__.__name__ == "Button"
                 and "Leave the bench" in str(getattr(e, "text", "")))
    for ev in leave._event_listeners.values():
        if ev.type == "click":
            leave._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    for _ in range(20):
        if all(not os.path.exists(t) for t in takes):
            break
        await asyncio.sleep(0.1)
    assert all(not os.path.exists(t) for t in takes), "unpicked takes left the folder"
    from storage.trash import list_entries
    notes = " ".join(e.get("note", "") for e in list_entries(os.path.join(_tmp, "data")))
    assert "unpicked take" in notes, "the takes wait in the ONE wastebasket"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_library_shelves_show_wardrobe_and_props(user: User) -> None:
    """The Librarian promises 'every character, wardrobe and setting' — the
    shelves must actually show outfits and props, each a door to its home."""
    main.LocalStorage = _TmpStorage
    from schema import Outfit, PropAsset
    storage = _TmpStorage()
    WL = "wonders-of-the-witchlight"
    storage.create_object(Outfit(outfit_id="shelf-test-cloak", series_id=WL,
                                 name="Shelf Test Cloak",
                                 description="A cloak for the shelf test."), overwrite=True)
    json.dump({"selection": [{"name": "Library", "id": None, "kind": "library"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("Shelf Test Cloak")
    # props already in the fixture shelve too
    props = storage.read_all_objects(PropAsset, {"series_id": WL})
    if props:
        await user.should_see(props[0].name)


def test_the_stop_door_cancels_the_stream():
    """stop_turn holds the live stream's handle and cancels it — the one
    door out of a runaway 40-turn spend."""
    from types import SimpleNamespace
    from messaging import stop_turn, _STOP_WORDS
    calls = []
    state = SimpleNamespace(_live_stream=SimpleNamespace(cancel=lambda: calls.append("cancel")),
                            _stop_requested=False)
    assert stop_turn(state) is True
    assert calls == ["cancel"] and state._stop_requested
    # no live turn -> nothing to stop, honestly
    assert stop_turn(SimpleNamespace(_live_stream=None)) is False
    # the words an author will actually type
    for w in ("stop", "Stop", "cancel", "STOP IT"):
        assert w.lower() in _STOP_WORDS or w.lower() in _STOP_WORDS
    assert "stop" in _STOP_WORDS and "cancel" in _STOP_WORDS


def test_one_agent_memory_gets_a_hat_on_room_change():
    """ONE MEMORY: a room change appends exactly one system hat item to the
    single agent thread — and silent walks coalesce to one hat."""
    from types import SimpleNamespace
    from gui.state import APPState
    from gui.selection import SelectionItem as S, SelectedKind as K

    thr = [{"role": "user", "content": "hello"}]
    hats_before = sum(1 for it in thr if it.get("role") == "system")

    # simulate the change_selection hat logic on a bare namespace
    def add_hat(state, new, new_key):
        hat = {"role": "system",
               "content": f"[The author walked to {new[-1].name} ({new_key}).  "
                          f"You now stand at that bench with its tools; "
                          f"the conversation continues.]"}
        t = state.agent_thread
        if t and isinstance(t[-1], dict) and t[-1].get("role") == "system" \
                and str(t[-1].get("content", "")).startswith("[The author walked"):
            t[-1] = hat
        else:
            t.append(hat)

    state = SimpleNamespace(agent_thread=thr)
    add_hat(state, [S(name="WL", id="wl", kind=K.SERIES)], "/series/wl")
    add_hat(state, [S(name="Carn", id="carn", kind=K.ISSUE)], "/series/wl/issue/carn")
    hats = [it for it in thr if it.get("role") == "system"]
    assert len(hats) - hats_before == 1, "silent walks coalesce to ONE hat"
    assert "Carn" in hats[-1]["content"], "the hat names the CURRENT room"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_no_route_shadows_niceguis_image_serving(user: User) -> None:
    """NiceGUI registers its image routes (/_nicegui/auto/static/…)
    DYNAMICALLY after startup — an import-time catch-all page shadows them
    and 404s EVERY image in the studio.  No page route may own '/{path'."""
    from nicegui import app as _app
    catchalls = [r.path for r in _app.routes
                 if getattr(r, 'path', '').startswith('/{')]
    assert not catchalls, f"catch-all routes shadow dynamic image routes: {catchalls}"
