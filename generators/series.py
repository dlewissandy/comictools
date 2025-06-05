from typing import Tuple, Optional, List
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import GUIState
from models.series import Series


def series_agent(state: GUIState) -> Agent:
    from models.issue import Issue
    
    @function_tool
    def get_details() -> str | Series:
        """
        Get the details of the currently selected comic series.
        
        Returns:
            A string containing the details of the current comic series.
        """
        selection = state.get("selection")
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
        selection = state.get("selection")
        series_id = selection[-1].id if selection else None
        if not series_id:
            return "No series selected. Please select a series to update."
        series = Series.read(id=series_id)
        if not series:
            return f"Series with ID '{series_id}' not found."
        
        series.description = description
        series.write()
        return f"Description for series '{series.series_title}' updated successfully."
    
    @function_tool
    def get_issues() -> List[Issue]:
        """
        Get a list of all the issues in the currently selected comic series.
        
        Returns:
            A list of the names of the issues in the current comic series.
        """
        selection = state.get("selection")
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

    return Agent(
        name="Series Agent",
        instructions="""
        You are an interactive artistic assistant who helps human artists and creators 
        compose and update comic book series.    

        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools = [get_details, update_description, get_issues],)
                   