import os
from loguru import logger
from nicegui import ui
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection
from gui.markdown import markdown, header
from gui.constants import TAILWIND_CARD
from models.issue import Issue
from models.panel import CoverLocation, TitleBoardModel
from style.comic import ComicStyle

def cover_selectors(gui_elements, selection):
    from gui.messaging import post_user_message
    issue_id = selection[-1].id
    issue = Issue.read(id=selection[-1].id)
    container = ui.element().classes('grid grid-cols-4 gap-2 w-full')
    aspect = "6/9"
    for location_enum in CoverLocation.__members__.values():
        location = location_enum.name
        location_name = location.replace("_", " ").title()
        location_id = location.replace("_", "-").lower()
        cover_id = issue.cover.get(location_id, None)
        with container:
            if cover_id is None or cover_id == "":
                # There is no cover.   Create a yellow card with instruction on how
                # to create a cover.
                card = ui.card().classes(TAILWIND_CARD).style(f'aspect-ratio: {aspect}')

                with card:
                    header(location_name, 3).style('color: grey')
                    message = f"I would like to create a {location_name} cover for this issue."
                    card.on('click', lambda _, message=message: post_user_message(gui_elements, selection, message))
                    continue
            # We have a cover, but does it exist?
            cover = TitleBoardModel.read(issue=issue_id, location=location)
            if cover is None:
                # The cover is specified, but it does not exist!
                card = ui.card().classes('mb-2 p-2 bg-red-50 break-inside-avoid').style(f'aspect-ratio: {aspect}')
                with card:
                    ui.markdown(f"{cover_id} could not be found!\n**Click Here to create a {location_name} Cover**")
                    message = f"I would like to create a {location_name} cover for this issue."
                    card.on('click', lambda _, message=message: post_user_message(gui_elements, selection, message))
                    continue
            image_filepath = cover.image_filepath()
            if not image_filepath or not os.path.exists(image_filepath):
                # The cover exists, but it doesn't have a rendered image
                card = ui.card().classes(TAILWIND_CARD).style(f'aspect-ratio: {aspect}')
                with card:
                    markdown(f"# {location_name}\n{cover.foreground}")
            else:
                # Cover exists and has a rendered image
                card = ui.card().classes(TAILWIND_CARD).style(f'aspect-ratio: {aspect}')
                with card:
                    ui.image(source=image_filepath)

            new_itm = SelectionItem(name=f"{location_name} Cover", id=location_id, kind='cover')
            new_sel = [s for s in selection]+[new_itm]
            card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))
       
 
def view_issue(gui_elements, selection):
    """
    View the details of an issue.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The current selection.
    """
    from gui.messaging import new_item_messager, post_user_message
    issue_id = selection[-1].id
    issue = Issue.read(id=issue_id)
    details = gui_elements.get("details")
    if issue is None:
        details.clear()
        message = f"Issue with ID {issue_id} not found."
        with details:
            ui.markdown(message)
        return
    
    with details:
        header(f"ISSUE {issue.issue_number}: {issue.issue_title}", 0)
        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().style('flex: 0 0 20%'): 
                header("Style")
                style = ComicStyle.read(id=issue.style)
                image = style.image_filepath()
                card = ui.card().classes(TAILWIND_CARD)
                with card:
                    ui.markdown(style.id.replace("-", " ").title()).classes('text-center bold').style('top-padding: 0; bottom-padding:0')
                    if image:
                        ui.image(source=image).style('top-padding: 0; bottom-padding:0')
                    new_itm = SelectionItem(name="Pick Style", id=style.id, kind='pick_style')
                    new_sel = [s for s in selection]+[new_itm]
                    card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel)) 
            with ui.column().style('flex: 0 0 80%'):
                new_item_messager(gui_elements, selection, "Covers","I would like to create a new cover for this issue.")
                if not issue.cover or issue.cover == {}:
                    ui.markdown("No covers available for this issue.")
                else:
                    cover_selectors(gui_elements, selection)

            
        new_item_messager(gui_elements, selection, "Scenes","I would like to create a new scene for this issue.")
        scenes = issue.get_scenes()
        if not scenes or scenes == []:
            ui.markdown("No scenes available for this issue.")
        else:
            with init_cardwall(3):
                for i,scene in enumerate(scenes):
                    card = ui.card().classes(TAILWIND_CARD)
                    with card:
                        markdown(f"## Scene {i+1}\n\n{scene.story}")
                    sel_itm = SelectionItem(name=f"scene {i+1}", id=scene.id, kind='scene')
                    new_sel = [s for s in selection]+[sel_itm]
                    card.on('click', lambda _, new_sel=new_sel: change_selection(gui_elements, selection, new=new_sel))
                        
        