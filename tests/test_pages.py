"""Page layout: the designed-grid path through layout tool, binder, and reader data."""
import asyncio
import json
import os

import agentic.tools.imaging as imaging
from helpers.binder import bind_issue_pdf, layout_pages
from gui.selection import SelectionItem, SelectedKind
from schema import Page, Panel

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"
TENT_SCENE = "b3cc50eb-5a57-463c-ba10-927d941c9779"
TENT_PANEL = "667ca06e-8b94-4d98-ab88-f996d6f3c8f9"


class _Stub:
    def __init__(self, storage):
        self.storage = storage
        self.is_dirty = False
        self.selection = [SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES)]


class _Ctx:
    def __init__(self, state): self.context = state


def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


def test_layout_tool_places_panels(storage):
    out = _invoke(imaging.layout_issue_pages, _Stub(storage),
                  series_id=WL, issue_id=CARN, pages=[[[TENT_PANEL]]])
    assert "Laid out 1 pages" in str(out)
    assert "not placed" in str(out), "unplaced panels must be reported"
    pages = storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN})
    assert len(pages) == 1 and pages[0].rows[0][0].panel_id == TENT_PANEL


def test_layout_tool_rejects_unknown_panel(storage):
    out = _invoke(imaging.layout_issue_pages, _Stub(storage),
                  series_id=WL, issue_id=CARN, pages=[[["nope"]]])
    assert "Unknown panel" in str(out)


def test_binder_composes_designed_pages(storage, tmp_data, unrendered_panel):
    # splash page of the rendered tent panel + a row with an unrendered placeholder
    other = unrendered_panel.panel_id
    _invoke(imaging.layout_issue_pages, _Stub(storage),
            series_id=WL, issue_id=CARN, pages=[[[TENT_PANEL]], [[TENT_PANEL, other]]])
    layout = layout_pages(storage, WL, CARN)
    assert len(layout) == 2
    assert layout[1][1][0][1] is None, "unrendered panel resolves to a placeholder"

    out = os.path.join(tmp_data, "series", WL, "issues", CARN, "exports", "paged.pdf")
    count, _missing = bind_issue_pdf(storage, WL, CARN, out)
    # front + 2 designed pages + the issue's OTHER rendered panels, which
    # now flow onto extra pages instead of being silently dropped
    assert count > 3
    assert any("on NO page" in m for m in _missing)
    assert os.path.getsize(out) > 10_000
