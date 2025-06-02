from loguru import logger
from pydantic import BaseModel, Field
from nicegui import ui
from gui.state import GUIState

class SelectionItem(BaseModel):
    name: str = Field(..., description="The name that will be displayed on the breadcrumbs")
    id: str | None = Field(..., description="The id of the item.  This will be used to identify the item in the system.")
    kind: str = Field(..., description="The kind of item.  This will be used to identify the item in the system.")

def breadcrumb_selector(state: GUIState):
    

    selection = state.get("selection")
    if selection == []:
        raise ValueError("Selection cannot be empty.  Please select an item first.")
    primary_selection = ui.dropdown_button(selection[0].name.title(), auto_close=True)
    with primary_selection:
        all_series = ui.item("Series")
        all_publishers = ui.item("Publishers")
        all_styles = ui.item("Styles")

    
    new_sel = [selection[0]]
    series_sel = [SelectionItem(kind="all_series", name="Series", id=None)]
    publishers_sel = [SelectionItem(kind="all_publishers", name="Publishers", id=None)]
    styles_sel = [SelectionItem(kind="all_styles", name="Styles", id=None)]

    primary_selection.on("click", lambda _, new_sel=new_sel: change_selection(state, new=new_sel, clear_history=True))
    all_series.on_click(lambda _, new_sel=series_sel: change_selection(state, new=new_sel, clear_history=True))
    all_publishers.on_click( lambda _, new_sel=publishers_sel: change_selection(state, new=new_sel, clear_history=True))
    all_styles.on_click( lambda _, new_sel=styles_sel: change_selection(state, new=new_sel, clear_history=True))
    return primary_selection

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
        breadcrumb_selector(state)
        for i,item in enumerate(selection[1:]):
            logger.critical(f"if i={i} clicked, then selection={selection[:i+2]}")
            new_sel = selection[:i+2]
            ui.button(item.name).props('rounded').on_click(lambda _, new_sel=new_sel: change_selection(state, new=new_sel))

def redraw_details(state: GUIState):
    details = state.get("details")
    details.clear()
    selection = state.get("selection")
    from gui.home import view_all_styles, view_all_series, view_all_publishers
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
        raise ValueError("Selection cannot be empty.  Please select an item first.")

    kind = selection[-1].kind
    

    if kind == "all_series":
        return view_all_series(state)
    if kind == "all_publishers":
        return view_all_publishers(state)
    if kind == "all_styles":
        return view_all_styles(state)
    
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
    logger.critical(f"Changing selection from {old} to {new}")
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

