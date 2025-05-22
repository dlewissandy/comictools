import os
from loguru import logger
from models.series import Series
from gui.cardwall import init_cardwall
from gui.markdown import markdown, header
from gui.selection import SelectionItem, change_selection
from gui.constants import TAILWIND_CARD
from nicegui import ui

def view_all_issues(gui_elements, selection):
    from gui.messaging import post_user_message
    logger.debug("view_all_issues")
    series = Series.read(id=selection[-1].id)
    issues = series.get_issues()
    
    # sort the issues by issue number
    issues_list = list(issues.values())
    issues_list.sort(key=lambda x: x.issue_number)
    details = gui_elements.get("details")
    with details:
        with ui.element().classes('grid grid-cols-4 gap-2 w-full'):
            for issue in issues_list:
                w = 200
                image = None
                if issue.cover and issue.cover !={}:
                    image = issue.cover.get("front")
                card = ui.card().classes(TAILWIND_CARD).style('aspect-ratio: 2/3')
                with card:
                    if image:
                        filepath = os.path.join(issue.path(), "covers", "front", "images", f"{image}.jpg")
                        if os.path.exists(filepath):
                            ui.image(source=filepath)
                        else:
                            logger.error(f"Cover file {filepath} does not exist.")
                            ui.markdown(f"Cover file {filepath} does not exist.")
                    else:
                        ui.label(f"{issue.issue_title} ({issue.issue_number})").classes('text-center')
                    new_itm = SelectionItem(name=issue.issue_title, id=issue.id, kind='issue')
                    new_sel = [s for s in selection]+[new_itm]


                card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))

def view_all_characters(gui_elements, selection):
    from gui.messaging import post_user_message
    logger.debug("view_all_characters")
    series_id = selection[-1].id
    series = Series.read(id=series_id)
    name = series.id.replace("-", " ").title()
    characters = series.get_characters()
    details = gui_elements.get("details")
    with details:
        with init_cardwall():
            for character in characters.values():
                name = character.name
                variant = character.variant if character.variant else 'base'
                card = ui.card().classes(TAILWIND_CARD).style('aspect-ratio: 3/2.75')
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
                    new_itm = SelectionItem(name=f"{name} ({variant})", id=character.id, kind='character')
                    new_sel= [s for s in selection]+[new_itm]
                    card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new = new_sel))


def view_series(gui_elements, selection):
    logger.debug("view_series")
    from gui.messaging import new_item_messager
    series = Series.read(id=selection[-1].id)
    name = series.id.replace("-", " ").title()
    details = gui_elements.get("details")
    details.clear()
    with details:
        header(name, 0)
        markdown(series.description)
        new_item_messager(gui_elements, selection, "ISSUES", f"I would like to create a new issue of the {series.series_title} series.")
        view_all_issues(gui_elements, selection)
        new_item_messager(gui_elements, selection, "CHARACTER", f"I would like to create a new character for the {series.series_title} series.")
        view_all_characters(gui_elements, selection)
        