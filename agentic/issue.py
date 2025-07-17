from typing import Tuple, Optional, List
from agentic.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool, RunContextWrapper
from gui.state import APPState
from schema import Cover, CoverLocation, FrameLayout, CharacterRef, Issue, InsertionLocation, BeforeFirst, Before, After, AfterLast, SceneModel
from gui.selection import SelectionItem, SelectedKind
from storage.generic import GenericStorage
from loguru import logger
from agentic.instructions import instructions

from agentic.tools import (
    read_context,
    read_issue,
    read_all_covers,
    read_cover,
    read_all_scenes,
    read_all_characters,
    read_style,
    delete_issue,
    delete_character,
    normalize_id,
    normalize_name
)

def _insertion_location_to_index(insertion_location: InsertionLocation) -> int:
    if isinstance(insertion_location, BeforeFirst):
        return 1
    elif isinstance(insertion_location, AfterLast):
        return -1
    elif isinstance(insertion_location, Before):
        return insertion_location.index - 1
    elif isinstance(insertion_location, After):
        return insertion_location.index - 1
    else:
        raise ValueError(f"Unknown insertion location type: {type(insertion_location)}")


        


@function_tool
def create_cover(wrapper: RunContextWrapper[APPState], location: CoverLocation, characters: list[str], foreground: str, background: str) -> str:
    """
    Create a cover for the currently selected comic book issue.   Returns the status
    of the cover creation operation.

    Args:
        location (CoverLocation): The location where the cover should be created.
        characters (str): The names of the characters to include on the cover.  You should verify that these
            characters are in the series.   If they are not, but there are similar names, confirm with the user
            which character they meant.
        foreground (str): A detailed description of the visual elements in the foreground of the cover.
        background (str): A detailed description of the visual elements in the background of the cover.

    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    context = read_context(state)
    
    issue: Issue = context[0]
    issue_id = issue.issue_id
    series_id = issue.series_id

    for cover in issue.covers:
        if cover.location == location.value:
            cover.delete()

    cover = Cover(
        cover_id=normalize_id(location.value),
        location = location,
        issue_id=issue_id,
        series_id=series_id,
        character_references=[CharacterRef(series_id=series_id, character_id=char, variant_id="base") for char in characters],
        style_id=issue.style_id,
        aspect=FrameLayout.PORTRAIT,
        foreground=foreground,
        background=background,
        image=None,
        reference_images=[]

    )

    kind = SelectedKind.COVER
    name = normalize_name(kind)
    new_sel = SelectionItem(id=cover.cover_id, kind=kind, name=name,)
    cover.write()
    new_sel = state.selection + [new_sel]
    state.change_selection(new_sel)
    state.is_dirty = True
    
    return f"Cover created successfully for issue {issue.name} at location {location.name}."




@function_tool
def swap_scene_order(wrapper: RunContextWrapper[APPState], first_scene_number: int, second_scene_number: int) -> str:
    """
    Swap the order of two scenes in the currently selected comic book issue.
    
    Args:
        first_scene_number (int): The scene number of the first scene to swap.
        second_scene_number (int): The scene number of the second scene to swap.
    
    Returns:
        A status message indicating the result of the swap.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    issue_id = state.selection[-1].id
    series_id = state.selection[-2].id
    pk = {"issue_id": issue_id, "series_id": series_id}

    scenes: list[SceneModel] = storage.read_all_objects(cls=SceneModel, primary_key=pk, order_by="scene_number")

    if first_scene_number < 1 or first_scene_number > len(scenes):
        msg = f"First scene number {first_scene_number} is out of bounds for the current scenes list."
        raise ValueError(msg)
    if second_scene_number < 1 or second_scene_number > len(scenes):
        msg = f"Second scene number {second_scene_number} is out of bounds for the current scenes list."
        raise ValueError(msg)
    if first_scene_number == second_scene_number:
        msg = f"First scene number {first_scene_number} is the same as second scene number {second_scene_number}. No swap needed."
        raise ValueError(msg)

    # Swap the scenes
    first_scene = scenes[first_scene_number - 1]
    first_scene.scene_number = second_scene_number
    second_scene = scenes[second_scene_number - 1]
    second_scene.scene_number = first_scene_number

    # Update the scenes in storage
    storage.update_object(data=first_scene)
    storage.update_object(data=second_scene)

    state.is_dirty = True
    return f"Swapped scenes {first_scene_number} and {second_scene_number} successfully."

@function_tool
def create_scene(wrapper: RunContextWrapper[APPState], name: str, story: str, insertion_location: InsertionLocation) -> str:
    """
    Create a new scene for the currently selected comic book issue.   This will create a new scene
    with the default properties and add it to the issue at the specified insertion location.

    Args:
        name (str): The name of the new scene.   This should be a unique identifier for the scene, and
            should be 2-5 words long, and should only contain letters, numbers and spaces (e.g. 
            "Teapot ride", "Joey gets hungry", etc).
        story (str): The story for the new scene.   This should be detailed enough to guide the 
            creative team (authors, artists, etc.) in creating the storyboard and artwork for the scene.
            This includes information about the setting, characters involved, and key actions or events.
            It should not be a full script, but rather a summary of the scene's content and purpose.
            Consider the key information that is required to ensure that this scene can be written and 
            maintains the narrative flow of the comic book issue.
        insertion_location (InsertionLocation): The location where the new scene should be inserted.
            NOTE: LIST ELEMENTS ARE ONES-BASED, SO THE FIRST ELEMENT IS AT INDEX 1.

    Returns:
        A status message indicating the result of the scene creation.
    """
    state: APPState = wrapper.context
    logger.trace(f"inserting scene {name} at {InsertionLocation}")
    storage: GenericStorage = state.storage

    issue_id = state.selection[-1].id
    series_id = state.selection[-2].id
    pk = {"issue_id": issue_id, "series_id": series_id}

    issue: Issue = storage.read_object(cls=Issue, primary_key=pk)
    scenes: list[SceneModel] = storage.read_all_objects(cls=SceneModel, primary_key=pk, order_by="scene_number")

    scene = SceneModel(
        scene_id=normalize_id(name),
        issue_id=issue_id,
        series_id=series_id,
        name=name,
        story=story,
        style_id=issue.style_id,
        aspect=FrameLayout.PORTRAIT,
        scene_number=len(scenes),
    )
    storage.create_object(data=scene)

    i = _insertion_location_to_index(insertion_location)
    
    if i < 0:
        i = len(scenes)+ 1
    if i < 1 or i > len(scenes) + 1:
        return f"Insertion location {insertion_location} is out of bounds for the current scenes list."
    logger.debug(f"inserting scene {name} at {i}")
    scenes.insert(i-1, scene)

    # reindex the scenes to ensure they are in order
    for idx, sc in enumerate(scenes):
        sc.scene_number = idx+1
        storage.update_object(data=sc)
    
    
    state.is_dirty = True
    return f"Scene created successfully for issue {issue.name}."

issue_agent: Agent =  Agent(
        name="issue",
        instructions=instructions,
        model=LANGUAGE_MODEL,
        
        tools=[

            read_issue,
            read_all_scenes,
            read_all_covers,
            read_all_characters,
            read_style,

            delete_issue,

            swap_scene_order,

            create_scene,
            create_cover,
        ]
    )

