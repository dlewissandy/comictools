from loguru import logger
from agents import function_tool, Tool, RunContextWrapper
from typing import Callable, Optional, Union
from pydantic import BaseModel
from gui.state import APPState
from gui.selection import SelectionItem, SelectedKind, selection_to_context
from storage.generic import GenericStorage
from schema import (
    ComicStyle,
    Publisher,
    CharacterModel,
    CharacterVariant,
    Panel,
    Cover,
    SceneModel,
    Series,
    Issue,
)

# -------------------------------------------------------------------------
# Functions to read objects from the database.   These are used by the tools
# To perform the file operations
# -------------------------------------------------------------------------
def read_all(
        wrapper: RunContextWrapper[APPState], 
        cls: type[BaseModel], 
        parent_key: dict[str, str] | None = None,
        order_by: Optional[Union[str, Callable[[BaseModel], str]]] = None
        ) -> list[BaseModel]:
    """
    Read all objects of a given class from the database.   

    Args:
        wrapper: The run context wrapper containing the application state.
        cls: The class of the objects to read.
        parent_key: An optional primary key for the parent object.   If not provided, the function will
            read all the objects rooted on the current selection.
    Notes: This function throws if any of the objects are ill formed.
    """
    state: APPState = wrapper.context
    storage:GenericStorage = state.storage

    logger.trace(f"Finding all objects of type {cls.__name__}")
    context = selection_to_context(state.selection)

    CONTEXT_ERROR_MSG = f"Cannot find {cls.__name__} instances."

    if len(context) == 0 and cls.__name__ not in ["Series", "Publisher", "ComicStyle"]:
        logger.error(CONTEXT_ERROR_MSG)
        raise ValueError(CONTEXT_ERROR_MSG)

    if len(context) == 0:
        return storage.read_all_objects(cls=cls)

    # If we reach here, the requested object is a child of the last item in the hierarchy
    pk_parent = context[0][1] if parent_key is None else parent_key
    objs = storage.read_all_objects(cls=cls, primary_key=pk_parent)

    if order_by is None:
        return objs
    elif callable(order_by):
        return sorted(objs, key=order_by)
    elif isinstance(order_by, str):
        return sorted(objs, key=lambda obj: getattr(obj, order_by))
    else:
        logger.error(f"Invalid order_by argument: {order_by}")
        raise ValueError(f"Invalid order_by argument: {order_by}")


