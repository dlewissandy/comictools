from typing import Tuple, Optional, List
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import APPState
from schema.series import Series
from gui.selection import SelectionItem
from schema.character import CharacterModel
from schema.publisher import Publisher
from schema.issue import Issue
from storage.generic import GenericStorage


def series_agent(state: APPState) -> Agent:
    storage: GenericStorage = state.storage
    logger = state.logger

    def _get_series_id() -> str:
        """
        Get the ID of the currently selected comic series.
        
        Returns:
            The ID of the selected series, or None if no series is selected.
        """
        series_id = state.selection[-1].id if state.selection else None
        if not series_id:
            logger.error("No comic series selected. Please select a series to perform this action.")
            raise ValueError("No comic series selected.")
        return series_id

    @function_tool
    def get_details() -> str | Series:
        """
        Get the details of the currently selected comic series.
        
        Returns:
            A string containing the details of the current comic series.
        """
        return storage.read_series(id=_get_series_id())

    @function_tool
    def update_description(
        description: str
    ) -> str:
        """
        Update the description of a comic series.
        
        Args:
            series_id: The ID of the comic series to update.
            description: The new description for the comic series.
        
        Returns:
            A confirmation message indicating the update was successful.
        """
        series = storage.read_series(id=_get_series_id())        
        series.description = description
        storage.update_series(data=series)
        state.is_dirty = True
        return f"Description for series '{series.series_title}' updated successfully."
    
    @function_tool
    def get_issues() -> List[Issue]:
        """
        Get a list of all the issues in the currently selected comic series.
        
        Returns:
            A list of the names of the issues in the current comic series.
        """
        selection = state.selection
        sel_item = selection[-1] if selection else None
        if not sel_item or sel_item.kind != "series":
            return ["No comic series selected. Please select a series to view issues."]
        
        series_id = sel_item.id
        series = storage.read_series(id=series_id)
        if not series:
            return [f"Series with ID '{series_id}' not found."]
        
        issues = Issue.read_all(series_id=series_id)
        if not issues:
            return ["No issues found in this series."]
        return issues

    @function_tool
    def delete_series() -> str:
        """
        Delete the currently selected series.
        NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        """
        
        series = storage.delete_series(id=_get_series_id())
        state.selection = state.selection[:-1]  # Remove the last selection item
        state.write()
        state.is_dirty = True
        return f"Series {series.name} deleted."

    @function_tool
    def get_characters() -> List[CharacterModel] | str:
        """
        Get a list of all characters in the currently selected comic series.
        
        Returns:
            A list of character in the current comic series or a descriptive message
            indicating why the operation has failed.
        """
        series = storage.read_series(id=_get_series_id())
        if not series:
            return f"Series with ID '{_get_series_id()}' not found."
        
        characters = series.get_characters()
        if not characters:
            return "No characters found in this series."
        
        return characters.values()

    @function_tool
    def get_publisher() -> Publisher | str:
        """
        Get the publisher of the currently selected comic series.
        
        Returns:
            Either the publisher's details or a descriptive message indicating why the operation has failed.
        """
        series = storage.read_series(id=_get_series_id())
        if not series:
            return "No comic series selected. Please select a series to view publisher details."
        
        publisher = series.get_publisher()
        if not publisher:
            return "No publisher found for this series."
        
        return publisher


    @function_tool
    def delete_issue(issue_id: str) -> str:
        """
        Delete an issue from the currently selected comic series.
        NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        
        Args:
            issue_id: The ID of the issue to delete.   NOTE: The should never need to provide an id.
            You should lookup the issue id from the name of the issue provided by the user.   If the 
            name is not an exact match, then you should ask if the name is correct before deleting.
        
        Returns:
            A confirmation message indicating the issue was deleted successfully.
        """
        return "Not implemented yet.  This is a placeholder for the delete_issue function."

    @function_tool
    def delete_character(name: str) -> str:
        """
        Delete a character from the currently selected comic series.
        NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        
        Args:
            name: The name of the character to delete.   
        
        Returns:
            A confirmation message indicating the character was deleted successfully.
        """
        selection = state.selection
        series = storage.read_series(id=_get_series_id())
        if not series:
            return "No comic series selected. Please select a series to delete a character."
        
        series_id = series.id
        character = CharacterModel.read(series=series.id, name=name)
        if not character:
            return f"Character with name '{name}' not found in series '{series.series_title}'."
        
        character.delete()
        state.is_dirty = True
        return f"Character '{name}' deleted successfully from series '{series.series_title}'."
    
    @function_tool
    def create_character(character_name: str, description: str) -> str:
        """
        Create a new character in the currently selected comic series.
        
        Args:
            character_name: The name of the character to create.
            description: A brief description (no more than 3 paragraphs) about the character.  This should serve
               as a summary of the character's background, and role in the comic series.
        
        Returns:
            A confirmation message indicating the character was created successfully.
        """
        # Normalize the identifiers
        series = storage.read_series(id=_get_series_id())
        if not series:
            return "No comic series selected. Please select a series to add a character."
        
        character = CharacterModel(
            series = series.id,
            name = character_name,
            description = description,
        )

        character.write()
        state.change_selection(new=state.selection + [SelectionItem(kind="character", id=character.id, name=character.name)])
        return f"Character '{character.name}' created successfully in series '{series.series_title}'."


    @function_tool
    def create_issue(title: str,  story: str) -> str:
        """
        Create a new issue in the currently selected comic series.
        
        Args:
            title: The title of the issue to create
            story: The story of the issue to create
            issue_number: The issue number of the issue to create.  If not provided, it will be auto-generated.
        
        Returns:
            A confirmation message indicating the issue was created successfully.
        """
        series = storage.read_series(id=_get_series_id())

        issue = Issue(
            id = title.lower().replace(" ", "-"),
            style = "vintage-four-color",
            series = series.id,
            title = title,
            story = story,
            issue_number = series.get_next_issue_number(),
            publication_date = None,  # This can be set later
            price = None,  # This can be set later
            author = None,  # This can be set later
            writer = None,  # This can be set later
            artist= None,  # This can be set later
            colorist= None,  # This can be set later
            creative_minds = None,  # This can be set later
            cover = {},
            scenes = [],
            characters = [],
        )
        
        issue.write()
        state.is_dirty = True
        return f"Issue '{issue.issue_number}' created successfully in series '{series.series_title}'."

    @function_tool
    def create_character_from_reference_image(
        character_name: str, 
        reference_image: str
    ) -> str:
        """
        Create a new character in the currently selected comic series using a reference image.
        
        Args:
            character_name: The name of the character to create.
            reference_image: The filepath of the reference image to use for the character.
        
        Returns:
            A confirmation message indicating the character was created successfully.
        """
        from helpers.generator import invoke_generate_api
        # Normalize the identifiers
        series = storage.read_series(id=_get_series_id())

        prompt = f"""Create a new CharacterModel for {character_name} in the {series.id} comic series using the reference image as a starting point."""
        character:CharacterModel = invoke_generate_api(
            prompt=prompt,
            model=LANGUAGE_MODEL,
            image=reference_image,
            text_format=CharacterModel
        )

        character.write()
        state.change_selection(new=state.selection + [SelectionItem(kind="character", id=character.id, name=character.name)])

        
        return f"Character '{character.name}' created successfully in series '{series.series_title}'."

    return Agent(
        name="Series Agent",
        instructions="""
        You are an interactive artistic assistant who helps human artists and creators 
        compose and update comic book series.
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools = [
            get_details, 
            get_issues,
            get_characters,
            get_publisher,

            create_character,
            create_character_from_reference_image,
            create_issue,

            
            update_description, 
            

            delete_series,
            delete_issue,
            delete_character,

            ],)
                   