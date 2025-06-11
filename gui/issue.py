import os
from loguru import logger
from nicegui import ui
from gui.elements import markdown, header, image_field_editor, view_all_instances, markdown_field_editor, Attribute, view_attributes
from models.issue import Issue
from style.comic import ComicStyle
from gui.state import APPState

def view_issue(state:APPState):
    """
    View the details of an issue.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    from gui.messaging import new_item_messager, post_user_message
    selection = state.selection
    issue_id = selection[-1].id
    issue = Issue.read(id=issue_id)
    details = state.details
    if issue is None:
        state.clear_details()
        message = f"Issue with ID {issue_id} not found."
        with details:
            ui.markdown(message)
        return
    
    if issue.style is None:
        style = None
    else:
        style = ComicStyle.read(id=issue.style) if issue.style else None
    
    with details:
        header(f"ISSUE {issue.issue_number}: {issue.title}", 0)
        
        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().classes('w-3/4'):
                markdown_field_editor(state, "Story", issue.story)
                

            with ui.column().classes('w-1/4'):
                image_field_editor(
                    state, "pick-style", "Style", 
                    lambda: style.name if style else None, 
                    lambda: style.id if style else None, 
                    lambda: style.image_filepath() if style else None
                )

        view_attributes(
                    state = state,
                    caption="Attributes",
                    attributes = [
                        Attribute(caption="publication date", get_value =lambda: issue.publication_date),
                        Attribute(caption="price", get_value =lambda: issue.price),
                        Attribute(caption="writer", get_value=lambda: issue.writer),
                        Attribute(caption="artist", get_value=lambda: issue.artist),
                        Attribute(caption="colorist", get_value=lambda: issue.colorist),
                        Attribute(caption="creative minds", get_value=lambda: issue.creative_minds)
                    ]
                )

        new_item_messager(state, "Covers","I would like to create a new cover for this issue.")
        view_all_instances(
            state=state,
            get_instances = issue.get_covers,
            kind=lambda cover: cover.location.replace("_", "-").lower() + "-cover",
            get_name=lambda _,cover: f"{cover.location.replace('_', ' ').title()} Cover",
            aspect_ratio="6/9"
        )

            
        new_item_messager(state, "Scenes","I would like to create a new scene for this issue.")
        view_all_instances(
            state=state,
            get_instances = issue.get_scenes,
            kind="scene",
            aspect_ratio="16/9",
            get_name=lambda i,_: f"Scene {i+1}",
            get_markdown=lambda scene: scene.story,
            number_of_columns=3
        )                
        