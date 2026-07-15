"""
The studio asset library: every reusable asset — characters, settings,
wardrobe and props — across every series, grouped by publisher.  Browsing
happens here; acting on assets (importing, editing) happens in conversation
with the coauthor.
"""
from nicegui import ui

from gui.elements import header
from gui.state import APPState


def view_library(state: APPState):
    """THE READING ROOM's door: the room itself is the immersive reader —
    walking here opens the book you left (or the first on the wall) with
    the rack drawer for picking any other.  The asset-browser library
    retired: series manage their own assets; the pickers borrow; Cmd-K
    jumps."""
    from storage import registry as _reg
    from schema import Issue as _Issue, Series as _Series
    from gui.selection import SelectedKind
    storage = state.storage

    target = None
    resume = getattr(state, 'resume_selection', None) or state.selection
    sid = next((it.id for it in (resume or []) if it.kind == SelectedKind.SERIES), None)
    iid = next((it.id for it in (resume or []) if it.kind == SelectedKind.ISSUE), None)
    if sid and iid:
        target = (sid, iid)
    if target is None:
        houses = (_reg.mounted_storages() if _reg.registered() else [(None, storage)])
        for _slug, st in houses:
            for sr in sorted(st.read_all_objects(_Series), key=lambda x: x.name):
                issues = sorted(st.read_all_objects(_Issue, {"series_id": sr.series_id}),
                                key=lambda i: i.issue_number or 0)
                if issues:
                    target = (sr.series_id, issues[0].issue_id)
                    break
            if target:
                break

    # NO LANDING PAGE: walking into the Reading Room IS opening it.
    # With a book in hand, straight to its spread; with none anywhere,
    # the spinner-rack wall of every readable issue (/read).
    if target is not None:
        ui.navigate.to(f'/series/{target[0]}/issue/{target[1]}/read')
    else:
        ui.navigate.to('/read')
    with state.details:
        header("The Reading Room", 0)
        ui.label("Lights down…").classes('text-sm q-mt-sm')

