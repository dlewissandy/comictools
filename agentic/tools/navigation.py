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

    # EVERY HOUSE IS MOUNTED: resolve which house holds it, then walk the
    # same canonical trail the UI walks — never append to the current room
    from gui.routes import _storage_holding
    from storage import registry as _reg
    st = _storage_holding(storage, Publisher, {"publisher_id": publisher_id},
                          house_of=_reg.house_of_publisher, key=publisher_id)
    publisher: Publisher = st.read_object(cls=Publisher, primary_key={"publisher_id": publisher_id})
    if publisher is None:
        return f"Publisher '{publisher_id}' not found.  Maybe try looking at the list of publishers first?"
    state.change_selection(new=[
        SelectionItem(id=None, name="Publishers", kind=SelectedKind.ALL_PUBLISHERS),
        SelectionItem(id=publisher.publisher_id, name=publisher.name,
                      kind=SelectedKind.PUBLISHER)])
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

    from gui.routes import series_ancestry, _storage_holding
    from storage import registry as _reg
    st = _storage_holding(storage, Series, {"series_id": series_id},
                          house_of=_reg.house_of_series, key=series_id)
    series: Series = st.read_object(Series, {"series_id": series_id})
    if series is None:
        return f"Comic series '{series_id}' not found.  Maybe try looking at the list of comic series first?"
    # THE ONE TRAIL: Publishers → house → series, same as every UI door
    state.change_selection(new=series_ancestry(storage, series_id))
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
    from gui.routes import style_ancestry, _storage_holding
    from storage import registry as _reg
    st = _storage_holding(storage, ComicStyle, {"style_id": style_id},
                          house_of=_reg.house_of_style, key=style_id)
    style: ComicStyle = st.read_object(ComicStyle, {"style_id": style_id})
    if style is None:
        return f"Comic style '{style_id}' not found.  Maybe try looking at the list of comic styles first?"
    # THE ONE TRAIL: Publishers → house → style, so the thread keys the
    # same conversation the UI keys
    state.change_selection(new=style_ancestry(storage, style_id))
    return f"Selected comic style: {style.name}"


@function_tool
def select_issue(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    Open an issue — the book lands on the table.  This is a precursor for
    working on its scenes, panels and covers.

    Args:
        series_id: The series the issue belongs to.
        issue_id: The issue to open.

    Returns:
        A status message indicating the result of the selection.
    """
    from schema import Issue
    state: APPState = wrapper.context
    from gui.routes import series_ancestry, _storage_holding
    from storage import registry as _reg
    st = _storage_holding(state.storage, Series, {"series_id": series_id},
                          house_of=_reg.house_of_series, key=series_id)
    issue = st.read_object(Issue, {"series_id": series_id, "issue_id": issue_id})
    if issue is None:
        return (f"Issue '{issue_id}' not found in series '{series_id}'.  "
                f"Maybe list the series' issues first?")
    state.change_selection(new=[*series_ancestry(state.storage, series_id),
                                SelectionItem(id=issue.issue_id, name=issue.name,
                                              kind=SelectedKind.ISSUE)])
    return f"Opened the issue: {issue.name}"


@function_tool
def select_character(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str) -> str:
    """
    Open a character's own room.  This is a precursor for working on their
    looks, wardrobe and reference sheets.

    Args:
        series_id: The series the character belongs to.
        character_id: The character to open.

    Returns:
        A status message indicating the result of the selection.
    """
    from schema import CharacterModel
    state: APPState = wrapper.context
    from gui.routes import series_ancestry, _storage_holding
    from storage import registry as _reg
    st = _storage_holding(state.storage, Series, {"series_id": series_id},
                          house_of=_reg.house_of_series, key=series_id)
    ch = st.read_object(CharacterModel, {"series_id": series_id, "character_id": character_id})
    if ch is None:
        return (f"Character '{character_id}' not found in series '{series_id}'.  "
                f"Maybe read the series bible first?")
    state.change_selection(new=[*series_ancestry(state.storage, series_id),
                                SelectionItem(id=ch.character_id, name=ch.name,
                                              kind=SelectedKind.CHARACTER)])
    return f"Opened the character: {ch.name}"
