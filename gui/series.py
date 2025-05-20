import os
from loguru import logger
from models.series import Series
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection
from nicegui import ui

def view_all_issues(breadcrumbs, details, chat_history, selection):
    logger.debug("view_all_issues")
    series = Series.read(id=series)
    issues = series.get_issues()
    with details:
        init_cardwall()
        for issue in issues.values():
            w = 200
            tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
            card = ui.card().classes(tailwind)
            with card:
                new_itm = SelectionItem(name=issue.issue_title, id=issue.id, kind='issue')
                new_selection = [s for s in selection]+[new_itm]
                ui.label(f"{issue.issue_title} ({issue.issue_number})").classes('text-center')
            card.on('click', lambda _: change_selection(breadcrumbs, details, chat_history, selection, new_selection))

def view_all_characters(breadcrumbs, details, chat_history, selection):
    logger.debug("view_all_characters")
    series_id = selection[-1].id
    series = Series.read(id=series_id)
    name = series.id.replace("-", " ").title()
    characters = series.get_characters()
    with details:
        init_cardwall()
        for character in characters.values():
            name = character.name
            variant = character.variant if character.variant else 'base'
            w = 200
            tailwind = f'mb-2 p-2 h-[{int(w/9*2)}] bg-blue-100 break-inside-avoid'
            
            card = ui.card().classes(tailwind)
            with card:
                ui.label(f"{name} ({variant})").classes('text-center')
                if character.image and character.image != {}:
                    if "vintage-four-color" in character.image:
                        image = character.image["vintage-four-color"]
                        style = "vintage-four-color"
                    else:
                        image = character.image.items()[0][1]
                        style = character.image.items()[0][0]
                    ui.image(source=os.path.join(character.path(), style, f"{image}.jpg"))
                card.on('click', lambda _: change_selection(breadcrumbs, details, chat_history, selection, [s for s in selection]+[SelectionItem(name=f"{name} ({variant})", id=character.id, kind='character')]))


def view_series(breadcrumbs, details, chat_history, selection):
    logger.debug("view_series")
    series = Series.read(id=selection[-1].id)
    name = series.id.replace("-", " ").title()

    details.clear()
    with details:
        ui.markdown(series.format())
        ui.markdown("# CHARACTERS")
#        view_all_characters(breadcrumbs, details, chat_history, selection)
        ui.markdown("# SCENES")
#        view_all_styles(init_cardwall())