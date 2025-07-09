from loguru import logger
from agents import function_tool, Tool
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
    CoverLocation,
    SceneModel,
    Series,
    Issue,
)

def read_context( state: APPState) -> list[BaseModel]:
    """
    Reads the context from the selection and returns a list of BaseModel objects.
    
    Args:
        selection: A list of SelectionItem objects representing the current selection.
    
    Returns:
        A list of BaseModel objects representing the context of the selection.
    """
    selection = state.selection
    storage = state.storage
    context = selection_to_context(selection)
    objects = []
    for item in context:
        cls, pk = item
        obj = storage.read_object(cls, pk)
        if obj is None:
            msg = f"Object of type {cls.__name__} with primary key {pk} not found in the database."
            logger.error(msg)
            raise ValueError(msg)
        objects.insert(0, obj)  # Insert at the beginning to have the most specific object first
    return objects

def init_tools(state: APPState) -> dict[str, Tool]:
    storage = state.storage

    def find(cls: type[BaseModel],pk: dict[str,str]) -> BaseModel:
        """
        Find an object in the storage by its primary key.
        
        Args:
            pk: The primary key of the object to find.
        
        Returns:
            The object if found, otherwise a status message.
        """
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
    
    
    def find_all(cls: type[BaseModel]) -> list[BaseModel]:
        """
        Find an object in the storage by its primary key.
        
        Args:
            pk: The primary key of the object to find.
        
        Returns:
            The object if found, otherwise a status message.
        """
        logger.trace(f"Finding all objects of type {cls.__name__} in selection")
        context = selection_to_context(state.selection)

        CONTEXT_ERROR_MSG = f"Cannot find {cls.__name__} instances.   They are not in the context of the current selection.  You may need to change the current selection."

        if len(context) == 0 and cls.__name__ not in ["Series", "Publisher", "ComicStyle"]:
            logger.error(CONTEXT_ERROR_MSG)
            raise ValueError(CONTEXT_ERROR_MSG)

        if len(context) == 0:
            return storage.read_all_objects(cls=cls)

        # If we reach here, the requested object is a child of the last item in the hierarchy
        parent_pk = context[0][1]
        return storage.read_all_objects(cls=cls, primary_key=parent_pk)

    @function_tool
    def get_current_selection() -> list[SelectionItem]:
        """
        Get the current selection.   This can be used to tell what the user is looking at.
        
        Returns:
            The current selection as a list of SelectionItems, representing the current
            object hierarchy/path to the item that the user is inspecting.
        """
        return state.selection
    
    # -------------------------------------------------------------------------
    # TOOLS TO FIND ALL TYPED CHILD OBJECTS OF THE SELECTION
    # -------------------------------------------------------------------------

    @function_tool
    def get_all_publishers() -> list[Publisher]:
        """
        Get a list of all publishers in the database.
        
        Returns:
            A list of publisher names.
        """
        return storage.read_all_objects(Publisher)
    
    @function_tool
    def get_all_styles() -> list[ComicStyle]:
        """
        Get a list of all comic styles in the database.
        
        Returns:
            A list of comic styles.
        """
        return storage.read_all_objects(ComicStyle)
    
    @function_tool
    def get_all_series() -> list[Series]:
        """
        Get a list of all comic series in the database.
        
        Returns:
            A list of comic series.
        """
        return storage.read_all_objects(Series)
    
    @function_tool
    def find_all_variants(series_id: str, character_id: str) -> list[CharacterVariant]:
        """
        Look up a all the variants of a character.
        Args:
            series_id: The identifier of the series the character belongs to.
            character_id: The identifier of the character for which to look up variants.
        
        Returns:
            A list of all variants for the character.
        """
        series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
        if series is None:
            raise ValueError(f"Series with id '{series_id}' not found.   You might want to look at the list of all series first.")
        character = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id})
        if character is None:
            raise ValueError(f"Character with id '{character_id}' not found in series '{series_id}'.   You might want to look at the list of all characters in the series first.")
        return storage.read_all_objects(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id})

    @function_tool
    def find_all_characters(series_id: str) -> list[CharacterModel]:
        """
        Look up a characters in a series.   

        Args:
            series_id: The identifier of the series the characters belongs to.
        
        Returns:
            The list of details about the characters in the series.
        """
        series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
        if series is None:
            raise ValueError(f"Series with id '{series_id}' not found.   You might want to look at the list of all series first.")
        return storage.read_all_objects(cls=CharacterModel, primary_key={"series_id": series_id})

    @function_tool
    def find_all_panels(series_id: str, issue_id: str, scene_id: str) -> list[Panel]:
        """
        look up all the panels in a scene

        Args:
            series_id: The identifier of the series the scene belongs to.
            issue_id: The identifier of the comic book issue the scene belongs to.
            scene_id: The identifier of the scene to look up panels for.
        Returns:
            A list of Panel objects representing the panels in the scene.
        """
        scene = storage.read_object(cls=SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
        if scene is None:
            raise ValueError(f"Scene with id '{scene_id}' not found in issue '{issue_id}' of series '{series_id}'.   You might want to look at the list of all scenes in the issue first.")
        
        return storage.read_all_objects(cls=Panel, primary_key={"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})    

    @function_tool
    def find_all_scenes(series_id: str, issue_id: str) -> list[SceneModel]:
        """
        Look up all scenes in a comic book issue.
        
        Args:
            series_id: The identifier of the series the issue belongs to.
            issue_id: The identifier of the comic book issue.
        
        Returns:
            A list of SceneModel objects representing the scenes in the issue.
        """
        issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
        if issue is None:
            raise ValueError(f"Issue with id '{issue_id}' not found in series '{series_id}'.   You might want to look at the list of all issues in the series first.")
        return storage.read_all_objects(cls=SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id}  )

    # -------------------------------------------------------------------------
    # FIND A SPECIFIC CHILD OBJECT OF THE CURRENT SELECTION
    # -------------------------------------------------------------------------

    @function_tool
    def find_character(series_id: str, character_id: str) -> CharacterModel | str:
        """
        Look up a character by its series and character identifiers.   

        Args:
            series_id: The identifier of the series the character belongs to.
            character_id: The identifier of the character to look up.
        
        Returns:
            The character object if found, otherwise a status message.
        """
        pk = {"series_id": series_id, "character_id": character_id}
        return find(CharacterModel, pk=pk)

    @function_tool
    def find_publisher(publisher_id: str) -> Publisher:
        """
        Find a publisher by its ID.
        
        Args:
            publisher_id: The ID of the publisher.
        
        Returns:
            The Publisher object if found, otherwise a status message.
        """
        pk = {"publisher_id": publisher_id}
        return find(Publisher, pk=pk)

    @function_tool
    def find_series(series_id: str) -> Series:
        """
        Get a comic series by its ID.
        Args:
            series_id: The ID of the comic series.  

        Returns:
            The Series object if found, otherwise a status message.
        """
        pk = {"series_id": series_id}
        return find(Series, pk=pk)

    @function_tool
    def find_style(style_id: str) -> ComicStyle | str:
        """
        Get the detailed information about a comic book style given its identifier.`
        
        Args:
            style_id: The unique identifier of the comic style.
        
        Returns:
            The ComicStyle object if found, otherwise a status message.
        """
        pk = {"style_id": style_id}
        return find(ComicStyle, pk=pk)

    @function_tool
    def find_variant(series_id: str, character_id: str, variant_id: str) -> CharacterVariant:
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
        return find(CharacterVariant, pk=pk)

    @function_tool
    def find_issue(series_id: str, issue_id: str) -> Issue:
        """
        Look up an issue of a comic book given its series and issue identifiers.   

        Args:
            series_id: The identifier of the series the issue belongs to.
            issue_id: The identifier of the comic book issue to look up.
        
        Returns:
            The Issue object if found, otherwise a status message.
        """
        pk = {"series_id": series_id, "issue_id": issue_id}
        return find(Issue, pk=pk)

    @function_tool
    def find_cover(series_id: str, issue_id: str, location: CoverLocation) -> Cover:
        """
        Look up a cover of a comic book given its series and issue identifiers.

        Args:
            series_id: The identifier of the series the cover belongs to.
            issue_id: The identifier of the comic book issue the cover belongs to.
            location: The location of the cover.
        Returns:
            The Cover object if found, otherwise a status message.
        """
        pk = dict(locals())
        pk['location'] = location.value
        return find(Cover, pk=pk)
    
    @function_tool
    def find_scene(series_id: str, issue_id: str, scene_id: str) -> SceneModel:
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
        return find(SceneModel, pk=pk)
    
    @function_tool
    def find_panel(series_id: str, issue_id: str, scene_id: str, panel_id: str) -> Panel:
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
        return find(Panel, pk=pk)

    # -------------------------------------------------------------------------
    # TOOLS TO DELETE OBJECTS FROM THE DATABASE
    # -------------------------------------------------------------------------

    @function_tool
    def delete_series(series_id: str) -> str:
        """
        Delete a comic series by name.   You MUST ask for confirmation before using this tool.
        
        Args:
            name: The name of the comic series to delete.
        
        Returns:
            A status message indicating the result of the deletion.
        """
        series = storage.delete_object(cls=Series, primary_key={"series_id": series_id})
        
        selection = state.selection
        sel_itm = selection[-1]
        if sel_itm.kind == SelectedKind.SERIES:
            # Change the selection!  Move up a level.
            new_selection = selection[:-1]
            state.change_selection(new=new_selection, clear_history=True)
        else:
            state.is_dirty = True
        return f"Deleted comic series: {series.name}"

    @function_tool
    def delete_style(style_id: str) -> str:
        """
        Delete a comic style by name.   You MUST ask for confirmation before using this tool.
        
        Args:
            name: The name of the comic style to delete.
        Returns:
            A status message indicating the result of the deletion.
        """
        style = storage.delete_object(cls=ComicStyle, primary_key={"style_id": style_id})
        selection = state.selection
        sel_itm = selection[-1]
        if sel_itm.kind == SelectedKind.STYLE:
            # Change the selection!  Move up a level.
            new_selection = selection[:-1]
            state.change_selection(new=new_selection, clear_history=True)
        else:
            state.is_dirty = True
        return f"Deleted comic style: {style.name}"
    
    @function_tool
    def delete_character(series_id: str, character_id: str) -> str:
        """
        Delete a character from a comic book series.   NOTE: YOU MUST ASK FOR
        CONFIRMATION BEFORE DELETING A CHARACTER.   THIS OPERATION CANNOT BE UNDONE.

        Args:
            series_id: The identifier of the series the character belongs to.
            character_id: The identifier of the character to delete.

        NOTES: You may be able to get the series_id or charcter_id from the current selection
        
        Returns:
            A message indicating the result of the deletion operation.
        """
        pk = locals()
        context = read_context(state)
        old = storage.delete_object(cls=CharacterModel, primary_key=pk)
        
        # Change the selection if the character is currently selected
        if this_sel.kind == SelectedKind.CHARACTER:
            new_selection = selection[:-1]  # Remove the last item (the character)
            state.change_selection(new=new_selection, clear_history=False)
        state.is_dirty = True
        return f"Character {character.name} deleted successfully."



    @function_tool
    def delete_publisher(publisher_id: str) -> str:
        """
        Delete a publisher by identifier.  You MUST ask for confirmation before using this tool.
        Args:
            publisher_id: The identifier of the publisher to delete.
        Returns:
            A status message indicating the result of the deletion.
        """
        publisher = storage.read_object(cls=Publisher, primary_key={"publisher_id": publisher_id})
        if publisher is None:
            return f"Publisher '{publisher_id}' not found."
        storage.delete_object(Publisher, primary_key={"publisher_id": publisher_id})

        selection = state.selection
        sel_itm = selection[-1]
        if sel_itm.kind == SelectedKind.PUBLISHER:
            # Change the selection!  Move up a level.
            new_selection = selection[:-1]
            state.change_selection(new=new_selection, clear_history=True)
        else:
            state.is_dirty = True
        return f"Deleted publisher: {publisher.name}"

    @function_tool
    def delete_issue(issue_id: str) -> str:
        """
        Delete a comic book issue by its id.   You MUST ask for confirmation before using this tool.
        
        Args:
            issue_id: The unique identifier for the issue
        
        Returns:
            A status message indicating the result of the deletion.
        """
        selection = state.selection
        selection_kind = state.selection[-1].kind
        selection_name = state.selection[-1].name
        selection_id = state.selection[-1].id

        if selection_kind == SelectedKind.ISSUE:
            series_id = state.selection[-2].id
            if issue_id != selection_id: 
                return f"Can't delete issue '{issue_id}.   The name does not match the currently selected issue."
        elif selection_kind == SelectedKind.SERIES:
            series_id = selection_id
            issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
            if issue is None:
                return f"Can't delete issue '{issue_id}'.   The issue does not exist in the series '{selection_name}'"
            issue_id = issue.id
        else:
            return f"Can't delete issue '{issue_id}'.   The selection is not a series or issue: {selection_kind}"
    
        storage.delete_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})

        if selection_kind == SelectedKind.ISSUE:
            # Change the selection!  Move up a level.
            new_selection = selection[:-1]
            state.change_selection(new=new_selection, clear_history=True)
        else:
            state.is_dirty = True
        return f"Deleted comic book issue: {issue_id}"


    @function_tool
    def delete_scene(scene_id: str) -> str:
        """
        Delete a scene from a comic book issue.   You MUST ask for confirmation before using this tool.
        
        Args:
            scene_id: The identifier of the scene to delete.
        Returns:
            A status message indicating the result of the deletion.
        """
        selection = state.selection
        sel_itm = selection[-1]
        if sel_itm.kind == SelectedKind.SCENE:
            issue_id = selection[-2].id
            if scene_id != sel_itm.id:
                return f"Can't delete scene '{scene_id}'.   The id does not match the currently selected scene."
        else:
            return f"Can't delete scene '{scene_id}'.   The selection is not a scene: {sel_itm.kind}"

        storage.delete_object(cls=SceneModel, primary_key={"issue_id": issue_id, "scene_id": scene_id})

        if sel_itm.kind == SelectedKind.SCENE:
            # Change the selection!  Move up a level.
            new_selection = selection[:-1]
            state.change_selection(new=new_selection, clear_history=True)
        else:
            state.is_dirty = True
        return f"Deleted comic book scene: {scene_id}"


    return {
        "get_current_selection": get_current_selection,

        # FIND ALL
        "get_all_publishers": get_all_publishers,
        "get_all_series": get_all_series,
        "get_all_styles": get_all_styles,
        "find_all_characters": find_all_characters,
        "find_all_variants": find_all_variants,
        "find_all_scenes": find_all_scenes,
        "find_all_panels": find_all_panels,
        
        # FIND SINGULAR
        "find_publisher": find_publisher,
        "find_style": find_style,
        "find_series": find_series,
        "find_character": find_character,
        "find_variant": find_variant,
        "find_issue": find_issue,
        "find_cover": find_cover,
        "find_scene": find_scene,
        "find_panel": find_panel,

        # DELETE 
        "delete_series": delete_series,
        "delete_style": delete_style,
        "delete_publisher": delete_publisher,
        "delete_issue": delete_issue,
        "delete_character": delete_character,
        "delete_scene": delete_scene,

        # UPDATE

        # IMAGES
    }

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

