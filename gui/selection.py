from loguru import logger
from pydantic import BaseModel, Field
from nicegui import ui
from gui.elements import GuiElements

class SelectionItem(BaseModel):
    name: str = Field(..., description="The name that will be displayed on the breadcrumbs")
    id: str | None = Field(..., description="The id of the item.  This will be used to identify the item in the system.")
    kind: str = Field(..., description="The kind of item.  This will be used to identify the item in the system.")

def update_breadcrumbs(gui_elements: GuiElements, selection: list[SelectionItem]):
    """
    Update the breadcrumbs based on a new selection.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The new selection to update the breadcrumbs with.
    """
    breadcrumbs = gui_elements.get("breadcrumbs")
    breadcrumbs.clear()
    with breadcrumbs:
        ui.button('', icon='home').props('rounded').on_click(lambda _, new_sel=[] : change_selection(gui_elements, selection, new_sel))
        for i,item in enumerate(selection):
            new_sel = selection[:i+1]
            ui.button(item.name).props('rounded').on_click(lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))

def update_details(gui_elements: GuiElements, selection: list[SelectionItem]):
    from gui.home import view_home
    from gui.style import view_style
    from gui.series import view_series
    from gui.character import view_character
    from gui.issue import view_issue
    from gui.scene import view_scene
    from gui.panel import view_panel
    from gui.cover import view_cover
    logger.debug(f"SELECTION:{selection}")

    if selection == []:
        return view_home(gui_elements, selection)

    kind = selection[-1].kind
    
    if kind == 'style':
        view_style(gui_elements, selection)
    elif kind == 'series':
        view_series(gui_elements, selection)
    elif kind == 'character':
        view_character(gui_elements, selection)
    elif kind == "issue":
        view_issue(gui_elements, selection)
    elif kind == "scene":
        view_scene(gui_elements, selection)
    elif kind == "panel":
        view_panel(gui_elements, selection)
    elif kind == "cover":
        view_cover(gui_elements, selection)
    else:
        # Handle other cases or return a default message
        details = gui_elements.get("details")
        details.clear()
        with details:
            ui.markdown(f"No description available for this item. {kind}")
            return    



def change_selection(gui_elements: GuiElements, old: list[SelectionItem], new:list[SelectionItem]):
    if old == new:
        return
    chat_history = gui_elements.get("history")
    details = gui_elements.get("details")
    chat_history.clear()
    details.clear()
    # TODO: Reset the agent memory
    update_breadcrumbs(gui_elements, new)
    update_details(gui_elements, new)
    # TODO: Select the correct agent

