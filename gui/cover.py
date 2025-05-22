from loguru import logger
from nicegui import ui
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection
from gui.markdown import markdown
from gui.panel import panel_selector
from models.panel import TitleBoardModel

def view_cover(gui_elements, selection):
    """
    View the cover of a comic book issue.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The current selection of items.
    """
    details = gui_elements.get("details")
    logger.debug("view_cover")
    location = selection[-1].id
    issue_id = selection[-2].id
    logger.debug(f"issue: {issue_id} cover: {location}")
    cover  = TitleBoardModel.read(issue=issue_id, location=location)
    with details:
        if cover:
            markdown(cover.format())
            markdown(f"# Image")
        cardwall = init_cardwall()
    panel_selector(gui_elements, selection, cardwall, cover.image_filepath(), SelectionItem(name=f"{location} Cover Image".title(), id=cover.image, kind=f'{location}-cover'.replace(" ", "-")))

    