# def dereference_series(state: APPState, index: int) -> Union[Series, str]:
#     """
#     Dereference a series from the state selection.
    
#     Args:
#         state: The GUI elements to interact with.
#         index: The index of the series in the selection.
    
#     Returns:
#         The series object or an error message if not found.
#     """
#     selection = state.selection
#     ser_sel = selection[index]
#     if ser_sel.kind != "series":
#         msg = f"The selection at index {index} is not a series: {ser_sel.kind}"
#         logger.error(msg)
#         return msg
    
#     return get_series(state, ser_sel.id)
    
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

def dereference_cover(state: APPState, index: int) -> Union[Cover, str]:
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

# def dereference_scene(state: APPState, index: int) -> Union[SceneModel, str]:
#     """
#     Dereference a scene from the state selection.
    
#     Args:
#         state: The GUI elements to interact with.
#         index: The index of the series in the selection.
    
#     Returns:
#         The scene object or an error message if not found.
#     """
#     selection = state.selection
#     ser_sel = selection[index]
#     iss_sel = selection[index+1]
#     sce_sel = selection[index+2]
#     if sce_sel.kind != "scene":
#         msg = f"The selection at index {index} is not a scene: {sce_sel.kind}"
#         logger.error(msg)
#         return msg
    
#     return get_scene(state=state, series_id=ser_sel.id, issue_id=iss_sel.id, scene_id=sce_sel.id)

