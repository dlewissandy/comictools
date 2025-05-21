import os
from loguru import logger
from nicegui import ui
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection
from gui.markdown import markdown
from models.series import Series
from style.comic import ComicStyle
from helpers.constants import COMICS_FOLDER, STYLES_FOLDER

def view_all_styles(breadcrumbs, details, chat_history, selection): 
    logger.debug("view_all_styles")
    with details:
        styles = ComicStyle.read_all()
        logger.debug(f"styles: {styles}")
        with init_cardwall():
            for style in styles:
                w = 200
                logger.debug(f"style: {style.id}")
                tailwind = f'mb-2 p-2 h-25 bg-blue-100 break-inside-avoid'
                card = ui.card().classes(tailwind)
                with card:
                    sel_itm = SelectionItem(name=style.name, id=style.id, kind='style')
                    new_sel = [s for s in selection]+[sel_itm]
                    image = style.image_filepath()
                    ui.markdown(style.id.replace("-", " ").title()).classes('text-center bold').style('top-padding: 0; bottom-padding:0')
                    if image:
                        ui.image(source=image).style('top-padding: 0; bottom-padding:0')
                    
                # Fix lambda by creating a closure with the current value of new_sel
                card.on('click', lambda _, new_sel=new_sel: change_selection(breadcrumbs, details, chat_history, selection, new_sel))

def view_all_series(breadcrumbs, details, chat_history, selection):
    logger.debug("view_all_series")
    seriess = read_all_series()
    with details:
        cardwall = init_cardwall()
        with cardwall:
            for series in seriess:
                w = 200
                tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
                card = ui.card().classes(tailwind)
                image = series.image_filepath()
                with card:
                    # Fix lambda by creating a closure with the current value of series
                    if image:
                        ui.image(source=image)
                    else:
                        markdown(f"### {series.id.replace("-", " ").title()}")
                card.on('click', lambda _, series_id=series.id: change_selection(breadcrumbs, details, chat_history, selection, [SelectionItem(name=series_id.replace("-", " ").title(), id=series_id, kind='series')]))


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



def view_home(breadcrumbs, details, chat_history, selection):
    with details:
        ui.markdown("# SERIES")
        view_all_series(breadcrumbs, details, chat_history, selection)
        ui.markdown("# STYLES")
        view_all_styles(breadcrumbs, details, chat_history, selection)
