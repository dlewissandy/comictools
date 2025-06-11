from loguru import logger
from nicegui import ui
from gui.elements import init_cardwall
from gui.selection import SelectionItem
from gui.elements import markdown
from gui.panel import panel_selector
from models.panel import TitleBoardModel
from gui.state import APPState

def view_cover(state: APPState):
    """
    View the cover of a comic book issue.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    details = state.details
    logger.debug("view_cover")
    selection = state.selection
    location = selection[-1].id
    issue_id = selection[-2].id
    logger.debug(f"issue: {issue_id} cover: {location}")
    cover  = TitleBoardModel.read(issue=issue_id, location=location)
    with details:
        if cover:
            markdown(cover.format())
            markdown(f"# Image")
        cardwall = init_cardwall()
    panel_selector(state, cardwall, cover.image_filepath(), SelectionItem(name=f"{location} Cover Image".title(), id=cover.image, kind=f'{location}-cover'.replace(" ", "-")))

    