# def dereference_panel(state: APPState, index: int) -> Union[Panel, str]:
#     """
#     Dereference a panel from the state selection.
    
#     Args:
#         state: The GUI elements to interact with.
#         index: The index of the series in the selection.
    
#     Returns:
#         The panel object or an error message if not found.
#     """
#     selection = state.selection
#     ser_sel = selection[index]
#     iss_sel = selection[index+1]
#     sce_sel = selection[index+2]
#     pan_sel = selection[index+3]
#     if pan_sel.kind != "panel":
#         msg = f"The selection at index {index} is not a panel: {pan_sel.kind}"
#         logger.error(msg)
#         return msg
    
#     return get_panel(state=state, series_id=ser_sel.id, issue_id=iss_sel.id, scene_id=sce_sel.id, panel_id=pan_sel.id)

# def dereference_character(state: APPState, index: int) -> Union[CharacterModel, str]:
#     """
#     Dereference a character from the state selection.
    
#     Args:
#         state: The GUI elements to interact with.
#         index: The index of the series in the selection.
    
#     Returns:
#         The character object or an error message if not found.
#     """
#     selection = state.selection
#     ser_sel = selection[index]
#     char_sel = selection[index+1]
#     if char_sel.kind != "character":
#         msg = f"The selection at index {index} is not a character: {char_sel.kind}"
#         logger.error(msg)
#         return msg
    
