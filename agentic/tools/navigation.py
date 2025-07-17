from loguru import logger
from agents import function_tool, Tool, RunContextWrapper

from gui.state import APPState
from gui.selection import SelectionItem, SelectedKind
from storage.generic import GenericStorage
from schema import (
    Publisher,
    ComicStyle,
    Series,
    Issue,
    SceneModel,
    Panel,
    Cover,
    CoverLocation,
    CharacterModel,
    CharacterVariant,
    CoverLocation,
    Cover
)  

@function_tool
def select_publisher(wrapper: RunContextWrapper[APPState], publisher_id: str) -> str:
    """
    Select a publisher by identifier.   This is a precursor for editing its 
    properties.
    
    Args:
        publisher_id: The identifier of the publisher to select.

    Returns:
        A status message indicating the result of the selection.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    publisher: Publisher = storage.read_object(cls=Publisher, primary_key={"publisher_id": publisher_id})
    if publisher is None:
        return f"Publisher '{publisher_id}' not found.  Maybe try looking at the list of publishers first?"
    sel_itm = SelectionItem(
        id=publisher.publisher_id,
        name=publisher.name,
        kind=SelectedKind.PUBLISHER,
    )
    new_selection = state.selection + [sel_itm]
    state.change_selection(new=new_selection)
    return f"Selected publisher: {publisher.publisher_id}"

@function_tool
def select_series(wrapper: RunContextWrapper[APPState], series_id: str) -> str:
    """
    Select a comic series by ID.   This is a precursor for editing its
    properties.
    
    Args:
        series_id: The ID of the comic series to select.

    Returns:
        A status message indicating the result of the selection.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    series = storage.read_object(Series, {"series_id": series_id})
    if series is None:
        return f"Comic series '{series_id}' not found.  Maybe try looking at the list of comic series first?"
    series: Series = series
    sel_itm = SelectionItem(
        id=series.series_id,
        name=series.name,
        kind=SelectedKind.SERIES,
    )
    state.selection.append(sel_itm)
    state.is_dirty = True
    return f"Selected comic series: {series.name}"

@function_tool
def select_comic_style(wrapper: RunContextWrapper[APPState], style_id: str) -> str:
    """
    Select a comic style by name.   This is a precursor for editing its 
    properties.
    
    Args:
        name: The name of the comic style to select.
    
    Returns:
        A status message indicating the result of the selection.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    style = storage.read_object(ComicStyle, {"style_id": style_id})
    if style is None:
        return f"Comic style '{style_id}' not found.  Maybe try looking at the list of comic styles first?"
    style: ComicStyle = style
    sel_itm = SelectionItem(
        id=style.style_id,
        name=style.name,
        kind=SelectedKind.STYLE,
    )
    state.change_selection(new=[s for s in state.selection] + [sel_itm])
    return f"Selected comic style: {style.name}"
