import os
from loguru import logger
from nicegui import ui
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection
from gui.markdown import markdown, header
from gui.elements import GuiElements
from models.series import Series
from style.comic import ComicStyle
from helpers.constants import COMICS_FOLDER, STYLES_FOLDER

def view_all_styles(gui_elements, selection): 
    logger.debug("view_all_styles")
    with gui_elements.get("details"):
        styles = ComicStyle.read_all()
        with init_cardwall():
            for style in styles:
                w = 200
                logger.debug(f"style: {style.id}")
                tailwind = f'mb-2 p-2 h-25 bg-blue-100 dark:bg-gray-800 break-inside-avoid text-gray-900 dark:text-gray-300'
                card = ui.card().classes(tailwind).style('aspect-ratio: 1/1')
                with card:
                    sel_itm = SelectionItem(name=style.name, id=style.id, kind='style')
                    new_sel = [s for s in selection]+[sel_itm]
                    image = style.image_filepath()
                    header(style.id.replace("-", " ").title(),4)
                    if image:
                        ui.image(source=image).style('top-padding: 0; bottom-padding:0')
                    
                # Fix lambda by creating a closure with the current value of new_sel
                card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new_sel))





def view_all_series(gui_elements, selection):
    logger.debug("view_all_series")
    seriess = read_all_series()
    with gui_elements.get("details"):
        cardwall = init_cardwall()
        with cardwall:
            for series in seriess:
                w = 200
                tailwind = f'mb-2 p-2 h-25 bg-blue-100 dark:bg-gray-800 break-inside-avoid text-gray-900 dark:text-gray-300'
                card = ui.card().classes(tailwind).style('aspect-ratio: 2/3')
                image = series.image_filepath()
                with card:
                    # Fix lambda by creating a closure with the current value of series
                    if image:
                        ui.image(source=image)
                    else:
                        header(series.id.replace("-", " ").title(),2)
                        header("No image available",5)
                    card.on('click', lambda _, series_id=series.id: change_selection(gui_elements, selection, [SelectionItem(name=series_id.replace("-", " ").title(), id=series_id, kind='series')]))


def read_all_series() -> list[Series]:
    """
    Read all styles from the styles folder.
    """
    seriess = []
    for item in os.listdir(COMICS_FOLDER):
        # if it is a directory then it is a series
        if os.path.isdir(os.path.join(COMICS_FOLDER, item)):
            series = Series.read(id=item)
            if series:
                seriess.append(series)
    return seriess



def view_home(gui_elements: GuiElements, selection):
    from gui.messaging import new_item_messager
    with gui_elements.get("details"):
        new_item_messager(gui_elements, selection, "SERIES", "I would like to create a new comic book series.")
        view_all_series(gui_elements, selection)
        new_item_messager(gui_elements, selection, "STYLES", "I would like to create a new comic book style.")
        view_all_styles(gui_elements, selection)