#     return get_character(state=state, series_id=ser_sel.id, character_id=char_sel.id)

# def dereference_character_variant(state: APPState, index: int) -> Union[CharacterVariant, str]:
#     """
#     Dereference a character variant from the state selection.
    
#     Args:
#         state: The GUI elements to interact with.
#         index: The index of the series in the selection.
    
#     Returns:
#         The character variant object or an error message if not found.
#     """
#     selection = state.selection
#     ser_sel = selection[index]
#     char_sel = selection[index+1]
#     var_sel = selection[index+2]
#     if var_sel.kind != "character-variant":
#         msg = f"The selection at index {index} is not a character variant: {var_sel.kind}"
#         logger.error(msg)
#         return msg
    
#     return get_character_variant(state=state, series_id=ser_sel.id, character_id=char_sel.id, variant_id=var_sel.id)

# def dereference_style(state: APPState, index: int) -> Union[ComicStyle, str]:
#     """
#     Dereference a style from the state selection.
    
#     Args:
#         state: The GUI elements to interact with.
#         index: The index of the style in the selection.
    
#     Returns:
#         The style object or an error message if not found.
#     """
#     selection = state.selection
#     sty_sel = selection[index+1]
#     if sty_sel.kind != "style":
#         msg = f"The selection at index {index} is not a style: {sty_sel.kind}"
#         logger.error(msg)
#         return msg
    
