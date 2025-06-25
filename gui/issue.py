import os
from loguru import logger
from nicegui import ui
from gui.elements import (
    markdown, header, image_field_editor, view_all_instances, markdown_field_editor, Attribute, view_attributes, crud_button, post_user_message,
    CrudButtonKind
    )
from schema.issue import Issue
from schema.style.comic import ComicStyle
from gui.state import APPState
from gui.messaging import post_user_message
from gui.selection import SelectionItem, SelectedKind

def view_issue(state:APPState):
    """
    View the details of an issue.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    from gui.messaging import new_item_messager
    selection = state.selection
    storage = state.storage

    series_id = selection[-2].id if len(selection) > 1 else None
    issue_id = selection[-1].id
    
    issue = storage.find_issue(series_id=series_id, id=issue_id)
    details = state.details
    if issue is None:
        state.clear_details()
        message = f"Issue with ID {issue_id} not found."
        with details:
            ui.markdown(message)
        return
    
    if issue.style is None:
        logger.debug(f"Issue {issue.id} has no style set.")
        style = None
    else:
        style = storage.read_style(id=issue.style) if issue.style else None
        if style is None:
            logger.warning(f"Issue {issue.id} has style set to {issue.style} but style not found.")

    
    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"ISSUE {issue.issue_number}: {issue.name}", 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message("I would like to delete the current issue."))

        
        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().classes('w-3/4'):
                markdown_field_editor(state, "Story", issue.story)
                

            with ui.column().classes('w-1/4'):
                image_field_editor(
                    state=state, 
                    kind=SelectedKind.PICK_STYLE, 
                    get_caption=lambda: "Style", 
                    get_id =lambda: style.id if style else None, 
                    get_image_filepath=lambda: storage.find_style_image(style_id=style.id) if style else None
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
                    ],
                    individual_icons=False,
                )

        with ui.expansion( value=True ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state, "Covers","I would like to create a new cover for this issue.")
            view_all_instances(
                state=state,
                get_instances = lambda: storage.find_covers(series_id=series_id, issue_id=issue_id),
                get_image_locator=lambda _: storage.find_issue_image(series_id=series_id, issue_id=issue_id),
                kind=SelectedKind.COVER,
                get_name=lambda _,cover: f"{cover.location.replace('_', ' ').title()} Cover",
                aspect_ratio="6/9"
            )

        with ui.expansion( value=True ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                new_item_messager(state, "Scenes","I would like to create a new scene for this issue.")
            view_all_instances(
                state=state,
                get_instances = lambda: storage.find_scenes(series_id=series_id, issue_id=issue_id),
                get_image_locator=lambda scene: storage.find_scene_image(series_id=series_id, issue_id=issue_id, scene_id=scene.id),
                kind=SelectedKind.SCENE,
                aspect_ratio="16/9",
                get_name=lambda i,scene: f"Scene {i+1}:{scene.name}",
                get_markdown=lambda scene: scene.story,
                number_of_columns=3
            )                
        