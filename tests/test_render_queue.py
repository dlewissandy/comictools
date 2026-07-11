"""The render queue: batch renders quote first, then run in the background."""
import asyncio
import json
import os

import pytest

import agentic.tools.imaging as imaging
from gui.selection import SelectionItem, SelectedKind
from schema import Panel, SceneModel

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"
TENT_SCENE = "b3cc50eb-5a57-463c-ba10-927d941c9779"


class _Stub:
    def __init__(self, storage):
        self.storage = storage
        self.is_dirty = False
        self.selection = [SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES)]


class _Ctx:
    def __init__(self, state): self.context = state


@pytest.mark.asyncio
async def test_quote_then_background_render(storage, mock_imaging, unrendered_panel):
    st = _Stub(storage)
    out = await imaging.render_missing_panels.on_invoke_tool(
        _Ctx(st), json.dumps({"series_id": WL, "issue_id": CARN}))
    assert "Estimated cost" in str(out) and "confirm=true" in str(out)
    assert not mock_imaging, "no renders happen before confirmation"

    # 2) confirmed: returns immediately, work happens in the background task
    out = await imaging.render_missing_panels.on_invoke_tool(
        _Ctx(st), json.dumps({"series_id": WL, "issue_id": CARN, "confirm": True}))
    assert "background" in str(out)
    await asyncio.wait_for(st._render_task, timeout=30)
    assert mock_imaging, "renders ran"

    # every panel of the issue now has artwork
    remaining = 0
    for sc in storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN}):
        for p in storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id}):
            if not (p.image and os.path.exists(p.image)):
                remaining += 1
    assert remaining == 0


@pytest.mark.asyncio
async def test_nothing_to_render(storage, mock_imaging, tmp_path):
    # construct the precondition rather than assuming it: give every
    # unrendered panel artwork in the test copy of the data
    for sc in storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN}):
        for p in storage.read_all_objects(Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id}):
            if not (p.image and os.path.exists(p.image)):
                img = tmp_path / f"{p.panel_id}.png"
                img.write_bytes(b"png")
                p.image = str(img)
                storage.update_object(p)

    st = _Stub(storage)
    out = await imaging.render_missing_panels.on_invoke_tool(
        _Ctx(st), json.dumps({"series_id": WL, "issue_id": CARN}))
    assert "every panel already has artwork" in str(out)
