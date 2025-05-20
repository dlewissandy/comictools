from pydantic import BaseModel, Field
from nicegui import ui

class SelectionItem(BaseModel):
    name: str = Field(..., description="The name that will be displayed on the breadcrumbs")
    id: str = Field(..., description="The id of the item.  This will be used to identify the item in the system.")
    kind: str = Field(..., description="The kind of item.  This will be used to identify the item in the system.")

def update_breadcrumbs(breadcrumbs, details, chat_history, selection):
    """
    Update the breadcrumbs based on a new selection.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The new selection to update the breadcrumbs with.
    """
    breadcrumbs.clear()
    with breadcrumbs:
        ui.button('', icon='home').props('rounded').on_click(lambda _ : change_selection(breadcrumbs, details, chat_history, selection, []))
        for i,item in enumerate(selection):
            ui.button(item.name).props('rounded').on_click(change_selection(breadcrumbs, details, chat_history, selection, selection[:i+1]))

def update_details(breadcrumbs, details, chat_history, selection):
    from gui.home import view_home
    from gui.style import view_style
    from gui.series import view_series
    from gui.character import view_character
    from gui.issue import view_issue
    from gui.scene import view_scene
    from gui.panel import view_panel

    if selection == []:
        return view_home(breadcrumbs, details, chat_history, selection)

    kind = selection[-1].kind
    
    if kind == 'style':
        view_style(breadcrumbs, details, chat_history, selection)
    elif kind == 'series':
        view_series(breadcrumbs, details, chat_history, selection)
    elif kind == 'character':
        view_character(breadcrumbs, details, chat_history, selection)
    elif kind == "issue":
        view_issue(breadcrumbs, details, chat_history, selection)
    elif kind == "scene":
        view_scene(breadcrumbs, details, chat_history, selection)
    elif kind == "panel":
        view_panel(breadcrumbs, details, chat_history, selection)
    else:
        # Handle other cases or return a default message
        details.clear()
        with details:
            ui.markdown(f"No description available for this item. {kind}")
            return    



def change_selection(breadcrumbs, details, chat_history, old, new):
    if old == new:
        return
    chat_history.clear()
    details.clear()
    # TODO: Reset the agent memory
    update_breadcrumbs(breadcrumbs, details, chat_history, new)
    update_details(breadcrumbs, details, chat_history, new)
    # TODO: Select the correct agent