#     return get_style(state=state, style_id=sty_sel.id)

# def dereference_publisher(state: APPState, index: int) -> Union[Publisher, str]:
#     """
#     Dereference a publisher from the state selection.
    
#     Args:
#         state: The GUI elements to interact with.
#         index: The index of the publisher in the selection.
    
#     Returns:
#         The publisher object or an error message if not found.
#     """
#     selection = state.selection
#     pub_sel = selection[index]
#     if pub_sel.kind != "publisher":
#         msg = f"The selection at index {index} is not a publisher: {pub_sel.kind}"
#         logger.error(msg)
#         return msg
    
#     return get_publisher(state=state, publisher_id=pub_sel.id)

# def get_series(state: APPState, series_id: int) -> str | Series:
#     """
#     Get the series by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series to retrieve.
    
#     Returns:
#         The series object or an error message if not found.
#     """
#     from schema.series import Series
#     series_id = normalize_id(series_id)
#     msg = None
#     try: 
#         series = Series.read(id=series_id)
#     except Exception as e:
#         msg = f"Error retrieving series with ID {series_id}: {e}"
#     if series is None:
#         msg = f"Series with ID '{series_id}' not found."
#     if msg:
#         logger.error(msg)
#         return msg
#     return series

# def get_issue(state: APPState, series_id: str, issue_id: str) -> str | Issue:
#     """
#     Get the issue by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         issue_id: The ID of the issue to retrieve.
    
