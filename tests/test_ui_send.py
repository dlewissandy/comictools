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
async def test_conversations_persist_per_object(user: User, api_alive) -> None:
    """The coauthor remembers: a thread survives reload on its own object and
    does not leak into another object's conversation."""
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

    # reload the root: the home conversation is restored, not cleared
    await user.open("/")
    await user.should_see("ZEBRA-99")

    # a different object's conversation does not contain it
    await user.open("/series/3e3fdb21-8f39-42ff-add7-6fbdda798a21")
    await user.should_not_see("ZEBRA-99")


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
    user.find("Assets").click()
    await user.should_see("in the studio")           # header with total count
    await user.should_see("Fortune Teller Tent")     # a setting tile

    # filter by type: styles shows the house styles, hides the props
    from nicegui import ui as _ui
    kind_toggle = user.find(_ui.toggle).elements.pop()
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
    # THE COLOPHON prints the credits set in type — every line a pencil
    await user.should_see("COLOPHON")
    await user.should_see("WRITER")
    await user.should_see("PRICE")
    # every credit line advertises its pencil
    tips = [getattr(e, "text", "") for e in user.client.elements.values()
            if e.__class__.__name__ == "Tooltip"]
    assert any("Set the writer" in t for t in tips), "writer line is a pencil"
    assert any("Set the price" in t for t in tips), "price line is a pencil"


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_palette_and_chip_removal(user: User) -> None:
    """Cmd-K palette lists objects; scene assets are removable chips."""
    main.LocalStorage = _TmpStorage
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
    # the detail dial reads the book at script, scene, or panel altitude
    await user.should_see("SCRIPT")
    await user.should_see("PANELS")
    await user.should_see("COLOPHON")
    await user.should_see("panels inked")
    # a broken-down story steps back at panels detail; the dial brings it up
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
    SC, P = "b3cc50eb-5a57-463c-ba10-927d941c9779", "667ca06e-8b94-4d98-ab88-f996d6f3c8f9"
    json.dump({"selection": [
        {"name": "Series", "id": None, "kind": "all-series"},
        {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
        {"name": "C", "id": "witchlight-carnival", "kind": "issue"},
        {"name": "T", "id": SC, "kind": "scene"},
        {"name": "P", "id": P, "kind": "panel"}],
        "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    # the panel's cast cardwall has ✕ buttons (icon=close) on each card
    closers = [e for e in user.client.elements.values()
               if e.__class__.__name__ == "Button" and 'uncast' in getattr(e, "_markers", [])]
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
    """THE CREDITS SET IN TYPE: all six roles print; set values show, unset
    ones ghost; clicking a line posts the edit ask for THAT role."""
    main.LocalStorage = _TmpStorage
    sent = []
    monkeypatch.setattr('gui.issue.post_user_message', lambda state, msg: sent.append(msg))
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"},
                             {"name": "WL", "id": "wonders-of-the-witchlight", "kind": "series"},
                             {"name": "C", "id": "witchlight-carnival", "kind": "issue"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("COLOPHON")
    for role in ("WRITER", "ARTIST", "COLORIST", "CREATIVE MINDS", "PUBLICATION DATE", "PRICE"):
        await user.should_see(role)
    await user.should_see("Mud, scribe of the Earth")     # set in fixture data
    await user.should_see("unset — pencil it in")

    lines = [e for e in user.client.elements.values()
             if 'credit-line' in getattr(e, "_classes", [])]
    assert len(lines) == 6
    for ev in lines[0]._event_listeners.values():
        if ev.type.startswith("click"):
            lines[0]._handle_event({"handler_id": ev.id, "listener_id": ev.id, "args": {}})
    assert sent == ["I would like to edit the writer."]


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
    """ONE HOME PER THING: the lobby offers the last bench back; the scene
    view keeps a door to the book instead of its own panel grid."""
    main.LocalStorage = _TmpStorage
    json.dump({"selection": [{"name": "Series", "id": None, "kind": "all-series"}],
               "messages": [], "dark_mode": False}, open(gui_state.STATE_FILEPATH, "w"))
    await user.open("/")
    await user.should_see("STILL ON THE DRAWING BOARD")

    # the scene view: a door, not a grid
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
    await user.should_see("read them in the book")


@pytest.mark.module_under_test(main)
@pytest.mark.asyncio
async def test_cast_chip_is_a_door_to_the_character(user: User) -> None:
    """The cast chip's BODY walks to the character's room; firing ✕ detaches
    without walking anywhere — one chip, two honest verbs."""
    main.LocalStorage = _TmpStorage
    # the removal test upstream may have detached Ezra from the shared tmp
    # copy — seat him again so the door has a chip to hang on
    from schema import SceneModel, CharacterRef
    storage = _TmpStorage()
    sc_pk = {"series_id": "wonders-of-the-witchlight", "issue_id": "witchlight-carnival",
             "scene_id": "b3cc50eb-5a57-463c-ba10-927d941c9779"}
    sc = storage.read_object(SceneModel, sc_pk)
    if not any(c.character_id == "ezra" for c in (sc.cast or [])):
        sc.cast = [*(sc.cast or []), CharacterRef(series_id="wonders-of-the-witchlight", character_id="ezra", variant_id="base")]
        storage.update_object(sc)
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
