from loguru import logger
from agents import function_tool
from typing import Callable, Optional, Union
from pydantic import BaseModel
from gui.state import APPState
from schema import (
    ComicStyle,
    Publisher,
    CharacterModel,
    CharacterVariant,
    Panel,
    TitleBoardModel,
    CoverLocation,
    SceneModel,
    Series,
    Issue,
)
from helpers.image import load_b64_image

class ImageLoadResult(BaseModel):
    success: bool
    warnings: list[str]
    b64_images: list[str]


def normalize_name(name: str) -> str:
    """
    Normalize a name by converting it to a string, and then 
    replacing the spaces with dashes.
    
    Args:
        name: The name to normalize.
    
    Returns:
        The normalized name.
    """
    return str(name).replace("-", " ").title()

def normalize_id(id: str) -> str:
    """
    Normalize an identifier by converting it to a string, and then 
    replacing the spaces with dashes.
    
    Args:
        series_id: The identifier to normalize.
    
    Returns:
        The normalized identifier.
    """
    return str(id).replace(" ", "-").lower()

def dereference_series(state: APPState, index: int) -> Union[Series, str]:
    """
    Dereference a series from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the series in the selection.
    
    Returns:
        The series object or an error message if not found.
    """
    selection = state.selection
    ser_sel = selection[index]
    if ser_sel.kind != "series":
        msg = f"The selection at index {index} is not a series: {ser_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_series(state, ser_sel.id)
    
def dereference_issue(state: APPState, index: int) -> Union[Issue, str]:
    """
    Dereference an issue from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the series in the selection.
    
    Returns:
        The issue object or an error message if not found.
    """
    selection = state.selection
    ser_sel = selection[index]
    iss_sel = selection[index+1]
    if iss_sel.kind != "issue":
        msg = f"The selection at index {index} is not an issue: {iss_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_issue(state=state, series_id=ser_sel.id, issue_id=iss_sel.id)

def dereference_cover(state: APPState, index: int) -> Union[TitleBoardModel, str]:
    """
    Dereference a cover from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the series in the selection.
    
    Returns:
        The cover object or an error message if not found.
    """
    selection = state.selection
    ser_sel = selection[index]
    iss_sel = selection[index+1]
    loc_sel = selection[index+2]
    if not loc_sel.kind.endswith("-cover"):
        msg = f"The selection at index {index} is not a cover: {loc_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_cover(state=state, series_id=ser_sel.id, issue_id=iss_sel.id, location=CoverLocation(loc_sel.id))

def dereference_scene(state: APPState, index: int) -> Union[SceneModel, str]:
    """
    Dereference a scene from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the series in the selection.
    
    Returns:
        The scene object or an error message if not found.
    """
    selection = state.selection
    ser_sel = selection[index]
    iss_sel = selection[index+1]
    sce_sel = selection[index+2]
    if sce_sel.kind != "scene":
        msg = f"The selection at index {index} is not a scene: {sce_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_scene(state=state, series_id=ser_sel.id, issue_id=iss_sel.id, scene_id=sce_sel.id)

def dereference_panel(state: APPState, index: int) -> Union[Panel, str]:
    """
    Dereference a panel from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the series in the selection.
    
    Returns:
        The panel object or an error message if not found.
    """
    selection = state.selection
    ser_sel = selection[index]
    iss_sel = selection[index+1]
    sce_sel = selection[index+2]
    pan_sel = selection[index+3]
    if pan_sel.kind != "panel":
        msg = f"The selection at index {index} is not a panel: {pan_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_panel(state=state, series_id=ser_sel.id, issue_id=iss_sel.id, scene_id=sce_sel.id, panel_id=pan_sel.id)

def dereference_character(state: APPState, index: int) -> Union[CharacterModel, str]:
    """
    Dereference a character from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the series in the selection.
    
    Returns:
        The character object or an error message if not found.
    """
    selection = state.selection
    ser_sel = selection[index]
    char_sel = selection[index+1]
    if char_sel.kind != "character":
        msg = f"The selection at index {index} is not a character: {char_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_character(state=state, series_id=ser_sel.id, character_id=char_sel.id)

def dereference_character_variant(state: APPState, index: int) -> Union[CharacterVariant, str]:
    """
    Dereference a character variant from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the series in the selection.
    
    Returns:
        The character variant object or an error message if not found.
    """
    selection = state.selection
    ser_sel = selection[index]
    char_sel = selection[index+1]
    var_sel = selection[index+2]
    if var_sel.kind != "character-variant":
        msg = f"The selection at index {index} is not a character variant: {var_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_character_variant(state=state, series_id=ser_sel.id, character_id=char_sel.id, variant_id=var_sel.id)