def read_one(wrapper: RunContextWrapper[APPState], cls: type[BaseModel], pk: dict[str, str]) -> BaseModel:
    """
    Find an object in the storage by its primary key.
    
    Args:
        pk: The primary key of the object to find.
    
    Returns:
        The object if found, otherwise a status message.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    logger.trace(f"Finding object with key = {pk}")
    context = selection_to_context(state.selection)

    CONTEXT_ERROR_MSG = f"Cannot find object with key = {pk}.   It is not in the context of the current selection.  You may need to change the current selection."
    NOT_FOUND_ERROR_MSG = f"Cannot find object with key = {pk}.   It is not in the database.   You may want to verify the primary key(s)"
    TOP_LEVEL_IDS = ['series_id', 'publisher_id', 'style_id']

    pk_keys = list(pk.keys())

    if len(pk_keys)==1 and pk_keys[0] in TOP_LEVEL_IDS:
        # Special case: Top level ids can be retrieved regardless of the current context.
        logger.debug("Finding top level object with key = {pk}")
    elif len(context) == 0:
        # If the context is empty, we can still find series, publishers and styles (since they)
        # are top level objects in the hierarchy.
        if any(pk.keys(), lambda k: k not in TOP_LEVEL_IDS):
            # However if the user selected something that is not at the top level of the hierarch, then
            # We throw an error
            logger.error(CONTEXT_ERROR_MSG)
            raise ValueError(CONTEXT_ERROR_MSG)
        logger.debug("Finding top level object with key = {pk}")

    # Special case for when the context and the primary key of the current selection are the same
    elif len(context) > 0 and context[0][1] == pk:
        logger.debug(f"Finding current selection {pk}")
    
    # The requested object should be a child of the selected object
    elif len(context) > 0 and len(pk) == len(context)+1:
        parent_pk = context[0][1]
        parent_keys = list(parent_pk.keys())
        child_keys = pk.keys()
        while len(parent_keys) > 0:
            k = parent_keys.pop()
            if k not in child_keys:
                logger.error(CONTEXT_ERROR_MSG)
                raise ValueError(CONTEXT_ERROR_MSG)
            if pk[k] != parent_pk[k]:
                logger.error(CONTEXT_ERROR_MSG)
                raise ValueError(CONTEXT_ERROR_MSG)
    else:
        logger.error(CONTEXT_ERROR_MSG)
        raise ValueError(CONTEXT_ERROR_MSG)

    obj = storage.read_object(cls=cls, primary_key=pk)
    if obj is None:
        logger.error(NOT_FOUND_ERROR_MSG)
        raise ValueError(NOT_FOUND_ERROR_MSG)
    return obj


# -------------------------------------------------------------------------
# TOOLS TO FIND ALL TYPED CHILD OBJECTS OF THE SELECTION
# -------------------------------------------------------------------------

@function_tool
def read_all_publishers(wrapper: RunContextWrapper[APPState]) -> list[Publisher]:
    """
    Get a list of all publishers in the database.
    
    Returns:
        A list of publisher names.
    """
    return read_all(wrapper=wrapper, cls=Publisher, parent_key=None)

@function_tool
def read_all_styles(wrapper: RunContextWrapper[APPState]) -> list[ComicStyle]:
    """
    Get a list of all comic styles in the database.
    
    Returns:
        A list of comic styles.
    """
    return read_all(wrapper=wrapper, cls=ComicStyle)

@function_tool
def read_all_series(wrapper: RunContextWrapper[APPState]) -> list[Series]:
    """
    Get a list of all comic series in the database.
    
    Returns:
        A list of comic series.
    """
    return read_all(wrapper=wrapper, cls=Series)

@function_tool
def read_all_characters(wrapper: RunContextWrapper[APPState], series_id: str) -> list[CharacterModel]:
    """
    Look up a characters in a series.   

    Args:
        series_id: The identifier of the series the characters belongs to.
    
    Returns:
        The list of details about the characters in the series.
    """
    return read_all(wrapper=wrapper, cls=CharacterModel, parent_key={"series_id": series_id})

@function_tool
def read_all_variants(
    wrapper: RunContextWrapper[APPState],
    series_id: str, 
    character_id: str                  
    ) -> list[CharacterVariant]:
    """
    Look up a all the variants of a character.
    Args:
        series_id: The identifier of the series the character belongs to.
        character_id: The identifier of the character for which to look up variants.
    
    Returns:
        A list of all variants for the currently selected character.
    """
    parent_key = {"series_id": series_id, "character_id": character_id}
    return read_all(wrapper=wrapper, cls=CharacterVariant, parent_key=parent_key, order_by="name")

@function_tool
def read_all_covers(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> list[Cover]:
    """
    Look up all covers in a comic book issue.

    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The identifier of the comic book issue.

    Returns:
        A list of Cover objects representing the covers in the issue.
    """
    parent_key = {"series_id": series_id, "issue_id": issue_id}

    ORDER: list[str] = ["front", "inside-front", "inside-back", "back"]

    return read_all(
        wrapper=wrapper, 
        cls=Cover, 
        parent_key=parent_key,
        order_by=lambda cover: ORDER.index(cover.location.value)
    )

@function_tool
def read_all_issues(wrapper: RunContextWrapper[APPState], series_id: str) -> list[Issue]:
    """
    Look up all issues in a comic book series.
    
    Args:
        series_id: The identifier of the comic book series.
    
    Returns:
        A list of Issue objects representing the issues in the series.
    """
    return read_all(wrapper=wrapper, cls=Issue, parent_key={"series_id": series_id})

@function_tool
def read_all_scenes(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> list[SceneModel]:
    """
    Look up all scenes in a comic book issue.
    
    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The identifier of the comic book issue.
    
    Returns:
        A list of SceneModel objects representing the scenes in the issue.
    """
    parent_key = {"series_id": series_id, "issue_id": issue_id}
    return read_all(wrapper=wrapper,cls=SceneModel, parent_key=parent_key) 

@function_tool
def read_all_panels(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str) -> list[Panel]:
    """
    look up all the panels in a scene

    Args:
        series_id: The identifier of the series the scene belongs to.
        issue_id: The identifier of the comic book issue the scene belongs to.
        scene_id: The identifier of the scene to look up panels for.
    Returns:
        A list of Panel objects representing the panels in the scene.
    """
    parent_key = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    return read_all(wrapper=wrapper, cls=Panel, parent_key=parent_key)

# -------------------------------------------------------------------------
# FIND A SPECIFIC CHILD OBJECT OF THE CURRENT SELECTION
# -------------------------------------------------------------------------

@function_tool
def read_publisher(wrapper: RunContextWrapper[APPState], publisher_id: str) -> Publisher | str:
    """
    Find a publisher by its ID.
    
    Args:
        publisher_id: The ID of the publisher.
    
    Returns:
        The Publisher object if found, otherwise a status message.
    """
    pk = {"publisher_id": publisher_id}
    return read_one(wrapper=wrapper, cls=Publisher, pk=pk)

@function_tool
def read_style(wrapper: RunContextWrapper[APPState], style_id: str) -> ComicStyle | str:
    """
    Get the detailed information about a comic book style given its identifier.
    
    Args:
        style_id: The unique identifier of the comic style.
    
    Returns:
        The ComicStyle object if found, otherwise a status message.
    """
    pk = {"style_id": style_id}
    return read_one(wrapper=wrapper, cls=ComicStyle, pk=pk)

@function_tool
def read_series(wrapper: RunContextWrapper[APPState], series_id: str) -> Series | str:
    """
    Get a comic series by its ID.
    Args:
        series_id: The ID of the comic series.  

    Returns:
        The Series object if found, otherwise a status message.
    """
    pk = {"series_id": series_id}
    return read_one(wrapper=wrapper, cls=Series, pk=pk)


@function_tool
def read_character(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str) -> CharacterModel | str:
    """
    Look up a character by its series and character identifiers.   

    Args:
        series_id: The identifier of the series the character belongs to.
        character_id: The identifier of the character to look up.
    
    Returns:
        The character object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "character_id": character_id}
    return read_one(wrapper=wrapper, cls=CharacterModel, pk=pk)

