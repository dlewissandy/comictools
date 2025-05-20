import os
from loguru import logger
from nicegui import ui
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection
from models.series import Series
from style.comic import ComicStyle
from helpers.constants import COMICS_FOLDER, STYLES_FOLDER

def read_all_styles() -> list[ComicStyle]:
    """
    Read all styles from the styles folder.
    """
    styles = []
    for item in os.listdir(STYLES_FOLDER):
        if item.endswith(".json"):
            basename = os.path.splitext(item)[0]
            style = ComicStyle.read(id=basename)
            if style:
                styles.append(style)
    return styles


def view_all_styles(breadcrumbs, details, chat_history, selection): 
    logger.debug("view_all_styles")
    with details:
        styles = read_all_styles()
        with init_cardwall():
            for style in styles:
                w = 200
                logger.debug(f"style: {style.id}")
                tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
                card = ui.card().classes(tailwind)
                with card:
                    sel_itm = SelectionItem(name=style.name, id=style.id, kind='style')
                    new_sel = [s for s in selection]+[sel_itm]
                    ui.label(style.id.replace("-", " ").title()).classes('text-center')
                card.on('click', lambda _: change_selection(breadcrumbs, details, chat_history, selection, new_sel))

def view_all_series(breadcrumbs, details, chat_history, selection):
    logger.debug("view_all_series")
    seriess = read_all_series()
    with details:
        cardwall = init_cardwall()
        with cardwall:
            for series in seriess:
                w = 200
                logger.debug(f"series: {series.id}")
                tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
                card = ui.card().classes(tailwind)
                with card:
                    ui.label(series.id.replace("-", " ").title()).classes('text-center')
                    card.on('click', lambda _: change_selection(breadcrumbs, details, chat_history, selection, [SelectionItem(name=series.id.replace("-", " ").title(), id=series.id, kind='series')]))


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