def dereference_style(state: APPState, index: int) -> Union[ComicStyle, str]:
    """
    Dereference a style from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the style in the selection.
    
    Returns:
        The style object or an error message if not found.
    """
    selection = state.selection
    sty_sel = selection[index+1]
    if sty_sel.kind != "style":
        msg = f"The selection at index {index} is not a style: {sty_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_style(state=state, style_id=sty_sel.id)

def dereference_publisher(state: APPState, index: int) -> Union[Publisher, str]:
    """
    Dereference a publisher from the state selection.
    
    Args:
        state: The GUI elements to interact with.
        index: The index of the publisher in the selection.
    
    Returns:
        The publisher object or an error message if not found.
    """
    selection = state.selection
    pub_sel = selection[index]
    if pub_sel.kind != "publisher":
        msg = f"The selection at index {index} is not a publisher: {pub_sel.kind}"
        logger.error(msg)
        return msg
    
    return get_publisher(state=state, publisher_id=pub_sel.id)

def get_series(state: APPState, series_id: int) -> str | Series:
    """
    Get the series by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series to retrieve.
    
    Returns:
        The series object or an error message if not found.
    """
    from schema.series import Series
    series_id = normalize_id(series_id)
    msg = None
    try: 
        series = Series.read(id=series_id)
    except Exception as e:
        msg = f"Error retrieving series with ID {series_id}: {e}"
    if series is None:
        msg = f"Series with ID '{series_id}' not found."
    if msg:
        logger.error(msg)
        return msg
    return series

def get_issue(state: APPState, series_id: str, issue_id: str) -> str | Issue:
    """
    Get the issue by its ID.
    
    Args:
        state: The GUI elements to interact with.
        issue_id: The ID of the issue to retrieve.
    
    Returns:
        The issue object or an error message if not found.
    """
    series_id = normalize_id(series_id)
    issue_id = normalize_id(issue_id)
    msg = None
    try: 
        issue = Issue.read(series_id=series_id, id=issue_id)
    except Exception as e:
        msg = f"Error retrieving issue with ID {issue_id}: {e}"
    if issue is None:
        msg = f"Issue with ID '{issue_id}' not found."
    if msg:
        logger.error(msg)
        return msg
    return issue

def get_style(state: APPState, style_id: str) -> str | ComicStyle:
    """
    Get the style by its ID.
    
    Args:
        state: The GUI elements to interact with.
        style_id: The ID of the style to retrieve.
    
    Returns:
        The style object or an error message if not found.
    """
    style_id = normalize_id(style_id)
    msg = None
    try: 
        style = ComicStyle.read(id=style_id)
    except Exception as e:
        msg = f"Error retrieving style with ID {style_id}: {e}"
    if style is None:
        msg = f"Style with ID '{style_id}' not found."
    if msg:
        logger.error(msg)
        return msg
    return style

def get_publisher(state: APPState, publisher_id: str) -> str | Publisher:
    """
    Get the publisher by its ID.
    
    Args:
        state: The GUI elements to interact with.
        publisher_id: The ID of the publisher to retrieve.
    
    Returns:
        The publisher object or an error message if not found.
    """
    publisher_id = normalize_id(publisher_id)
    msg = None
    try: 
        publisher = Publisher.read(id=publisher_id)
    except Exception as e:
        msg = f"Error retrieving publisher with ID {publisher_id}: {e}"
    if publisher is None:
        msg = f"Publisher with ID '{publisher_id}' not found."
    if msg:
        logger.error(msg)
        return msg
    return publisher

def get_character(state: APPState, series_id: str, character_id: str) -> str | None:
    """
    Get the character by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the character belongs to.
        character_id: The ID of the character to retrieve.
    
    Returns:
        The character object or an error message if not found.
    """
    series_id = normalize_id(series_id)
    character_id = normalize_id(character_id)
    msg = None
    try: 
        character = CharacterModel.read(series_id=series_id, id=character_id)
    except Exception as e:
        msg = f"Error retrieving character with ID {character_id}: {e}"
    if character is None:
        msg = f"Character with ID '{character_id}' not found in series '{series_id}'."
    if msg:
        logger.error(msg)
        return msg
    return character

def get_character_variant(state: APPState, series_id: str, character_id: str, variant_id: str) -> str | CharacterVariant:
    """
    Get the character variant by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the character belongs to.
        character_id: The ID of the character the variant belongs to.
        variant_id: The ID of the variant to retrieve.
    
    Returns:
        The character variant object or an error message if not found.
    """
    series_id = normalize_id(series_id)
    character_id = normalize_id(character_id)
    variant_id = normalize_id(variant_id)
    msg = None
    try: 
        variant = CharacterVariant.read(series_id=series_id, character_id=character_id, id=variant_id)
    except Exception as e:
        msg = f"Error retrieving character variant with ID {variant_id}: {e}"
    if variant is None:
        msg = f"Character variant with ID '{variant_id}' not found for character '{character_id}' in series '{series_id}'."
    if msg:
        logger.error(msg)
        return msg
    return variant