#     Returns:
#         The issue object or an error message if not found.
#     """
#     series_id = normalize_id(series_id)
#     issue_id = normalize_id(issue_id)
#     msg = None
#     try: 
#         issue = Issue.read(series_id=series_id, id=issue_id)
#     except Exception as e:
#         msg = f"Error retrieving issue with ID {issue_id}: {e}"
#     if issue is None:
#         msg = f"Issue with ID '{issue_id}' not found."
#     if msg:
#         logger.error(msg)
#         return msg
#     return issue

# def get_style(state: APPState, style_id: str) -> str | ComicStyle:
#     """
#     Get the style by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         style_id: The ID of the style to retrieve.
    
#     Returns:
#         The style object or an error message if not found.
#     """
#     style_id = normalize_id(style_id)
#     msg = None
#     try: 
#         style = ComicStyle.read(id=style_id)
#     except Exception as e:
#         msg = f"Error retrieving style with ID {style_id}: {e}"
#     if style is None:
#         msg = f"Style with ID '{style_id}' not found."
#     if msg:
#         logger.error(msg)
#         return msg
#     return style

# def get_publisher(state: APPState, publisher_id: str) -> str | Publisher:
#     """
#     Get the publisher by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         publisher_id: The ID of the publisher to retrieve.
    
#     Returns:
#         The publisher object or an error message if not found.
#     """
#     publisher_id = normalize_id(publisher_id)
#     msg = None
#     try: 
#         publisher = Publisher.read(id=publisher_id)
#     except Exception as e:
#         msg = f"Error retrieving publisher with ID {publisher_id}: {e}"
#     if publisher is None:
#         msg = f"Publisher with ID '{publisher_id}' not found."
#     if msg:
#         logger.error(msg)
#         return msg
#     return publisher

# def get_character(state: APPState, series_id: str, character_id: str) -> str | None:
#     """
#     Get the character by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the character belongs to.
#         character_id: The ID of the character to retrieve.
    
#     Returns:
#         The character object or an error message if not found.
#     """
#     series_id = normalize_id(series_id)
#     character_id = normalize_id(character_id)
#     msg = None
#     try: 
#         character = CharacterModel.read(series_id=series_id, id=character_id)
#     except Exception as e:
#         msg = f"Error retrieving character with ID {character_id}: {e}"
#     if character is None:
#         msg = f"Character with ID '{character_id}' not found in series '{series_id}'."
#     if msg:
#         logger.error(msg)
#         return msg
#     return character

# def get_character_variant(state: APPState, series_id: str, character_id: str, variant_id: str) -> str | CharacterVariant:
#     """
#     Get the character variant by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the character belongs to.
#         character_id: The ID of the character the variant belongs to.
#         variant_id: The ID of the variant to retrieve.
    
#     Returns:
#         The character variant object or an error message if not found.
#     """
#     series_id = normalize_id(series_id)
#     character_id = normalize_id(character_id)
#     variant_id = normalize_id(variant_id)
#     msg = None
#     try: 
#         variant = CharacterVariant.read(series_id=series_id, character_id=character_id, id=variant_id)
#     except Exception as e:
#         msg = f"Error retrieving character variant with ID {variant_id}: {e}"
#     if variant is None:
#         msg = f"Character variant with ID '{variant_id}' not found for character '{character_id}' in series '{series_id}'."
#     if msg:
#         logger.error(msg)
#         return msg
#     return variant

# def get_cover(state: APPState, series_id: str, issue_id: str, location: CoverLocation) -> str | TitleBoardModel:
#     """
#     Get the cover by its location.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the cover belongs to.
#         issue_id: The ID of the issue the cover belongs to.
#         location: The location of the cover (e.g., "front", "back", etc.).
    
#     Returns:
#         The cover object or an error message if not found.
#     """
#     series_id = normalize_id(series_id)
#     issue_id = normalize_id(issue_id)
#     msg = None
#     try: 
#         cover = TitleBoardModel.read(series=series_id, issue=issue_id, location=location)
#     except Exception as e:
#         msg = f"Error retrieving cover for issue {issue_id} in series {series_id} at location {location}: {e}"
#     if cover is None:
#         msg = f"Cover not found for issue '{issue_id}' in series '{series_id}' at location '{location}'."
#     if msg:
#         logger.error(msg)
#         return msg
#     return cover

