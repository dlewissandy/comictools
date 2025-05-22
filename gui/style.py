from loguru import logger
from nicegui import ui
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection
from gui.markdown import markdown, header
from style.comic import ComicStyle
from gui.constants import TAILWIND_CARD

def style_selector(gui_elements, selection, cardwall, style_id):
    """
    Create a style selector card.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The current selection of items.
        cardwall: The cardwall UI element.
        new_sel: The new selection item to be added.
    """
    new_itm = SelectionItem(name=f"Style picker", id=style_id, kind='style-picker')
    new_sel = [s for s in selection]+[new_itm]
    with cardwall:
        if style_id is not None and style_id != "":
            style = ComicStyle.read(id=style_id)
            if style is None:
                card = ui.card().classes(TAILWIND_CARD)
                with card:
                    header("Not Yet Selected", 4)
                card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))
                return
            image_filepath = style.image_filepath()
            if image_filepath is None:
                card = ui.card().classes(TAILWIND_CARD)
            else:
                card = ui.card().classes(TAILWIND_CARD)
            with card:
                header(style.id.replace("-", " ").title(), 4)
                if image_filepath:
                    ui.image(source=image_filepath).style('top-padding: 0; bottom-padding:0')  
                card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))
            return
        else:
            msg = f"No style has been selected."
            logger.error(msg)
            card = ui.card().classes(TAILWIND_CARD)
            with card:
                header("Not Yet Selected", 4)
            new_itm = SelectionItem(name=new_itm.name, id=None, kind=new_itm.kind)
            new_sel = [s for s in selection]+[new_itm]
            card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))

def view_style(gui_elements, selection):
    style = ComicStyle.read(id=selection[-1].id)
    details = gui_elements.get("details")
    with details:
        markdown(style.format())
        
        init_cardwall()