def get_cover(state: APPState, series_id: str, issue_id: str, location: CoverLocation) -> str | TitleBoardModel:
    """
    Get the cover by its location.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the cover belongs to.
        issue_id: The ID of the issue the cover belongs to.
        location: The location of the cover (e.g., "front", "back", etc.).
    
    Returns:
        The cover object or an error message if not found.
    """
    series_id = normalize_id(series_id)
    issue_id = normalize_id(issue_id)
    msg = None
    try: 
        cover = TitleBoardModel.read(series=series_id, issue=issue_id, location=location)
    except Exception as e:
        msg = f"Error retrieving cover for issue {issue_id} in series {series_id} at location {location}: {e}"
    if cover is None:
        msg = f"Cover not found for issue '{issue_id}' in series '{series_id}' at location '{location}'."
    if msg:
        logger.error(msg)
        return msg
    return cover

def get_scene(state: APPState, series_id: str, issue_id: str, scene_id: str) -> str | SceneModel:
    """
    Get the scene by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the scene belongs to.
        issue_id: The ID of the issue the scene belongs to.
        scene_id: The ID of the scene to retrieve.
    
    Returns:
        The scene object or an error message if not found.
    """
    series_id = normalize_id(series_id)
    issue_id = normalize_id(issue_id)
    scene_id = normalize_id(scene_id)
    msg = None
    try: 
        scene = SceneModel.read(series=series_id, issue=issue_id, id=scene_id)
    except Exception as e:
        msg = f"Error retrieving scene with ID {scene_id}: {e}"
    if scene is None:
        msg = f"Scene with ID '{scene_id}' not found in issue '{issue_id}' of series '{series_id}'."
    if msg:
        logger.error(msg)
        return msg
    return scene

