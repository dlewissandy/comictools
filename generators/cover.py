from typing import Tuple, Optional, List
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import APPState
from schema.series import Series
from schema.issue import Issue
from schema.publisher import Publisher
from schema.style.comic import ComicStyle


def cover_agent(state: APPState) -> Agent:
    from schema.panel import TitleBoardModel, CoverLocation, FrameLayout, CharacterRef
    from generators.tools import dereference_cover as _get_cover
    from generators.tools import delete_cover as _delete_cover
    from generators.tools import dereference_series as _get_series
    from generators.tools import dereference_issue as _get_issue
    from generators.tools import get_publisher as _get_publisher
    from generators.tools import get_style as _get_style
    
    @function_tool
    def get_cover() -> TitleBoardModel:
        """
        Get the currently selected cover.
        
        Returns:
            The currently selected cover.
        """
        logger.trace("get_cover")
        logger.critical(state.selection)
        return _get_cover(state=state, index=-3)
        
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
        cover: TitleBoardModel = cover_or_str
        return _delete_cover(state=state, series_id=cover.series, issue_id=cover.issue, location=cover.location)
    
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

        cover: TitleBoardModel = cover_or_str
        result = cover.render()
        state.is_dirty = True
        return result
        

        
        


    return Agent(
        name="cover",
        instructions="Agent for managing comic book covers.\n\n"+BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        
        tools=[
            get_cover,

            delete_cover,

            render_cover,
        ]
    )

