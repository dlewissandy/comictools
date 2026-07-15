"""EVERY DOOR LANDS TRUE: agent selects and creates walk the same canonical
trails the UI walks, and deep-link crumbs speak names."""
import asyncio
import json

WL = "wonders-of-the-witchlight"


class _Stub:
    def __init__(self, storage, selection=None):
        self.storage = storage
        self.is_dirty = False
        self.selection = selection or []
        self.trail = None

    def change_selection(self, new):
        self.trail = new
        self.selection = new


class _Ctx:
    def __init__(self, state): self.context = state


def _invoke(tool, state, **args):
    return asyncio.run(tool.on_invoke_tool(_Ctx(state), json.dumps(args)))


def test_select_series_walks_the_one_trail(storage):
    from agentic.tools.navigation import select_series
    from gui.selection import SelectionItem, SelectedKind
    # the chat sits deep in another room — the select must NOT append there
    deep = [SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES),
            SelectionItem(name="Other", id="other", kind=SelectedKind.SERIES),
            SelectionItem(name="Issue", id="i", kind=SelectedKind.ISSUE)]
    state = _Stub(storage, selection=deep)
    out = str(_invoke(select_series, state, series_id=WL))
    assert "Selected comic series" in out
    kinds = [i.kind.value for i in state.trail]
    assert kinds == ["lobby", "publisher", "series"], kinds
    assert state.trail[-1].id == WL and state.trail[-1].name


def test_select_style_keys_the_same_thread_as_the_ui(storage):
    from agentic.tools.navigation import select_comic_style
    from gui.routes import selection_to_url, style_ancestry
    from schema import ComicStyle
    st = storage.read_all_objects(ComicStyle)[0]
    state = _Stub(storage)
    out = str(_invoke(select_comic_style, state, style_id=st.style_id))
    assert "Selected comic style" in out
    # the agent's trail and the UI's trail must serialize to ONE address —
    # otherwise the same style holds two conversations
    assert selection_to_url(state.trail) == selection_to_url(style_ancestry(storage, st.style_id))


def test_deep_link_crumbs_speak_names(storage):
    from gui.routes import selection_from_path
    from schema import SceneModel
    sc = storage.read_all_objects(SceneModel,
        {"series_id": WL, "issue_id": "witchlight-carnival"})[0]
    sel = selection_from_path(storage,
        ["series", WL, "issue", "witchlight-carnival", "scene", sc.scene_id])
    assert sel is not None
    assert sel[-1].name == sc.name, "the crumb wears the scene's NAME, not its id"


def test_select_issue_and_character_walk_the_one_trail(storage):
    from agentic.tools.navigation import select_issue, select_character
    state = _Stub(storage)
    out = str(_invoke(select_issue, state, series_id=WL, issue_id="witchlight-carnival"))
    assert "Opened the issue" in out
    assert [i.kind.value for i in state.trail] == \
        ["lobby", "publisher", "series", "issue"]
    assert state.trail[-1].name and state.trail[-1].name != "witchlight-carnival"

    out = str(_invoke(select_character, state, series_id=WL, character_id="ezra"))
    assert "Opened the character: Ezra" in out
    assert [i.kind.value for i in state.trail] == \
        ["lobby", "publisher", "series", "character"]
