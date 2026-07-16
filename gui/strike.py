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
    quiet receipt — the wastebasket is the way back."""
    from gui.light_table import table_receipt

    wrapper = SimpleNamespace(context=state)
    result = str(await tool.on_invoke_tool(wrapper, json.dumps(params)))
    if not result.startswith("Deleted"):
        ui.notify(result, type='warning')
        return
    table_receipt(state, f"🗑 struck {label} — it waits in the wastebasket")
    state.refresh_details()
