"""
ONE-CLICK REVERSIBLE DELETES: friction proportional to irreversibility.

Every delete in the studio is a MOVE into the wastebasket, visible and
restorable — so the creative-flow deletes (a panel, a scene, a prop) no
longer route through a chat confirmation.  One click strikes it, the
receipt carries UNDO, and the cascades still run because the strike goes
THROUGH the agent tool body (page refs stripped, scenes renumbered,
insert anchors carried).

The blast-radius deletes (an issue, a series, a publisher) keep their
conversational confirmation — that much friction is proportional.
"""
import json
from types import SimpleNamespace

from nicegui import ui


async def strike(state, tool, params: dict, label: str):
    """Invoke a delete TOOL directly (cascades included), then leave a
    receipt with UNDO that restores the newest wastebasket entry."""
    from gui.light_table import table_receipt
    from storage.trash import list_entries, restore_entry

    wrapper = SimpleNamespace(context=state)
    result = str(await tool.on_invoke_tool(wrapper, json.dumps(params)))
    if not result.startswith("Deleted"):
        ui.notify(result, type='warning')
        return
    base = str(state.storage.base_path)
    entries = list_entries(base, limit=1)
    entry = entries[0]["entry"] if entries else None

    def undo():
        restored = entry and restore_entry(base, entry)
        if restored:
            table_receipt(state, f"↩️ brought {label} back from the wastebasket")
            state.refresh_details()
        else:
            ui.notify("Couldn't bring it back — its place is occupied. "
                      "The wastebasket (header) has the full list.", type='warning')

    table_receipt(state, f"🗑 struck {label} — it waits in the wastebasket", undo=undo)
    state.refresh_details()