def get_panel(state: APPState, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str | Panel:
    """
    Get the panel by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the panel belongs to.
        issue_id: The ID of the issue the panel belongs to.
        scene_id: The ID of the scene the panel belongs to.
        panel_id: The ID of the panel to retrieve.
    
    Returns:
        The panel object or an error message if not found.
    """
    series_id = normalize_id(series_id)
    issue_id = normalize_id(issue_id)
    scene_id = normalize_id(scene_id)
    panel_id = normalize_id(panel_id)
    msg = None
    try: 
        panel = Panel.read(series=series_id, issue=issue_id, scene=scene_id, id=panel_id)
    except Exception as e:
        msg = f"Error retrieving panel with ID {panel_id}: {e}"
    if panel is None:
        msg = f"Panel with ID '{panel_id}' not found in scene '{scene_id}' of issue '{issue_id}' in series '{series_id}'."
    if msg:
        logger.error(msg)
        return msg
    return panel

def wrap_render_logo(state: APPState):
    """
    Render the logo for a publisher.
    
    Args:
        state: The GUI elements to interact with.
    
    Returns:
        The rendered logo image.
    """
    @function_tool
    def render_logo() -> str:
        """
        Render the logo.
        
        Returns:
            A status message indicating the result of the rendering.
        """
        from schema.publisher import Publisher
        selection = state.selection
        kind = selection[-1].kind
        if kind != "publisher":
            msg = f"The selection is not a publisher: {kind}"
            logger.error(msg)
            return msg
        
        publisher_id = selection[-1].id
        publisher = Publisher.read(id=publisher_id)
        if publisher is None:
            msg = f"Publisher with ID '{publisher_id}' not found."
            logger.error(msg)
            return msg
        
        img = publisher.render()
        if img is None:
            msg = f"Logo for publisher '{publisher.name}' could not be rendered."
            logger.error(msg)
            return msg
        
        state["is_dirty"] = True        
        return f"The logo for publisher '{publisher.name}' has been rendered and is saved to {img}.jpg"
    
    return render_logo

def delete_publisher(state: APPState, publisher_id: str) -> str:
    """
    Delete a publisher by its ID.
    
    Args:
        state: The GUI elements to interact with.
        publisher_id: The ID of the publisher to delete.
    
    Returns:
        A status message indicating the result of the deletion operation.
    """
    from schema.publisher import Publisher
    publisher = get_publisher(state, publisher_id)
    if isinstance(publisher, str):
        return publisher
    
    publisher.delete()
    state.is_dirty = True

    if state.selection[-1].id == publisher_id and state.selection[-1].kind == "publisher":
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Publisher '{publisher.name}' deleted successfully."

def delete_style(state: APPState, style_id: str) -> str:
    """
    Delete a style by its ID.
    
    Args:
        state: The GUI elements to interact with.
        style_id: The ID of the style to delete.
    
    Returns:
        A status message indicating the result of the deletion operation.
    """
    style = get_style(state, style_id)
    if isinstance(style, str):
        return style
    
    style.delete()
    state.is_dirty = True

    if state.selection[-1].id == style_id and state.selection[-1].kind == "style":
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Style '{style.name}' deleted successfully."

def delete_panel(state: APPState, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str:
    """
    Delete a panel by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the panel belongs to.
        issue_id: The ID of the issue the panel belongs to.
        scene_id: The ID of the scene the panel belongs to.
        panel_id: The ID of the panel to delete.
    
    Returns:
        A status message indicating the result of the deletion operation.
    """
    panel = get_panel(state, series_id, issue_id, scene_id, panel_id)
    if isinstance(panel, str):
        return panel
    
    panel.delete()
    state.is_dirty = True

    if state.selection[-1].id == panel_id and state.selection[-1].kind == "panel":
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Panel '{panel.name}' deleted successfully."
    
def delete_scene(state: APPState, series_id: str, issue_id: str, scene_id: str) -> str:
    """
    Delete a scene by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the scene belongs to.
        issue_id: The ID of the issue the scene belongs to.
        scene_id: The ID of the scene to delete.
    
    Returns:
        A status message indicating the result of the deletion operation.
    """
    scene = get_scene(state, series_id, issue_id, scene_id)
    if isinstance(scene, str):
        return scene
    
    scene.delete()
    state.is_dirty = True

    if state.selection[-1].id == scene_id and state.selection[-1].kind == "scene":
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Scene '{scene.name}' deleted successfully."

def delete_issue(state: APPState, series_id: str, issue_id: str) -> str:
    """
    Delete an issue by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the issue belongs to.
        issue_id: The ID of the issue to delete.
    
    Returns:
        A status message indicating the result of the deletion operation.
    """
    issue = get_issue(state, series_id, issue_id)
    if isinstance(issue, str):
        return issue
    
    issue.delete()
    state.is_dirty = True

    if state.selection[-1].id == issue_id and state.selection[-1].kind == "issue":
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Issue '{issue.name}' deleted successfully."

def delete_series(state: APPState, series_id: str) -> str:
    """
    Delete a series by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series to delete.
    
    Returns:
        A status message indicating the result of the deletion operation.
    """
    series = get_series(state, series_id)
    if isinstance(series, str):
        return series
    
    series.delete()
    state.is_dirty = True

    if state.selection[-1].id == series_id and state.selection[-1].kind == "series":
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Series '{series.name}' deleted successfully."

def delete_character(state: APPState, series_id: str, character_id: str) -> str:
    """
    Delete a character by its ID.
    
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the character belongs to.
        character_id: The ID of the character to delete.
    
    Returns:
        A status message indicating the result of the deletion operation.
    """
    character = get_character(state, series_id, character_id)
    if isinstance(character, str):
        return character
    
    character.delete()
    state.is_dirty = True

    if state.selection[-1].id == character_id and state.selection[-1].kind == "character":
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Character '{character.name}' deleted successfully."

def delete_character_variant(state: APPState, series_id: str, character_id: str, variant_id: str) -> str:
    """
    Delete a character variant by its ID.
    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the character belongs to.
        character_id: The ID of the character the variant belongs to.
        variant_id: The ID of the variant to delete.

    Returns:
        A status message indicating the result of the deletion operation.
    """
    variant = get_character_variant(state, series_id, character_id, variant_id)
    if isinstance(variant, str):
        return variant
    
    variant.delete()
    state.is_dirty = True

    if state.selection[-1].id == variant_id and state.selection[-1].kind == "character-variant":
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Character variant '{variant.name}' deleted successfully."

def delete_cover(state: APPState, series_id: str, issue_id: str, location: CoverLocation) -> str:
    """
    Delete a cover by its location.

    Args:
        state: The GUI elements to interact with.
        series_id: The ID of the series the cover belongs to.
        issue_id: The ID of the issue the cover belongs to.
        location: The location of the cover (e.g., "front", "back", etc
    ).

    Returns:
        A status message indicating the result of the deletion operation.

    """
    cover = get_cover(state, series_id, issue_id, location)
    if isinstance(cover, str):
        return cover
    
    cover.delete()
    state.is_dirty = True

    if state.selection[-1].id == location.value and state.selection[-1].kind.endswith("-cover"):
        state.change_selection(new=state.selection[:-1])
        state.write()

    return f"Cover at location '{location.value}' for issue '{issue_id}' in series '{series_id}' deleted successfully."