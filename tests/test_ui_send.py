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
shutil.copytree(os.path.join(REPO, "data"), os.path.join(_tmp, "data"))

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

    # filter by type: styles shows studio-wide styles, hides the props
    from nicegui import ui as _ui
    kind_toggle = user.find(_ui.toggle).elements.pop()
    kind_toggle.set_value("style")
    await user.should_see("studio-wide")
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
    await user.should_see("ezra")

    # remove Ezra from the cast via the chip's ✕
    from nicegui import ui as _ui
    chips = [e for e in user.client.elements.values()
             if e.__class__.__name__ == "Chip" and "ezra" in str(getattr(e, "text", ""))]
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
