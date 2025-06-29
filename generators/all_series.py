from typing import Optional
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool
from gui.state import APPState
from storage.generic import GenericStorage
from helpers.file import normalize_id


def all_series_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    from schema import Series
    from gui.selection import SelectionItem, SelectedKind
    storage: GenericStorage = state.storage
    
    @function_tool
    def create_comic_series(series_title: str, description: Optional[str], publisher: Optional[str]) -> Series:
        """
        Create a new comic series with the given title.
        
        Args:
            series_title: The title of the new comic series.
            description: An optional description of the comic series.   This should be 2-5 paragraphs about the series, its themes, characters and setting.  This is intended for writers and artists to understand the series and generate content for it.   IT IS NOT INTENDED FOR THE READER, OR MARKETING.
            publisher: An optional name of the publisher for the comic series.   If povided, YOU MUST verify that the publisher exists in the database.
        
        Returns:
            The created Series object.
        """
        # check to see if the series already exists.
        series_id = normalize_id(series_title)
        if storage.read_object(Series, {"series_id": series_id}) is not None:
            logger.error(f"Series with title '{series_title}' already exists.")
            return f"Series with title '{series_title}' already exists."
        else:
            logger.info(f"The title '{series_title}' is available.")
        series = Series(series_id=series_id, name=series_title, description=description, publisher_id=publisher)
        new_id = storage.create_object(data=series)
        selection = state.selection
        new_itm = SelectionItem(name=series.name, id=new_id, kind=SelectedKind.SERIES)
        new_sel = [s for s in selection]+[new_itm]
        state.change_selection(new=new_sel, clear_history=False)
        state.is_dirty = True
        return series

    @function_tool
    def select_comic_series(series_id: str) -> str:
        """
        Select a comic series by ID.   This is a precursor for editing its
        properties.
        
        Args:
            series_id: The ID of the comic series to select.

        Returns:
            A status message indicating the result of the selection.
        """
        series = storage.read_object(Series, {"series_id": series_id})
        if series is None:
            return f"Comic series '{series_id}' not found.  Maybe try looking at the list of comic series first?"
        sel_itm = SelectionItem(
            id=series.series_id,
            name=series.name,
            kind=SelectedKind.SERIES,
        )
        state.selection.append(sel_itm)
        state.is_dirty = True
        return f"Selected comic series: {series.name}"




    return Agent(
        name="Comic Series Assistant",
        instructions="""
        You are an interactive artistic assistant who helps human artists and creators manage
        comic book assests.  You are a specialist on comic book series (sometimes called titles).
        You can help users understand, and modify your extensive database of comic book series.   

        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools = [
            tools.get('get_current_selection', None),

            # Getters
            select_comic_series,

            
            tools.get('find_series', None),
            tools.get('find_publisher', None),

            tools.get('get_all_series', None),
            tools.get('get_all_publishers', None),

            create_comic_series,
            tools.get('delete_series', None),
        ]
    )

