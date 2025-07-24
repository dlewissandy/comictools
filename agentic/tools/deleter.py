from agents import function_tool, Tool, RunContextWrapper
from pydantic import BaseModel
from gui.state import APPState
from gui.selection import SelectionItem
from storage.generic import GenericStorage
from schema import (
    ComicStyle,
    Publisher,
    CharacterModel,
    CharacterVariant,
    Panel,
    Cover,
    CoverLocation,
    SceneModel,
    Series,
    Issue,
)

def deleter(wrapper: RunContextWrapper[APPState], cls: BaseModel, primary_key: dict[str, str]) -> str:
    """
    Delete an object from the database.
    
    Args:
        wrapper: The run context wrapper containing the application state.
        cls: The class of the object to delete.
        primary_key: A dictionary containing the primary key fields and their values.
    
    Returns:
        A status message indicating the result of the deletion.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    selection: list[SelectionItem] = state.selection

    obj = storage.delete_object(cls=cls, primary_key=primary_key)
    if obj is None:
        return f"Object with primary key {primary_key} not found."

    if selection[-1].id == obj.id and selection[-1].kind == cls.__name__.lower():
        new_selection = selection[:-1]
        state.change_selection(new=new_selection)
    state.is_dirty = True
    return f"Deleted {cls.__name__} with primary key {primary_key}."

# -------------------------------------------------------------------------
# TOOLS TO DELETE OBJECTS FROM THE DATABASE
# -------------------------------------------------------------------------


@function_tool
def delete_publisher(wrapper: RunContextWrapper[APPState], publisher_id: str) -> str:
    """
    Delete a publisher by identifier.  You MUST ask for confirmation before using this tool.
    Args:
        publisher_id: The identifier of the publisher to delete.
    Returns:
        A status message indicating the result of the deletion.
    """
    pk = {"publisher_id": publisher_id}

    return deleter(wrapper=wrapper, cls=Publisher, primary_key=pk)

@function_tool
def delete_style(wrapper: RunContextWrapper[APPState], style_id: str) -> str:
    """
    Delete a comic style by name.   You MUST ask for confirmation before using this tool.
    
    Args:
        name: The name of the comic style to delete.
    Returns:
        A status message indicating the result of the deletion.
    """
    return deleter(wrapper=wrapper, cls=ComicStyle, primary_key={"style_id": style_id})
    
@function_tool
def delete_series(wrapper: RunContextWrapper[APPState], series_id: str) -> str:
    """
    Delete a comic series by name.   You MUST ask for confirmation before using this tool.
    
    Args:
        name: The name of the comic series to delete.
    
    Returns:
        A status message indicating the result of the deletion.
    """
    return deleter(wrapper=wrapper, cls=Series, primary_key={"series_id": series_id})

@function_tool
def delete_issue(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    Delete a comic book issue by its id.   You MUST ask for confirmation before using this tool.
    
    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The unique identifier for the issue
    
    Returns:
        A status message indicating the result of the deletion.
    """
    pk = {"series_id": series_id, "issue_id": issue_id}
    return deleter(wrapper=wrapper, cls=Issue, primary_key=pk)


@function_tool
def delete_scene(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str) -> str:
    """
    Delete a scene from a comic book issue.   You MUST ask for confirmation before using this tool.
    
    Args:
        scene_id: The identifier of the scene to delete.
    Returns:
        A status message indicating the result of the deletion.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    return deleter(wrapper=wrapper, cls=SceneModel, primary_key=pk)

@function_tool
def delete_panel(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str:
    """
    Delete a panel from a comic book scene.   You MUST ask for confirmation before using this tool.
    
    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The identifier of the issue the scene belongs to.
        scene_id: The identifier of the scene the panel belongs to.
        panel_id: The identifier of the panel to delete.
    
    Returns:
        A status message indicating the result of the deletion.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id}
    return deleter(wrapper=wrapper, cls=Panel, primary_key=pk)

@function_tool
def delete_cover(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, cover_id: str) -> str:
    """
    Delete a cover from a comic book issue.   You MUST ask for confirmation before using this tool.
    
    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The identifier of the issue the cover belongs to.
        location: The location of the cover (e.g., FRONT, BACK).
    
    Returns:
        A status message indicating the result of the deletion.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "cover_id": cover_id}
    return deleter(wrapper=wrapper, cls=Cover, primary_key=pk)

@function_tool
def delete_character(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str) -> str:
    """
    Delete a character from a comic book series.   You MUST ask for confirmation before using this tool.
    
    Args:
        series_id: The identifier of the series the character belongs to.
        character_id: The identifier of the character to delete.
    
    Returns:
        A status message indicating the result of the deletion.
    """
    pk = {"series_id": series_id, "character_id": character_id}
    return deleter(wrapper=wrapper, cls=CharacterModel, primary_key=pk)

@function_tool
def delete_character_variant(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str) -> str:
    """
    Delete a character variant from a comic book series.   You MUST ask for confirmation before using this tool.
    
    Args:
        series_id: The identifier of the series the character belongs to.
        character_id: The identifier of the character the variant belongs to.
        variant_id: The identifier of the variant to delete.
    
    Returns:
        A status message indicating the result of the deletion.
    """
    pk = {"series_id": series_id, "character_id": character_id, "variant_id": variant_id}
    return deleter(wrapper=wrapper, cls=CharacterVariant, primary_key=pk)   