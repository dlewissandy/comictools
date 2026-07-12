"""A bare 'new scene' ask must succeed: name alone is enough, the scene lands
at the end of the issue, and the issue is resolved from anywhere in the
selection chain — not just its exact tail position."""
from types import SimpleNamespace

from agentic.tools.creator import create_scene_body
from gui.selection import SelectionItem, SelectedKind
from schema import SceneModel

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"


def _state(storage, sel):
    return SimpleNamespace(storage=storage, selection=sel, is_dirty=False)


def _sel_issue():
    return [SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES),
            SelectionItem(name="WL", id=WL, kind=SelectedKind.SERIES),
            SelectionItem(name="Carn", id=CARN, kind=SelectedKind.ISSUE)]


def test_bare_name_creates_scene_at_the_end(storage):
    before = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    note = create_scene_body(_state(storage, _sel_issue()), name="Midnight Parade")
    assert "created successfully" in note
    after = sorted(storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN}),
                   key=lambda s: s.scene_number)
    assert len(after) == len(before) + 1
    assert after[-1].name == "Midnight Parade"
    assert after[-1].story == ""
    assert after[-1].scene_number == len(after)
    assert after[-1].style_id  # never empty — falls back to the house style


def test_issue_resolved_from_deeper_selection(storage):
    sel = _sel_issue() + [SelectionItem(name="Scene", id="whatever", kind=SelectedKind.SCENE)]
    note = create_scene_body(_state(storage, sel), name="After the Rain")
    assert "created successfully" in note


def test_no_issue_in_selection_is_a_clear_message(storage):
    sel = [SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES),
           SelectionItem(name="WL", id=WL, kind=SelectedKind.SERIES)]
    note = create_scene_body(_state(storage, sel), name="Nowhere")
    assert "Open an issue first" in note
