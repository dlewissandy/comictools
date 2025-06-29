from typing import Tuple, Optional, List
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool
from gui.state import APPState
from schema import Cover


def cover_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    from generators.tools import dereference_cover as _get_cover
    from generators.tools import delete_cover as _delete_cover
    
    @function_tool
    def delete_cover() -> str:
        """
        Delete the currently selected cover.   NOTE: YOU MUST ASK FOR
        CONFIRMATION BEFORE DELETING A COVER.   THIS OPERATION CANNOT BE UNDONE.
        
        Returns:
            A message indicating the result of the deletion operation.
        """
        cover_or_str = _get_cover(state=state, index=-3)
        if isinstance(cover_or_str, str):
            return cover_or_str
        cover: Cover = cover_or_str
        return _delete_cover(state=state, series_id=cover.series_id, issue_id=cover.issue_id, location=cover.location)
    
    @function_tool
    def render_cover() -> str:
        """
        Render the cover for the currently selected comic book issue.
        
        Returns:
            A string indicating the status of the rendering operation.
        """
        cover_or_str = _get_cover(state=state, index=-3)
        if isinstance(cover_or_str, str):
            return cover_or_str

        cover: Cover = cover_or_str
        result = cover.render()
        state.is_dirty = True
        return result
        

        
        


    return Agent(
        name="cover",
        instructions="Agent for managing comic book covers.\n\n"+BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        
        tools=[
            tools.get('get_current_selection', None),

            # Getters
            tools.get('find_cover', None),

            delete_cover,

            render_cover,
        ]
    )

