from typing import Tuple, Optional, List
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool
from gui.state import APPState
from schema import Cover, CoverLocation, FrameLayout, CharacterRef, Issue, InsertionLocation, BeforeFirst, Before, After, AfterLast, SceneModel
from gui.selection import SelectionItem, SelectedKind
from storage.generic import GenericStorage
from loguru import logger

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


def issue_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    from generators.tools import dereference_issue as _get_issue
    from generators.tools import normalize_id, normalize_name
        

    @function_tool
    def get_current_issue() -> Issue:
        """
        Get the currently selected comic book issue.
        
        Returns:
            The currently selected issue.
        """
        return _get_issue(state, index=-2)

    @function_tool
    def create_cover(location: CoverLocation, characters: list[str], foreground: str, background: str) -> str:
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
        issue_or_str = _get_issue(state, index=-2)
        
        if isinstance(issue_or_str, str):
            return issue_or_str
        
        issue: Issue = issue_or_str
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

    def _update_attribute(attribute: str, value: Optional[str]) -> str:
        """
        Update an attribute of the currently selected issue.
        
        Args:
            attribute (str): The name of the attribute to update.
            value (Optional[str]): The new value for the attribute.
        
        Returns:
            A status message indicating the result of the update.
        """
        storage: GenericStorage = state.storage
        issue_id = state.selection[-1].id
        series_id = state.selection[-2].id
        issue = storage.read_object(cls=Issue, primary_key={"issue_id": issue_id, "series_id": series_id})
        if issue is None:
            return f"Issue with ID '{issue_id}' in series '{series_id}' not found."
        if not hasattr(issue, attribute):
            return f"Attribute '{attribute}' does not exist on Issue."
        setattr(issue, attribute, value)
        storage.update_object(data=issue)
        state.is_dirty = True
        return f"Updated {attribute} to '{value}' for issue {issue.name}."

    @function_tool
    def update_story(story: str) -> str:
        """
        Update the story of the currently selected comic book issue.   Note, the story should
        be a summary of the issue's plot, not a full script.   It should be in sufficient detail as
        to allow the creative team to understand the narrative flow and key events, and to produce
        the necessary artwork and dialogue.

        Args:
            story (str): The new story for the issue.

        Returns:
            A status message indicating the result of the update.
        """
        return _update_attribute("story", story)

    @function_tool
    def update_publication_date(publication_date: Optional[str]) -> str:
        """
        Update the publication date of the currently selected comic book issue.
        
        Args:
            publication_date (str): The new publication date for the issue.  This can
              be empty if the publication date is not known or not applicable.
        
        Returns:
            A status message indicating the result of the update.
        """
        return _update_attribute("publication_date", publication_date)
    
    @function_tool
    def update_price(price: Optional[float]) -> str:
        """
        Update the price of the currently selected comic book issue.
        
        Args:
            price (Optional[float]): The new price for the issue.  This can be None if the price is not known or not applicable.
        
        Returns:
            A status message indicating the result of the update.
        """
        return _update_attribute("price", price)

    @function_tool
    def update_writer(writer: Optional[str]) -> str:
        """
        Update the writer of the currently selected comic book issue.
        
        Args:
            writer (Optional[str]): The new writer for the issue.  This can be None if the writer is not known or not applicable.
        
        Returns:
            A status message indicating the result of the update.
        """
        return _update_attribute("writer", writer)

    @function_tool
    def update_artist(artist: Optional[str]) -> str:
        """
        Update the artist of the currently selected comic book issue.
        
        Args:
            artist (Optional[str]): The new artist for the issue.  This can be None if the artist is not known or not applicable.
        
        Returns:
            A status message indicating the result of the update.
        """
        return _update_attribute("artist", artist)
    
    @function_tool
    def update_colorist(colorist: Optional[str]) -> str:
        """
        Update the colorist of the currently selected comic book issue.

        Args:
            colorist (Optional[str]): The new colorist for the issue.  This can be None if the
            colorist is not known or not applicable.

        Returns:
            A status message indicating the result of the update.
        """
        return _update_attribute("colorist", colorist)
    
    @function_tool
    def update_creative_minds(creative_minds: Optional[str]) -> str:
        """
        Update the creative minds of the currently selected comic book issue.
        Args:
            creative_minds (Optional[str]): The new creative minds for the issue.  This can be None if the
            creative minds are not known or not applicable.

        Returns:
            A status message indicating the result of the update.
        """
        return _update_attribute("creative_minds", creative_minds)
    
    @function_tool
    def swap_scene_order(first_scene_number: int, second_scene_number: int) -> str:
        """
        Swap the order of two scenes in the currently selected comic book issue.
        
        Args:
            first_scene_number (int): The scene number of the first scene to swap.
            second_scene_number (int): The scene number of the second scene to swap.
        
        Returns:
            A status message indicating the result of the swap.
        """
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
    def create_scene(name: str, story: str, insertion_location: InsertionLocation) -> str:
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

    return Agent(
        name="issue",
        instructions="Agent for managing comic book issues.\n\n"+BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        
        tools=[
            tools.get('get_current_selection', None),

            tools.get('delete_issue', None),
            tools.get('find_issue', None),
            tools.get('find_all_scenes', None),
            tools.get('find_style', None),
            
            update_story,
            update_publication_date,
            update_price,
            update_writer,
            update_artist,
            update_colorist,
            update_creative_minds,
            swap_scene_order,
            create_scene,

            create_cover,
        ]
    )

