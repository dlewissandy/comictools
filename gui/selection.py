from loguru import logger
from pydantic import BaseModel, Field
from nicegui import ui
from gui.state import GUIState

class SelectionItem(BaseModel):
    name: str = Field(..., description="The name that will be displayed on the breadcrumbs")
    id: str | None = Field(..., description="The id of the item.  This will be used to identify the item in the system.")
    kind: str = Field(..., description="The kind of item.  This will be used to identify the item in the system.")

def update_breadcrumbs(state: GUIState):
    """
    Update the breadcrumbs based on a new selection.
    
    Args:
        state: The GUI elements containing the breadcrumbs and selection.
    """
    breadcrumbs = state.get("breadcrumbs")
    selection = state.get("selection")
    breadcrumbs.clear()
    with breadcrumbs:
        ui.button('', icon='home').props('rounded').on_click(lambda _, new_sel=[] : change_selection(state, new_sel))
        for i,item in enumerate(selection):
            new_sel = selection[:i+1]
            ui.button(item.name).props('rounded').on_click(lambda _, new_sel=new_sel: change_selection(state, new=new_sel))

def redraw_details(state: GUIState):
    details = state.get("details")
    details.clear()
    selection = state.get("selection")
    from gui.home import view_home
    from gui.style import view_style, view_pick_style
    from gui.series import view_series
    from gui.character import view_character
    from gui.issue import view_issue
    from gui.scene import view_scene
    from gui.panel import view_panel
    from gui.cover import view_cover
    from gui.publisher import view_publisher, view_pick_publisher
    logger.debug(f"SELECTION:{selection}")

    if selection == []:
        return view_home(state)

    kind = selection[-1].kind
    
    if kind == 'style':
        view_style(state)
    elif kind == 'series':
        view_series(state)
    elif kind == 'character':
        view_character(state)
    elif kind == "issue":
        view_issue(state)
    elif kind == "scene":
        view_scene(state)
    elif kind == "panel":
        view_panel(state)
    elif kind == "cover":
        view_cover(state)
    elif kind == "publisher":
        view_publisher(state)
    elif kind == "pick-publisher":
        view_pick_publisher(state)
    elif kind == "pick-style":
        view_pick_style(state)
    else:
        # Handle other cases or return a default message
        details = state.get("details")
        details.clear()
        with details:
            ui.markdown(f"No description available for this item. {kind}")
            return    



def change_selection(state: GUIState,new:list[SelectionItem], clear_history=True):
    old = state.get("selection")
    if old == new:
        return
    state["selection"] = new
    chat_history = state.get("history")
    details = state.get("details")
    if clear_history:
        chat_history.clear()
    state.get("messages").clear()
    details.clear()
    update_breadcrumbs(state)
    redraw_details(state)
    # TODO: Select the correct agent