@function_tool
def read_variant(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str) -> CharacterVariant | str:
    """
    Look up a variant of a character.

    Args:
        series_id: The identifier of the series the character belongs to.
        character_id: The identifier of the character for which to look up variants.
        variant_id: The identifier of the variant to look up.

    Returns:
        The CharacterVariant object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "character_id": character_id, "variant_id": variant_id}
    return read_one(wrapper=wrapper, cls=CharacterVariant, pk=pk)

@function_tool
def read_issue(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> Issue | str:
    """
    Look up an issue of a comic book given its series and issue identifiers.   

    Args:
        series_id: The identifier of the series the issue belongs to.
        issue_id: The identifier of the comic book issue to look up.
    
    Returns:
        The Issue object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "issue_id": issue_id}
    return read_one(wrapper=wrapper, cls=Issue, pk=pk)

@function_tool
def read_cover(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, cover_id: str) -> Cover | str:
    """
    Look up a cover of a comic book given its series and issue identifiers.

    Args:
        series_id: The identifier of the series the cover belongs to.
        issue_id: The identifier of the comic book issue the cover belongs to.
        cover_id: The identifier of the cover to look up.
    Returns:
        The Cover object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "cover_id": cover_id}
    return read_one(wrapper=wrapper, cls=Cover, pk=pk)

@function_tool
def read_scene(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str) -> SceneModel | str:
    """
    Look up a scene of a comic book given its series and issue identifiers.

    Args:
        series_id: The identifier of the series the scene belongs to.
        issue_id: The identifier of the comic book issue the scene belongs to.
        scene_id: The identifier of the scene to look up.

    Returns:
        The SceneModel object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    return read_one(wrapper=wrapper, cls=SceneModel, pk=pk)

@function_tool
def read_panel(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, panel_id: str) -> Panel | str:
    """
    Look up a panel of a comic book given its series, issue, and scene identifiers.
    Args:
        series_id: The identifier of the series the panel belongs to.
        issue_id: The identifier of the comic book issue the panel belongs to.
        scene_id: The identifier of the scene the panel belongs to.
        panel_id: The identifier of the panel to look up.
    Returns:
        The Panel object if found, otherwise a status message.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id}
    return read_one(wrapper=wrapper, cls=Panel, pk=pk)
