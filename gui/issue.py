import os
from loguru import logger
from nicegui import ui
from gui.cardwall import init_cardwall
from gui.selection import SelectionItem, change_selection
from gui.markdown import markdown
from models.issue import Issue
from style.comic import ComicStyle

def view_issue(breadcrumbs, details, chat_history, selection):
    """
    View the details of an issue.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The current selection.
    """
    issue_id = selection[-1].id
    issue = Issue.read(id=issue_id)
    if issue is None:
        details.clear()
        message = f"Issue with ID {issue_id} not found."
        with details:
            ui.markdown(message)
        return
    
    with details:
        markdown(issue.format(no_scenes=True, no_covers=True, no_style=True))
        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().style('flex: 0 0 20%'): 
                ui.markdown("# Style")
                style = ComicStyle.read(id=issue.style)
                image = style.image_filepath()
                card = ui.card().classes('mb-2 p-2 bg-blue-100 break-inside-avoid w-full')
                with card:
                    ui.markdown(style.id.replace("-", " ").title()).classes('text-center bold').style('top-padding: 0; bottom-padding:0')
                    if image:
                        ui.image(source=image).style('top-padding: 0; bottom-padding:0')
                    new_itm = SelectionItem(name="Pick Style", id=style.id, kind='pick_style')
                    new_sel = [s for s in selection]+[new_itm]
                    card.on('click', lambda _, new_sel=new_sel: change_selection(breadcrumbs, details, chat_history, selection, new=new_sel)) 
            with ui.column().style('flex: 0 0 80%'):
                ui.markdown("# Covers")
                if not issue.cover or issue.cover == {}:
                    ui.markdown("No covers available for this issue.")
                else:
                    with init_cardwall(4):
                        for cover_type,image_id in issue.cover.items():
                            filepath = os.path.join(issue.path(), "covers", cover_type, "images", f"{image_id}.jpg")
                            if os.path.exists(filepath):
                                card = ui.card().classes('mb-2 p-2 bg-blue-100 break-inside-avoid')
                                with card:
                                    ui.label(f"{cover_type.title()} Cover").classes('text-center bold')
                                    ui.image(source=filepath)
                                new_itm = SelectionItem(name=f"{cover_type.title()} Cover", id=cover_type, kind='cover')
                                new_sel = [s for s in selection]+[new_itm]
                                card.on('click', lambda _, new_sel=new_sel: change_selection(breadcrumbs, details, chat_history, selection, new=new_sel))
                            else:
                                logger.error(f"Cover file {filepath} does not exist.")
                                with ui.card().classes('mb-2 p-2 bg-red-100 break-inside-avoid'):
                                    ui.markdown(f"Cover file {filepath} does not exist.")
            
        ui.markdown("# Scenes")
        scenes = issue.get_scenes()
        if not scenes or scenes == []:
            ui.markdown("No scenes available for this issue.")
        else:
            with init_cardwall():
                for i,scene in enumerate(scenes):
                    card = ui.card().classes('mb-2 p-2 bg-blue-100 break-inside-avoid')
                    with card:
                        markdown(f"## Scene {i+1}\n\n{scene.story}")
                    sel_itm = SelectionItem(name=f"scene {i+1}", id=scene.id, kind='scene')
                    new_sel = [s for s in selection]+[sel_itm]
                    card.on('click', lambda _, new_sel=new_sel: change_selection(breadcrumbs, details, chat_history, selection, new=new_sel))
                        
        