# def get_scene(state: APPState, series_id: str, issue_id: str, scene_id: str) -> str | SceneModel:
#     """
#     Get the scene by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the scene belongs to.
#         issue_id: The ID of the issue the scene belongs to.
#         scene_id: The ID of the scene to retrieve.
    
#     Returns:
#         The scene object or an error message if not found.
#     """
#     series_id = normalize_id(series_id)
#     issue_id = normalize_id(issue_id)
#     scene_id = normalize_id(scene_id)
#     msg = None
#     try: 
#         scene = SceneModel.read(series=series_id, issue=issue_id, id=scene_id)
#     except Exception as e:
#         msg = f"Error retrieving scene with ID {scene_id}: {e}"
#     if scene is None:
#         msg = f"Scene with ID '{scene_id}' not found in issue '{issue_id}' of series '{series_id}'."
#     if msg:
#         logger.error(msg)
#         return msg
#     return scene

# def get_panel(state: APPState, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str | Panel:
#     """
#     Get the panel by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the panel belongs to.
#         issue_id: The ID of the issue the panel belongs to.
#         scene_id: The ID of the scene the panel belongs to.
#         panel_id: The ID of the panel to retrieve.
    
#     Returns:
#         The panel object or an error message if not found.
#     """
#     series_id = normalize_id(series_id)
#     issue_id = normalize_id(issue_id)
#     scene_id = normalize_id(scene_id)
#     panel_id = normalize_id(panel_id)
#     msg = None
#     try: 
#         panel = Panel.read(series=series_id, issue=issue_id, scene=scene_id, id=panel_id)
#     except Exception as e:
#         msg = f"Error retrieving panel with ID {panel_id}: {e}"
#     if panel is None:
#         msg = f"Panel with ID '{panel_id}' not found in scene '{scene_id}' of issue '{issue_id}' in series '{series_id}'."
#     if msg:
#         logger.error(msg)
#         return msg
#     return panel

# def wrap_render_logo(state: APPState):
#     """
#     Render the logo for a publisher.
    
#     Args:
#         state: The GUI elements to interact with.
    
#     Returns:
#         The rendered logo image.
#     """
#     @function_tool
#     def render_logo() -> str:
#         """
#         Render the logo.
        
#         Returns:
#             A status message indicating the result of the rendering.
#         """
#         from schema.publisher import Publisher
#         selection = state.selection
#         kind = selection[-1].kind
#         if kind != "publisher":
#             msg = f"The selection is not a publisher: {kind}"
#             logger.error(msg)
#             return msg
        
#         publisher_id = selection[-1].id
#         publisher = Publisher.read(id=publisher_id)
#         if publisher is None:
#             msg = f"Publisher with ID '{publisher_id}' not found."
#             logger.error(msg)
#             return msg
        
#         img = publisher.render()
#         if img is None:
#             msg = f"Logo for publisher '{publisher.name}' could not be rendered."
#             logger.error(msg)
#             return msg
        
#         state["is_dirty"] = True        
#         return f"The logo for publisher '{publisher.name}' has been rendered and is saved to {img}.jpg"
    
#     return render_logo

# def delete_publisher(state: APPState, publisher_id: str) -> str:
#     """
#     Delete a publisher by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         publisher_id: The ID of the publisher to delete.
    
#     Returns:
#         A status message indicating the result of the deletion operation.
#     """
#     from schema.publisher import Publisher
#     publisher = get_publisher(state, publisher_id)
#     if isinstance(publisher, str):
#         return publisher
    
#     publisher.delete()
#     state.is_dirty = True

#     if state.selection[-1].id == publisher_id and state.selection[-1].kind == "publisher":
#         state.change_selection(new=state.selection[:-1])
#         state.write()

#     return f"Publisher '{publisher.name}' deleted successfully."

# def delete_style(state: APPState, style_id: str) -> str:
#     """
#     Delete a style by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         style_id: The ID of the style to delete.
    
#     Returns:
#         A status message indicating the result of the deletion operation.
#     """
#     style = get_style(state, style_id)
#     if isinstance(style, str):
#         return style
    
#     style.delete()
#     state.is_dirty = True

#     if state.selection[-1].id == style_id and state.selection[-1].kind == "style":
#         state.change_selection(new=state.selection[:-1])
#         state.write()

