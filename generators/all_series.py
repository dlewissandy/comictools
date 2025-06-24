from typing import Tuple, Optional, List
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import APPState
from storage.generic import GenericStorage


def all_series_agent(state: APPState) -> Agent:
    from schema.series import Series
    from gui.selection import SelectionItem
    storage: GenericStorage = state.storage
    
    @function_tool
    def get_all_comic_series_names() -> list[str]:
        """
        Get a list of the names of all comic series that a user has created.
        
        Returns:
            A list of comic series names.
        """
        series = storage.read_all_series()
        return [s.name for s in series]

    @function_tool
    def get_all_comic_series() -> list[Series]:
        """
        Get a list of all comic series that a user has created.
        
        Returns:
            A list of comic series names.
        """
        return storage.read_all_series()

    @function_tool
    def find_comic_series_by_name(name: str) -> Series:
        """
        Get a comic series' definition by its name.
        
        Args:
            name: The name (or title) of the comic series.
        
        Returns:
            The Series object if found, otherwise None.
        """
        return storage.find_series(name=name)

    @function_tool
    def verify_publisher_exists(publisher_name: str) -> str:
        """
        Verify that a publisher exists in the database.
        
        Args:
            publisher_name: The name of the publisher to verify.
        
        Returns:
            A string indicating if the publisher exists.
        """
        publisher = storage.find_publisher(name=publisher_name)
        if publisher is None:
            publishers = storage.read_all_publishers()
            names = [p.name for p in publishers]
            return f"Publisher '{publisher_name}' not found.  It should be one of the following: {', '.join(names)}"
        return "Publisher exists."

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
        if storage.find_series(name=series_title) is not None:
            logger.error(f"Series with title '{series_title}' already exists.")
            return f"Series with title '{series_title}' already exists."
        else:
            logger.info(f"The title '{series_title}' is available.")
        series = Series(series_title=series_title, description=description, publisher=publisher)
        new_id = storage.create_series(series)
        selection = state.selection
        new_itm = SelectionItem(name=series.series_title, id=new_id, kind='series')
        new_sel = [s for s in selection]+[new_itm]
        state.change_selection(new=new_sel, clear_history=False)
        state.is_dirty = True
        return series

    @function_tool
    def select_comic_series(name: str) -> str:
        """
        Select a comic series by name.   This is a precursor for editing its 
        properties.
        
        Args:
            name: The name of the comic series to select.
        
        Returns:
            A status message indicating the result of the selection.
        """
        series = storage.find_series(name=name)
        if series is None:
            return f"Comic series '{name}' not found.  Maybe try looking at the list of comic series first?"
        sel_itm = SelectionItem(
            id=series.id,
            name=series.name,
            kind="series",
        )
        state.selection.append(sel_itm)
        state.is_dirty = True
        return f"Selected comic series: {series.name}"

    @function_tool
    def delete_comic_series(name: str) -> str:
        """
        Delete a comic series by name.   You MUST ask for confirmation before using this tool.
        
        Args:
            name: The name of the comic series to delete.
        
        Returns:
            A status message indicating the result of the deletion.
        """
        series = storage.find_series(name=name)
        if series is None:
            return f"Comic series '{name}' not found."
        storage.delete_series(id = series.id)
        state.is_dirty = True
        return f"Deleted comic series: {series.name}"


    return Agent(
        name="Comic Series Assistant",
        instructions="""
        You are an interactive artistic assistant who helps human artists and creators manage
        comic book series/title assets.  

        You are capable of searching for, updating, deleting or creating any of these assets.   

        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools = [
            select_comic_series,
            find_comic_series_by_name,
            get_all_comic_series_names,
            get_all_comic_series,
            create_comic_series,
            delete_comic_series,

            verify_publisher_exists
                    ]
    )

