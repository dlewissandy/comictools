from loguru import logger
from nicegui import ui
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection

def panel_selector(gui_elements, selection, container, image_filepath, new_itm:SelectionItem):
    new_sel = [s for s in selection]+[new_itm]
    image_id = new_itm.id
    with container:
        if image_id is not None and image_id != "":
            if image_filepath:
                card = ui.card().classes('mb-2 p-2 bg-blue-100 break-inside-avoid')
                with card:
                    ui.image(source=image_filepath)
                card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))
            else:
                card = ui.card().classes('mb-2 p-2 h-[200px] bg-red-50 break-inside-avoid')
                with card:
                    ui.markdown(f"image {image_filepath} not found")
                card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))
        else:
            msg = f"No image has been selected."
            logger.error(msg)
            card = ui.card().classes('mb-2 p-2 h-[200px] bg-yellow-50 break-inside-avoid')
            with card:
                ui.markdown("**Click Here to select an image**")
            new_itm = SelectionItem(name=new_itm.name, id=None, kind=new_itm.kind)
            new_sel = [s for s in selection]+[new_itm]
            card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))

def view_panel(gui_elements, selection):
    """
    View the details of a panel.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The current selection.
    """
    pass