#     return f"Style '{style.name}' deleted successfully."

# def delete_panel(state: APPState, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str:
#     """
#     Delete a panel by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the panel belongs to.
#         issue_id: The ID of the issue the panel belongs to.
#         scene_id: The ID of the scene the panel belongs to.
#         panel_id: The ID of the panel to delete.
    
#     Returns:
#         A status message indicating the result of the deletion operation.
#     """
#     panel = get_panel(state, series_id, issue_id, scene_id, panel_id)
#     if isinstance(panel, str):
#         return panel
    
#     panel.delete()
#     state.is_dirty = True

#     if state.selection[-1].id == panel_id and state.selection[-1].kind == "panel":
#         state.change_selection(new=state.selection[:-1])
#         state.write()

#     return f"Panel '{panel.name}' deleted successfully."
    
# def delete_scene(state: APPState, series_id: str, issue_id: str, scene_id: str) -> str:
#     """
#     Delete a scene by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the scene belongs to.
#         issue_id: The ID of the issue the scene belongs to.
#         scene_id: The ID of the scene to delete.
    
#     Returns:
#         A status message indicating the result of the deletion operation.
#     """
#     scene = get_scene(state, series_id, issue_id, scene_id)
#     if isinstance(scene, str):
#         return scene
    
#     scene.delete()
#     state.is_dirty = True

#     if state.selection[-1].id == scene_id and state.selection[-1].kind == "scene":
#         state.change_selection(new=state.selection[:-1])
#         state.write()

#     return f"Scene '{scene.name}' deleted successfully."

# def delete_issue(state: APPState, series_id: str, issue_id: str) -> str:
#     """
#     Delete an issue by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the issue belongs to.
#         issue_id: The ID of the issue to delete.
    
#     Returns:
#         A status message indicating the result of the deletion operation.
#     """
#     issue = get_issue(state, series_id, issue_id)
#     if isinstance(issue, str):
#         return issue
    
#     issue.delete()
#     state.is_dirty = True

#     if state.selection[-1].id == issue_id and state.selection[-1].kind == "issue":
#         state.change_selection(new=state.selection[:-1])
#         state.write()

#     return f"Issue '{issue.name}' deleted successfully."

# def delete_series(state: APPState, series_id: str) -> str:
#     """
#     Delete a series by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series to delete.
    
#     Returns:
#         A status message indicating the result of the deletion operation.
#     """
#     series = get_series(state, series_id)
#     if isinstance(series, str):
#         return series
    
#     series.delete()
#     state.is_dirty = True

#     if state.selection[-1].id == series_id and state.selection[-1].kind == "series":
#         state.change_selection(new=state.selection[:-1])
#         state.write()

#     return f"Series '{series.name}' deleted successfully."

# def delete_character(state: APPState, series_id: str, character_id: str) -> str:
#     """
#     Delete a character by its ID.
    
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the character belongs to.
#         character_id: The ID of the character to delete.
    
#     Returns:
#         A status message indicating the result of the deletion operation.
#     """
#     character = get_character(state, series_id, character_id)
#     if isinstance(character, str):
#         return character
    
#     character.delete()
#     state.is_dirty = True

#     if state.selection[-1].id == character_id and state.selection[-1].kind == "character":
#         state.change_selection(new=state.selection[:-1])
#         state.write()

#     return f"Character '{character.name}' deleted successfully."

# def delete_character_variant(state: APPState, series_id: str, character_id: str, variant_id: str) -> str:
#     """
#     Delete a character variant by its ID.
#     Args:
#         state: The GUI elements to interact with.
#         series_id: The ID of the series the character belongs to.
#         character_id: The ID of the character the variant belongs to.
#         variant_id: The ID of the variant to delete.

#     Returns:
#         A status message indicating the result of the deletion operation.
#     """
#     variant = get_character_variant(state, series_id, character_id, variant_id)
#     if isinstance(variant, str):
#         return variant
    
#     variant.delete()
#     state.is_dirty = True

#     if state.selection[-1].id == variant_id and state.selection[-1].kind == "character-variant":
#         state.change_selection(new=state.selection[:-1])
#         state.write()

#     return f"Character variant '{variant.name}' deleted successfully."

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