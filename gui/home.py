import os
from loguru import logger
from nicegui import ui
from gui.elements import init_cardwall
from gui.constants import TAILWIND_CARD
from gui.selection import SelectionItem, change_selection
from gui.elements import markdown, header, view_all_instances
from gui.state import GUIState
from models.series import Series
from models.publisher import Publisher
from style.comic import ComicStyle
from helpers.constants import COMICS_FOLDER, STYLES_FOLDER

def view_all_styles(state): 
    logger.debug("view_all_styles")
    selection = state.get("selection")
    with state.get("details"):
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
                card.on('click', lambda _, new_sel=new_sel: change_selection(state, new_sel))


# def view_all_publishers(state): 
#     logger.debug("view_all_publishers")
#     selection = state.get("selection")
#     with state.get("details"):
#         pubs = Publisher.read_all()
#         with init_cardwall():
#             for pub in pubs:
#                 name = pub.name.replace("-", " ").title()
#                 id = pub.name.replace(" ", "-").lower()
#                 logger.debug(f"publisher: {pub.id}")
#                 card = ui.card().classes(TAILWIND_CARD).style('aspect-ratio: 1/1')
#                 with card:
#                     sel_itm = SelectionItem(name=name, id=id, kind='publisher')
#                     new_sel = [s for s in selection]+[sel_itm]
#                     image = pub.image_filepath()
#                     header(name,4)
#                     if image:
#                         ui.image(source=image).style('top-padding: 0; bottom-padding:0')
                    
#                 # Fix lambda by creating a closure with the current value of new_sel
#                 card.on('click', lambda _, new_sel=new_sel: change_selection(state, new_sel))




def view_all_series(state):
    logger.debug("view_all_series")
    seriess = read_all_series()
    with state.get("details"):
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
                    card.on('click', lambda _, series_id=series.id: change_selection(state, [SelectionItem(name=series_id.replace("-", " ").title(), id=series_id, kind='series')]))


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



def view_home(state: GUIState):
    from gui.messaging import new_item_messager
    with state.get("details"):
        new_item_messager(state, "PUBLISHERS", "I would like to create a new comic book publisher.")
        view_all_instances(state, Publisher.read_all, "publisher")
        new_item_messager(state, "SERIES", "I would like to create a new comic book series.")
        view_all_instances(state, Series.read_all, "series", aspect_ratio="16/27")
        new_item_messager(state, "STYLES", "I would like to create a new comic book style.")
        view_all_instances(state,ComicStyle.read_all, aspect_ratio="1/1", kind="style")
        