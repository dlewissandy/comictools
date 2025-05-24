from typing import Optional
from loguru import logger
from agents import function_tool
from nicegui import ui
from style.comic import ComicStyle
from models.series import Series
from models.publisher import Publisher
from gui.state import GUIState
from gui.selection import SelectionItem, change_selection

@function_tool
def get_publisher_names() -> list[str]:
    """
    Get a list of all publisher names.
    
    Returns:
        A list of publisher names.
    """
    from models.publisher import Publisher
    publishers = Publisher.read_all()
    return [publisher.name for publisher in publishers]

@function_tool
def get_publisher_by_name(name: str) -> Publisher | None:
    """
    Get a publisher's definition by its name.
    
    Args:
        name: The name of the publisher.
    
    Returns:
        The Publisher object if found, otherwise None.
    """
    from models.publisher import Publisher
    id = name.replace(" ", "-").lower()
    publisher = Publisher.read(id)
    return publisher

def wrap_create_publisher(state: GUIState):
    
    @function_tool
    def create_publisher(name: str, description: Optional[str]) -> Publisher | str | None:
        """
        Create a new publisher with the given name.
        
        Args:
            name: The name of the new publisher.
            description: An optional description of the publisher.

        
        Returns:
            The created Publisher object or an error message if the publisher already exists.
        """
        from models.publisher import Publisher
        # check to see if the publisher already exists.
        if Publisher.read(name=name) is not None:
            logger.error(f"Publisher with name '{name}' already exists.")
            return f"Publisher with name '{name}' already exists."
        
        logger.info(f"The name '{name}' is available.")
        publisher = Publisher(name=name, logo=None, description=description, image=None)
        publisher.write()
        selection = state.get("selection")
        new_itm = SelectionItem(name=publisher.name, id=publisher.id, kind='publisher')
        new_sel = [s for s in selection]+[new_itm]
        change_selection(state, new=new_sel, clear_history=False)
        state["is_dirty"] = True
        return publisher
    return create_publisher

@function_tool
def get_comic_style_names() -> list[str]:
    """
    Get a list of all comic style names.
    
    Returns:
        A list of comic style names.
    """
    from style.comic import ComicStyle
    styles = ComicStyle.read_all()
    return [style.name for style in styles]

@function_tool
def get_comic_style_by_name(name: str) -> ComicStyle:
    """
    Get a comic style's definition by its name.
    
    Args:
        name: The name of the comic style.
    
    Returns:
        The ComicStyle object if found, otherwise None.
    """
    from style.comic import ComicStyle
    id = name.replace(" ", "-").lower()
    style = ComicStyle.read(id)
    return None

@function_tool
def get_comic_series_names() -> list[str]:
    """
    Get a list of all comic series that a user has created.
    
    Returns:
        A list of comic series names.
    """
    series = Series.read_all()
    return [s.series_title for s in series]

@function_tool
def get_comic_series_by_name(name: str) -> Series:
    """
    Get a comic series' definition by its name.
    
    Args:
        name: The name (or title) of the comic series.
    
    Returns:
        The Series object if found, otherwise None.
    """
    return Series.read(series_title=name)

def wrap_create_comic_series(state: GUIState) -> Series | str | None:
    """
    Create a new comic series with the given title.
    
    Args:
        state: The GUI elements to interact with.
        series_title: The title of the new comic series.
    
    Returns:
        The created Series object.
    """
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
    return create_comic_series
    
def wrap_render_logo(state: GUIState):
    """
    Render the logo for a publisher.
    
    Args:
        state: The GUI elements to interact with.
    
    Returns:
        The rendered logo image.
    """
    @function_tool
    def render_logo() -> str:
        """
        Render the logo.
        
        Returns:
            A status message indicating the result of the rendering.
        """
        from models.publisher import Publisher
        selection = state.get("selection")
        kind = selection[-1].kind
        if kind != "publisher":
            msg = f"The selection is not a publisher: {kind}"
            logger.error(msg)
            return msg
        
        publisher_id = selection[-1].id
        publisher = Publisher.read(id=publisher_id)
        if publisher is None:
            msg = f"Publisher with ID '{publisher_id}' not found."
            logger.error(msg)
            return msg
        
        img = publisher.render()
        if img is None:
            msg = f"Logo for publisher '{publisher.name}' could not be rendered."
            logger.error(msg)
            return msg
        
        state["is_dirty"] = True        
        return f"The logo for publisher '{publisher.name}' has been rendered and is saved to {img}.jpg"
    
    return render_logo