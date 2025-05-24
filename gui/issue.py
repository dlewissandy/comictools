import os
from loguru import logger
from nicegui import ui
from gui.elements import init_cardwall
from gui.selection import SelectionItem, change_selection
from gui.elements import markdown, header, image_field_editor
from gui.constants import TAILWIND_CARD
from models.issue import Issue
from models.panel import CoverLocation, TitleBoardModel
from style.comic import ComicStyle

def cover_selectors(state, ):
    from gui.messaging import post_user_message
    selection = state.get("selection")
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
                    card.on('click', lambda _, message=message: post_user_message(state, message))
                    continue
            # We have a cover, but does it exist?
            cover = TitleBoardModel.read(issue=issue_id, location=location)
            if cover is None:
                # The cover is specified, but it does not exist!
                card = ui.card().classes(TAILWIND_CARD).style(f'aspect-ratio: {aspect}')
                with card:
                    ui.markdown(f"{cover_id} could not be found!\n**Click Here to create a {location_name} Cover**")
                    message = f"I would like to create a {location_name} cover for this issue."
                    card.on('click', lambda _, message=message: post_user_message(state, message))
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
            card.on('click', lambda _, new_sel=new_sel: change_selection(state, new=new_sel))
       
 
def view_issue(state):
    """
    View the details of an issue.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    from gui.messaging import new_item_messager, post_user_message
    selection = state.get("selection")
    issue_id = selection[-1].id
    issue = Issue.read(id=issue_id)
    details = state.get("details")
    if issue is None:
        details.clear()
        message = f"Issue with ID {issue_id} not found."
        with details:
            ui.markdown(message)
        return
    
    if issue.style is None:
        style = None
    else:
        style = ComicStyle.read(id=issue.style) if issue.style else None
    
    with details:
        header(f"ISSUE {issue.issue_number}: {issue.issue_title}", 0)

        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().classes('w-3/4'):
                header("Attributes", 2)
                with ui.grid(rows=5, columns=3).style('grid-template-columns: auto auto auto;'):
                    ui.button(icon='edit').classes('text-base rounded-md').style('font-size: 0.75em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit').on('click', lambda _: post_user_message(state, "I would like to edit the issue's publication date."))
                    header("issue date",4)
                    ui.label(("" if issue.issue_date is None else issue.issue_date).rjust(30))
                    
                    ui.button(icon='edit').classes('text-base rounded-md').style('font-size: 0.75em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit').on('click', lambda _: post_user_message(state, "I would like to edit the issue's writer."))
                    header("writer",4)
                    ui.label(("" if issue.writer is None else issue.issue_date).rjust(30))
                    
                    ui.button(icon='edit').classes('text-base rounded-md').style('font-size: 0.75em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit').on('click', lambda _: post_user_message(state, "I would like to edit the issue's artist."))
                    header("artist",4)
                    ui.label(("" if issue.artist is None else issue.artist).rjust(30))

                    ui.button(icon='edit').classes('text-base rounded-md').style('font-size: 0.75em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit').on('click', lambda _: post_user_message(state, "I would like to edit the issue's colorist."))
                    header("colorist",4)
                    ui.label(("" if issue.colorist is None else issue.colorist).rjust(30))

                    ui.button(icon='edit').classes('text-base rounded-md').style('font-size: 0.75em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit').on('click', lambda _: post_user_message(state, "I would like to edit the issue's creative minds."))
                    header("creative minds",4)
                    ui.label(("" if issue.creative_minds is None else issue.creative_minds).rjust(30))

            with ui.column().classes('w-1/4'):
                image_field_editor(
                    state, "pick-style", "Style", 
                    lambda: style.name if style else None, 
                    lambda: style.id if style else None, 
                    lambda: style.image_filepath() if style else None
                )

        new_item_messager(state, "Covers","I would like to create a new cover for this issue.")
        cover_selectors(state)

            
        new_item_messager(state, "Scenes","I would like to create a new scene for this issue.")
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
                    card.on('click', lambda _, new_sel=new_sel: change_selection(state, new=new_sel))
                        
        