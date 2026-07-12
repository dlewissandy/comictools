"""A series created under a publisher must BELONG to that publisher: the
publisher reference resolves by id or display name (any case), and defaults
to the publisher in the current selection."""
from agentic.tools.creator import resolve_publisher_id
from gui.selection import SelectionItem, SelectedKind


def test_resolves_display_name_and_case(storage):
    assert resolve_publisher_id(storage, "DND NERDS") == "dnd-nerds"
    assert resolve_publisher_id(storage, "dnd-nerds") == "dnd-nerds"
    assert resolve_publisher_id(storage, "Dnd Nerds") == "dnd-nerds"


def test_unknown_publisher_is_flagged_not_stored(storage):
    assert resolve_publisher_id(storage, "Marble Comics") == ""


def test_defaults_to_the_publisher_on_screen(storage):
    sel = [SelectionItem(name="Publishers", id=None, kind=SelectedKind.ALL_PUBLISHERS),
           SelectionItem(name="DND Nerds", id="dnd-nerds", kind=SelectedKind.PUBLISHER)]
    assert resolve_publisher_id(storage, None, sel) == "dnd-nerds"
    assert resolve_publisher_id(storage, None, []) is None
