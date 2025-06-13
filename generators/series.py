from typing import Tuple, Optional, List
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import APPState
from models.series import Series
from models.character import CharacterModel
from models.publisher import Publisher
from models.issue import Issue


def series_agent(state: APPState) -> Agent:

    def _get_series() -> Optional[Series]:
        """
        Get the currently selected comic series.
        """
        selection = state.selection
        if selection and selection[-1].kind == "series":
            return Series.read(id=selection[-1].id)
        return None
    
    @function_tool
    def get_details() -> str | Series:
        """
        Get the details of the currently selected comic series.
        
        Returns:
            A string containing the details of the current comic series.
        """
        selection = state.selection
        sel_item = selection[-1] if selection else None
        if not sel_item or sel_item.kind != "series":
            return "No comic series selected. Please select a series to view details."
        
        series_id = sel_item.id
        
        series = Series.read(id=series_id)
        return series

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
        from models.series import Series
        selection = state.selection
        series_id = selection[-1].id if selection else None
        if not series_id:
            return "No series selected. Please select a series to update."
        series = Series.read(id=series_id)
        if not series:
            return f"Series with ID '{series_id}' not found."
        
        series.description = description
        series.write()
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
        series = Series.read(id=series_id)
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
        selection = state.selection
        series = _get_series()
        if not series:
            return "Something odd happened.  No series is currently selected."  
        series.delete()
        state.change_selection(selection[:-1])
        state.write()
        return f"Series {series.name} deleted."

    @function_tool
    def get_characters() -> List[CharacterModel] | str:
        """
        Get a list of all characters in the currently selected comic series.
        
        Returns:
            A list of character in the current comic series or a descriptive message
            indicating why the operation has failed.
        """
        selection = state.selection
        sel_item = selection[-1] if selection else None
        if not sel_item or sel_item.kind != "series":
            return "No comic series selected. Please select a series to view characters."
        
        series_id = sel_item.id
        series = Series.read(id=series_id)
        if not series:
            return f"Series with ID '{series_id}' not found."
        
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
        series = _get_series()
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
        return "Not implemented yet.  This is a placeholder for the delete_character function."
    
    @function_tool
    def create_character(character: CharacterModel) -> str:
        """
        Create a new character in the currently selected comic series.
        
        Args:
            character: The character model to create.
        
        Returns:
            A confirmation message indicating the character was created successfully.
        """
        series = _get_series()
        if not series:
            return "No comic series selected. Please select a series to add a character."
        
        character.write()
        state.is_dirty = True
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
        series = _get_series()
        if not series:
            return "No comic series selected. Please select a series to add an issue."
        
        series 

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
            create_issue,

            
            update_description, 
            

            delete_series,
            delete_issue,
            delete_character,

            ],)
                   