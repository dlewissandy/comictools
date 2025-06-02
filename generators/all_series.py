from typing import Tuple, Optional, List
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import GUIState
from models.series import Series
from gui.selection import change_selection, SelectionItem
from style.comic import ComicStyle


def all_series_agent(state: GUIState) -> Agent:
    from models.series import Series
    from gui.selection import SelectionItem

    @function_tool
    def get_all_comic_series_names() -> list[str]:
        """
        Get a list of all comic series that a user has created.
        
        Returns:
            A list of comic series names.
        """
        series = Series.read_all()
        return [s.series_title for s in series]

    @function_tool
    def find_comic_series_by_name(name: str) -> Series:
        """
        Get a comic series' definition by its name.
        
        Args:
            name: The name (or title) of the comic series.
        
        Returns:
            The Series object if found, otherwise None.
        """
        return Series.read(series_title=name)

   
    @function_tool
    def create_comic_series(series_title: str, description: Optional[str], publisher: Optional[str]) -> Series:
        """
        Create a new comic series with the given title.
        
        Args:
            series_title: The title of the new comic series.
        
        Returns:
            The created Series object.
        """
        # check to see if the series already exists.
        if Series.read(series_title=series_title) is not None:
            logger.error(f"Series with title '{series_title}' already exists.")
            return f"Series with title '{series_title}' already exists."
        else:
            logger.info(f"The title '{series_title}' is available.")
        series = Series(series_title=series_title, description=description, publisher=publisher)
        series.write()
        selection = state.get("selection")
        new_itm = SelectionItem(name=series.series_title, id=series.id, kind='series')
        new_sel = [s for s in selection]+[new_itm]
        change_selection(state, new=new_sel, clear_history=False)
        state["is_dirty"] = True
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
        series = Series.read(name=name.lower().replace(" ", "-"))
        if series is None:
            return f"Comic series '{name}' not found.  Maybe try looking at the list of comic series first?"
        sel_itm = SelectionItem(
            id=series.id,
            name=series.name,
            kind="series",
        )
        state["selection"].append(sel_itm)
        state["is_dirty"] = True
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
        series = Series.read(id=name.lower().replace(" ", "-"))
        if series is None:
            return f"Comic series '{name}' not found."
        path = series.path()
        if path is None:
            return f"Comic series '{name}' has no associated file to delete."
        # REMOVE THE FOLDER THAT THE SERIES IS STORED IN.
        import shutil
        try:
            shutil.rmtree(path)
        except Exception as e:
            logger.error(f"Failed to delete series folder '{path}': {e}")
            return f"Failed to delete series folder '{path}': {e}"

        # The selection does not need to change, but we do need to refresh the display to 
        # remove the deleted series from the list.
        state["is_dirty"] = True
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
            create_comic_series,
            delete_comic_series
                    ]
    )

