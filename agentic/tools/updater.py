from typing import Optional
from agents import function_tool, Tool, RunContextWrapper
from pydantic import BaseModel
from gui.state import APPState
from gui.selection import SelectionItem, SelectedKind
from schema.enums import FrameLayout
from schema.style.comic import ComicStyle
from schema.style.dialog import BubbleStyle
from storage.generic import GenericStorage
from schema import (
    CharacterModel,
    CharacterRef,
    CharacterVariant,
    Issue,
    Cover,
    Setting,
    Prop,
    Publisher,
    Series,
    SceneModel,
    Panel,
    ArtStyle,
    BubbleStyle,
    DialogType,
    CharacterStyle
)
from .context import read_context

def update_attribute(wrapper: RunContextWrapper[APPState],
    cls: type[BaseModel],
    primary_key: dict[str, str],
    attribute: str,
    value: Optional[str],
    key: Optional[str]=None) -> str:
    """
    Update an attribute of the specified object.
    
    Args:
        cls (type[BaseModel]): The class of the object to update.
        primary_key (dict[str, str]): The primary key
        attribute (str): The name of the attribute to update.
        value (Optional[str]): The new value for the attribute.
        key (Optional[str]): The key for the attribute if it is a dictionary field.
    
    Returns:
        A status message indicating the result of the update.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    obj: BaseModel = storage.read_object(cls=cls, primary_key=primary_key)
    if obj is None:
        return f"{cls.__name__} with ID '{primary_key}' not found."
    if not hasattr(obj, attribute):
        return f"Attribute '{attribute}' does not exist on {cls.__name__}."
    if key is not None:
        if not isinstance(getattr(obj, attribute), dict):
            return f"Attribute '{attribute}' is not a dictionary and cannot be updated with a key."
        getattr(obj, attribute)[key] = value
    else:
        setattr(obj, attribute, value)
    storage.update_object(data=obj)
    state.is_dirty = True
    return f"Updated {attribute} to '{value}' for {cls.__name__} with ID '{primary_key}'."


@function_tool
def update_character_description(wrapper: RunContextWrapper[APPState], description: str) -> str:
    """
    Update the description of the currently selected character.

    Args:
        description: The new description for the character.
    
    Returns:
        A message indicating the result of the update operation.
    """
    state: APPState = wrapper.context
    series_id = state.selection[-2].id  # Assuming the second last item is the series
    character_id = state.selection[-1].id  # Assuming the last item is the character

    primary_key = {'character_id': character_id, 'series_id': series_id}
    return update_attribute(wrapper, CharacterModel, primary_key, 'description', description)

@function_tool
def update_cover_description(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, cover_id: str, description: str) -> str:
    """
    Update the description of the specified cover.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the comic book issue.
        cover_id: The ID of the cover to update.
        description: The new description for the cover.
    
    Returns:
        A message indicating the result of the update operation.
    """
    state: APPState = wrapper.context

    primary_key = {'cover_id': cover_id, 'series_id': series_id, 'issue_id': issue_id}
    return update_attribute(wrapper, Cover, primary_key, 'description', description)

@function_tool
def update_cover_style(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, cover_id: str, style_id: str) -> str:
    """
    Update the style of the specified cover.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the comic book issue.
        cover_id: The ID of the cover to update.
        style_id: The new style ID for the cover.  NOTE:  You should verify that this style exists prior to running this tool (e.g. by getting all styles).  Failure
           to do so may result in an error.
    
    Returns:
        A message indicating the result of the update operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    style: ComicStyle | None = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if style is None:
        return f"Cannot update style.   Style with ID '{style_id}' not found.   Perhaps you should double check against the list of available styles."
    
    primary_key = {'cover_id': cover_id, 'series_id': series_id, 'issue_id': issue_id}
    return update_attribute(wrapper, Cover, primary_key, 'style_id', style_id)

# -------------------------------------------------------------------------
# ISSUE UPDATING TOOLS
# -------------------------------------------------------------------------

@function_tool
def update_cover_aspect_ratio(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    issue_id: str,
    cover_id: str,
    aspect_ratio: FrameLayout
) -> str:
    """
    Update the aspect ratio of the specified cover.

    Args:
        wrapper: The context wrapper.
        series_id: The ID of the comic series.
        issue_id: The ID of the comic book issue.
        cover_id: The ID of the cover to update.
        aspect_ratio: The new aspect ratio for the cover.

    Returns:
        A message indicating the result of the update operation.
    """
    primary_key = {'cover_id': cover_id, 'series_id': series_id, 'issue_id': issue_id}
    return update_attribute(wrapper, Cover, primary_key, 'aspect', aspect_ratio)

@function_tool
def update_issue_story(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, story: str) -> str:
    """
    Update the story of the currently selected comic book issue.   Note, the story should
    be a summary of the issue's plot, not a full script.   It should be in sufficient detail as
    to allow the creative team to understand the narrative flow and key events, and to produce
    the necessary artwork and dialogue.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the comic book issue.
        story (str): The new story for the issue.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"issue_id": issue_id, "series_id": series_id}
    return update_attribute(
        wrapper=wrapper, 
        cls=Issue, 
        primary_key=pk,
        attribute="story", 
        value=story)

@function_tool
def update_issue_publication_date(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, publication_date: Optional[str]) -> str:
    """
    Update the publication date of the currently selected comic book issue.
    
    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the comic book issue.
        publication_date (str): The new publication date for the issue.  This can
            be empty if the publication date is not known or not applicable.
    
    Returns:
        A status message indicating the result of the update.
    """
    pk = {"issue_id": issue_id, "series_id": series_id}
    return update_attribute(
        wrapper=wrapper,
        cls=Issue,
        primary_key=pk,
        attribute="publication_date", 
        value=publication_date)

@function_tool
def update_issue_price(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, price: Optional[float]) -> str:
    """
    Update the price of the currently selected comic book issue.
    
    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the comic book issue.
        price (Optional[float]): The new price for the issue.  This can be None if the price is not known or not applicable.
    
    Returns:
        A status message indicating the result of the update.
    """

    pk = {"issue_id": issue_id, "series_id": series_id}
    return update_attribute(
        wrapper=wrapper,
        cls=Issue,
        primary_key=pk,
        attribute="price",
        value=price)

@function_tool
def update_issue_writer(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, writer: Optional[str]) -> str:
    """
    Update the writer of the currently selected comic book issue.
    
    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the comic book issue.
        writer (Optional[str]): The new writer for the issue.  This can be None if the writer is not known or not applicable.
    
    Returns:
        A status message indicating the result of the update.
    """
    pk = {"issue_id": issue_id, "series_id": series_id}
    return update_attribute(
        wrapper=wrapper,
        cls=Issue,
        primary_key=pk,
        attribute="writer",
        value=writer)

@function_tool
def update_issue_artist(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, artist: Optional[str]) -> str:
    """
    Update the artist of the currently selected comic book issue.
    
    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the comic book issue.
        artist (Optional[str]): The new artist for the issue.  This can be None if the artist is not known or not applicable.
    
    Returns:
        A status message indicating the result of the update.
    """
    pk = {"issue_id": issue_id, "series_id": series_id}
    return update_attribute(
        wrapper=wrapper,
        cls=Issue,
        primary_key=pk,
        attribute="artist",
        value=artist)

@function_tool
def update_issue_colorist(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, colorist: Optional[str]) -> str:
    """
    Update the colorist of the currently selected comic book issue.

    Args:
        colorist (Optional[str]): The new colorist for the issue.  This can be None if the
        colorist is not known or not applicable.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"issue_id": issue_id, "series_id": series_id}
    return update_attribute(
        wrapper=wrapper,
        cls=Issue,
        primary_key=pk,
        attribute="colorist",
        value=colorist)

@function_tool
def update_issue_creative_minds(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, creative_minds: Optional[str]) -> str:
    """
    Update the creative minds of the currently selected comic book issue.
    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the comic book issue.
        creative_minds (Optional[str]): The new creative minds for the issue.  This can be None if the
        creative minds are not known or not applicable.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"issue_id": issue_id, "series_id": series_id}
    return update_attribute(
        wrapper=wrapper,
        cls=Issue,
        primary_key=pk,
        attribute="creative_minds",
        value=creative_minds)

# -------------------------------------------------------------------------
# PUBLISHER UPDATING TOOLS
# -------------------------------------------------------------------------

@function_tool
def update_publisher_description(wrapper: RunContextWrapper[APPState], publisher_id: str, value: str) -> str:
    """
    Update the description for a publisher publisher.

    Args:
        publisher_id: The identifier of the publisher to update.
        value: The new description of the publisher.
    
    Returns:
        A status message indicating the result of the update.
    """
    pk = {"publisher_id": publisher_id}
    return update_attribute(
        wrapper=wrapper,
        cls=Publisher,
        primary_key=pk,
        attribute="description",
        value=value)

@function_tool
def update_logo_description(wrapper: RunContextWrapper[APPState], publisher_id: str, value: str) -> str:
    """
    Update the logo description for a publisher.

    Args:
        publisher_id: The identifier of the publisher to update.
        value: The new logo description of the publisher.
    
    Returns:
        A status message indicating the result of the update.
    """
    pk = {"publisher_id": publisher_id}
    return update_attribute(
        wrapper=wrapper,
        cls=Publisher,
        primary_key=pk,
        attribute="logo",
        value=value,
        key=None)


@function_tool
def update_series_description(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
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
    return update_attribute(
        wrapper=wrapper,
        cls=Series,
        primary_key={"series_id": series_id},
        attribute="description",
        value=description
    )

# -------------------------------------------------------------------------
# TOOLS FOR UPDATING VARIANTS
# -------------------------------------------------------------------------

@function_tool
def update_variant_description(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str, description: str) -> str:
    """
    Update the general description of the currently selected character variant.  This field
    should provide a high-level overview of the character's role, personality, and significance
    within the comic series.   It should not be used to describe specific appearances or attire,
    or attribues that are better suited for other fields (age, gender, race, height, etc.).
    
    Args:

        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to update.
        description: The new general description for the character variant.
    
    Returns:
        A confirmation message indicating the description was updated successfully.
    """
    primary_key = {
        "series_id": series_id,
        "character_id": character_id,
        "variant_id": variant_id
    }
    return update_attribute(
        wrapper=wrapper,
        cls=CharacterVariant,
        primary_key=primary_key,
        attribute="description",
        value=description
    )

@function_tool
def update_variant_appearance(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str, appearance: str) -> str:
    """
    Update the appearance of the currently selected character variant.
    
    Args:
        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to update.
        appearance: The new appearance description for the character variant.
    
    Returns:
        A confirmation message indicating the appearance was updated successfully.
    """
    primary_key = {
        "series_id": series_id,
        "character_id": character_id,
        "variant_id": variant_id
    }
    return update_attribute(
        wrapper=wrapper,
        cls=CharacterVariant,
        primary_key=primary_key,
        attribute="appearance",
        value=appearance
    )

@function_tool
def update_variant_attire(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str, attire: str) -> str:
    """
    Update the attire of the currently selected character variant.
    
    Args:
        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to update.
        attire: The new attire description for the character variant.
    
    Returns:
        A confirmation message indicating the attire was updated successfully.
    """
    primary_key = {
        "series_id": series_id,
        "character_id": character_id,
        "variant_id": variant_id
    }
    return update_attribute(
        wrapper=wrapper,
        cls=CharacterVariant,
        primary_key=primary_key,
        attribute="attire",
        value=attire
    )

@function_tool
def update_variant_behavior(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str, behavior: str) -> str:
    """
    Update the behavior of the currently selected character variant.
    
    Args:
        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to update.
        behavior: The new behavior description for the character variant.
    
    Returns:
        A confirmation message indicating the behavior was updated successfully.
    """
    primary_key = {
        "series_id": series_id,
        "character_id": character_id,
        "variant_id": variant_id
    }
    return update_attribute(
        wrapper=wrapper,
        cls=CharacterVariant,
        primary_key=primary_key,
        attribute="behavior",
        value=behavior
    )

@function_tool
def update_variant_race(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str, race: str) -> str:
    """
    Update the race of the currently selected character variant.
    
    Args:
        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to update.
        race: The new race description for the character variant.

    Returns:
        A confirmation message indicating the race was updated successfully.
    """
    primary_key = {
        "series_id": series_id,
        "character_id": character_id,
        "variant_id": variant_id
    }
    return update_attribute(
        wrapper=wrapper,
        cls=CharacterVariant,
        primary_key=primary_key,
        attribute="race",
        value=race
    )

@function_tool
def update_variant_age(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str, age: str) -> str:
    """
    Update the age of the currently selected character variant.
    
    Args:
        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to update.
        age: The new age for the character variant.
    
    Returns:
        A confirmation message indicating the age was updated successfully.
    """
    primary_key = {
        "series_id": series_id,
        "character_id": character_id,
        "variant_id": variant_id
    }
    return update_attribute(
        wrapper=wrapper,
        cls=CharacterVariant,
        primary_key=primary_key,
        attribute="age",
        value=age
    )

@function_tool
def update_variant_gender(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str, gender: str) -> str:
    """
    Update the gender of the currently selected character variant.
    
    Args:
        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to update.
        gender: The new gender description for the character variant.

    Returns:
        A confirmation message indicating the gender was updated successfully.
    """
    primary_key = {
        "series_id": series_id,
        "character_id": character_id,
        "variant_id": variant_id
    }
    return update_attribute(
        wrapper=wrapper,
        cls=CharacterVariant,
        primary_key=primary_key,
        attribute="gender",
        value=gender
    )

@function_tool
def update_variant_height(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, variant_id: str, height: str) -> str:
    """
    Update the height of the currently selected character variant.
    
    Args:
        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to update.
        height: The new height description for the character variant.
    
    Returns:
        A confirmation message indicating the height was updated successfully.
    """
    primary_key = {
        "series_id": series_id,
        "character_id": character_id,
        "variant_id": variant_id
    }
    return update_attribute(
        wrapper=wrapper,
        cls=CharacterVariant,
        primary_key=primary_key,
        attribute="height",
        value=height
    )

@function_tool
def update_style_description(wrapper: RunContextWrapper, style_id: str, value: str) -> str:
    """
    Update the description of the specified comic style.

    Args:
        style_id: The identifier of the style to update
        value: The new description for the comic style. 

    Returns:
        A status message indicating the result of the operation
    """
    pk = { "style_id": style_id }
    return update_attribute(
        wrapper=wrapper,
        cls=ComicStyle,
        primary_key=pk,
        attribute="description",
        value=value
    )

@function_tool
def update_art_style(
        wrapper: RunContextWrapper[APPState],
        style_id: str,
        art_style: ArtStyle
) -> str:
    """
    Update the art style of the currently selected comic style.
    
    Args:
        style_id: The ID of the comic style to update.
        art_style: The new art style for the comic style.
    
    Returns:
        A status message indicating the result of the operation.
    """
    pk = { "style_id": style_id}
    return update_attribute(
        wrapper=wrapper,
        cls=ComicStyle,
        primary_key=pk,
        attribute="art_style",
        value = art_style
        )

@function_tool
def update_dialog_style(
        wrapper: RunContextWrapper[APPState],
        style_id: str,
        dialog_type: DialogType,
        dialog_style: BubbleStyle
) -> str:
    """
    Update the dialog style of the currently selected comic style.
    
    Args:
        style_id: The ID of the comic style to update.
        dialog_type: The type of dialog (e.g. chat, whisper, sound-effect, narration, shout, thought)
        dialog_style: The new dialog style for the comic style.
    
    Returns:
        A status message indicating the result of the operation.
    """
    # BubbleStyles is a pydantic model whose per-type fields use underscores
    # (e.g. "sound-effect" -> "sound_effect"), so we cannot treat it as a plain
    # dict.  Update the specific nested bubble style field directly.
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    style: ComicStyle = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if style is None:
        return f"ComicStyle with ID '{style_id}' not found."
    field = dialog_type.value.replace("-", "_")
    if not hasattr(style.bubble_styles, field):
        return f"Unknown dialog type '{dialog_type.value}'."
    setattr(style.bubble_styles, field, dialog_style)
    storage.update_object(data=style)
    state.is_dirty = True
    return f"Updated {dialog_type.value} bubble style for comic style '{style_id}'."

@function_tool
def update_character_style(
        wrapper: RunContextWrapper[APPState],
        style_id: str,
        character_style: CharacterStyle
) -> str:
    """
    Update the character style of the currently selected comic style.
    
    Args:
        style_id: The ID of the comic style to update.
        character_style: The new character style for the comic style.
    
    Returns:
        A status message indicating the result of the operation.
    """
    pk = { "style_id": style_id }
    return update_attribute(
        wrapper=wrapper,
        cls=ComicStyle,
        primary_key=pk,
        attribute="character_style",
        value=character_style
)


# -------------------------------------------------------------------------
# NAME UPDATES
# Renaming updates the human-readable display name only; the object's id
# (and therefore its storage setting) is intentionally left unchanged.
# -------------------------------------------------------------------------
@function_tool
def update_series_name(wrapper: RunContextWrapper[APPState], series_id: str, name: str) -> str:
    """
    Update the display name (title) of a comic series.

    Args:
        series_id (str): The ID of the comic series.
        name (str): The new name for the series.

    Returns:
        A status message indicating the result of the update.
    """
    return update_attribute(wrapper=wrapper, cls=Series, primary_key={"series_id": series_id}, attribute="name", value=name)


@function_tool
def update_issue_name(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, name: str) -> str:
    """
    Update the display name (title) of a comic book issue.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the comic book issue.
        name (str): The new name for the issue.

    Returns:
        A status message indicating the result of the update.
    """
    return update_attribute(wrapper=wrapper, cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id}, attribute="name", value=name)


@function_tool
def update_character_name(wrapper: RunContextWrapper[APPState], series_id: str, character_id: str, name: str) -> str:
    """
    Update the display name of a character.

    Args:
        series_id (str): The ID of the comic series the character belongs to.
        character_id (str): The ID of the character.
        name (str): The new name for the character.

    Returns:
        A status message indicating the result of the update.
    """
    return update_attribute(wrapper=wrapper, cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id}, attribute="name", value=name)


@function_tool
def update_style_name(wrapper: RunContextWrapper[APPState], style_id: str, name: str) -> str:
    """
    Update the display name of a comic style.

    Args:
        style_id (str): The ID of the comic style.
        name (str): The new name for the style.

    Returns:
        A status message indicating the result of the update.
    """
    return update_attribute(wrapper=wrapper, cls=ComicStyle, primary_key={"style_id": style_id}, attribute="name", value=name)


# -------------------------------------------------------------------------
# SCENE UPDATES
# -------------------------------------------------------------------------
@function_tool
def update_scene_name(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, name: str) -> str:
    """
    Update the title/name of a scene.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue the scene belongs to.
        scene_id (str): The ID of the scene.
        name (str): The new name for the scene.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    return update_attribute(wrapper=wrapper, cls=SceneModel, primary_key=pk, attribute="name", value=name)


@function_tool
def update_scene_story(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, story: str) -> str:
    """
    Update the story/narrative arc of a scene.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue the scene belongs to.
        scene_id (str): The ID of the scene.
        story (str): The new story for the scene.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    return update_attribute(wrapper=wrapper, cls=SceneModel, primary_key=pk, attribute="story", value=story)


# -------------------------------------------------------------------------
# PANEL UPDATES
# -------------------------------------------------------------------------
@function_tool
def update_panel_name(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, panel_id: str, name: str) -> str:
    """
    Update the short name of a panel.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue.
        scene_id (str): The ID of the scene the panel belongs to.
        panel_id (str): The ID of the panel.
        name (str): The new name for the panel.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id}
    return update_attribute(wrapper=wrapper, cls=Panel, primary_key=pk, attribute="name", value=name)


@function_tool
def update_panel_beat(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, panel_id: str, beat: str) -> str:
    """
    Update the narrative beat of a panel (what changes or happens in this moment).

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue.
        scene_id (str): The ID of the scene the panel belongs to.
        panel_id (str): The ID of the panel.
        beat (str): The new narrative beat for the panel.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id}
    return update_attribute(wrapper=wrapper, cls=Panel, primary_key=pk, attribute="beat", value=beat)


@function_tool
def update_panel_description(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, panel_id: str, description: str) -> str:
    """
    Update the detailed visual description of a panel.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue.
        scene_id (str): The ID of the scene the panel belongs to.
        panel_id (str): The ID of the panel.
        description (str): The new visual description for the panel.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id}
    return update_attribute(wrapper=wrapper, cls=Panel, primary_key=pk, attribute="description", value=description)


# -------------------------------------------------------------------------
# REORDERING
# Moving an item renumbers the whole sibling list so the *_number fields stay
# contiguous and 1-based, matching how the create_* tools maintain order.
# -------------------------------------------------------------------------
def _reorder(items: list, number_attr: str, item_id_attr: str, item_id: str, new_position: int):
    """
    Move the item identified by item_id to new_position (1-based) within items
    (which must already be ordered by number_attr) and return the reordered list.
    Returns None if the item is not found.
    """
    idx = next((i for i, it in enumerate(items) if getattr(it, item_id_attr) == item_id), None)
    if idx is None:
        return None
    # Clamp the target to a valid 1-based position.
    target = max(1, min(new_position, len(items))) - 1
    moved = items.pop(idx)
    items.insert(target, moved)
    return items


@function_tool
def move_scene(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, new_position: int) -> str:
    """
    Reorder a scene within its issue by moving it to a new position.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue the scene belongs to.
        scene_id (str): The ID of the scene to move.
        new_position (int): The 1-based position the scene should occupy (1 = first).

    Returns:
        A status message indicating the result of the reorder.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = {"series_id": series_id, "issue_id": issue_id}
    scenes: list = storage.read_all_objects(cls=SceneModel, primary_key=pk, order_by="scene_number")
    ordered = _reorder(scenes, "scene_number", "scene_id", scene_id, new_position)
    if ordered is None:
        return f"Scene '{scene_id}' not found in issue '{issue_id}'."
    for i, s in enumerate(ordered):
        if s.scene_number != i + 1:
            s.scene_number = i + 1
            storage.update_object(s)
    state.is_dirty = True
    return f"Moved scene '{scene_id}' to position {max(1, min(new_position, len(ordered)))}."


@function_tool
def move_panel(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, scene_id: str, panel_id: str, new_position: int) -> str:
    """
    Reorder a panel within its scene by moving it to a new position.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue.
        scene_id (str): The ID of the scene the panel belongs to.
        panel_id (str): The ID of the panel to move.
        new_position (int): The 1-based position the panel should occupy (1 = first).

    Returns:
        A status message indicating the result of the reorder.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    panels: list = storage.read_all_objects(cls=Panel, primary_key=pk, order_by="panel_number")
    ordered = _reorder(panels, "panel_number", "panel_id", panel_id, new_position)
    if ordered is None:
        return f"Panel '{panel_id}' not found in scene '{scene_id}'."
    for i, p in enumerate(ordered):
        if p.panel_number != i + 1:
            p.panel_number = i + 1
            storage.update_object(p)
    state.is_dirty = True
    return f"Moved panel '{panel_id}' to position {max(1, min(new_position, len(ordered)))}."

# -------------------------------------------------------------------------
# SCENE PRODUCTION DETAILS (setting, cast, blocking)
# -------------------------------------------------------------------------
@function_tool
def update_scene_setting(wrapper: RunContextWrapper[APPState],
        series_id: str, issue_id: str, scene_id: str,
        setting_id: Optional[str] = None,
        time_of_day: Optional[str] = None,
        mood: Optional[str] = None) -> str:
    """
    Update the setting of a scene: where it takes place, at what time of day,
    and with what mood/lighting.   Only the provided fields are changed.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue the scene belongs to.
        scene_id (str): The ID of the scene.
        setting_id (str, optional): The setting (set) where the scene takes place.
            Must be an existing setting in the series.
        time_of_day (str, optional): e.g. 'day', 'night', 'dusk'.
        mood (str, optional): The emotional tone and lighting mood.

    Returns:
        A status message indicating the result of the update.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    scene: SceneModel = storage.read_object(cls=SceneModel, primary_key=pk)
    if scene is None:
        return f"Scene with ID '{scene_id}' not found."
    if setting_id is not None:
        from schema import Setting
        if storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": setting_id}) is None:
            return f"Setting '{setting_id}' not found in series '{series_id}'.  Create it first."
        scene.setting_id = setting_id
    if time_of_day is not None:
        scene.time_of_day = time_of_day
    if mood is not None:
        scene.mood = mood
    storage.update_object(data=scene)
    state.is_dirty = True
    return f"Updated setting for scene '{scene.name}'."


@function_tool
def update_scene_cast(wrapper: RunContextWrapper[APPState],
        series_id: str, issue_id: str, scene_id: str,
        cast: list[CharacterRef]) -> str:
    """
    Set the cast of a scene: which characters appear and which variant (wardrobe)
    each one wears.   Replaces the scene's existing cast list.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue the scene belongs to.
        scene_id (str): The ID of the scene.
        cast (list[CharacterRef]): The characters in the scene with their wardrobe variants.

    Returns:
        A status message indicating the result of the update.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    scene: SceneModel = storage.read_object(cls=SceneModel, primary_key=pk)
    if scene is None:
        return f"Scene with ID '{scene_id}' not found."
    scene.cast = cast
    storage.update_object(data=scene)
    state.is_dirty = True
    return f"Cast of scene '{scene.name}' set to: " + ", ".join(c.name for c in cast)


@function_tool
def update_scene_blocking(wrapper: RunContextWrapper[APPState],
        series_id: str, issue_id: str, scene_id: str,
        blocking: str) -> str:
    """
    Update the blocking notes of a scene: how the characters are staged and move
    through the setting over the course of the scene.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue the scene belongs to.
        scene_id (str): The ID of the scene.
        blocking (str): The blocking notes.

    Returns:
        A status message indicating the result of the update.
    """
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    return update_attribute(wrapper=wrapper, cls=SceneModel, primary_key=pk, attribute="blocking", value=blocking)


@function_tool
def update_scene_props(wrapper: RunContextWrapper[APPState],
        series_id: str, issue_id: str, scene_id: str,
        props: list[Prop]) -> str:
    """
    Set the scene-specific props (beyond the setting's standing props).
    Replaces the scene's existing prop list.

    Args:
        series_id (str): The ID of the comic series.
        issue_id (str): The ID of the issue the scene belongs to.
        scene_id (str): The ID of the scene.
        props (list[Prop]): The scene-specific props.

    Returns:
        A status message indicating the result of the update.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}
    scene: SceneModel = storage.read_object(cls=SceneModel, primary_key=pk)
    if scene is None:
        return f"Scene with ID '{scene_id}' not found."
    scene.props = props
    storage.update_object(data=scene)
    state.is_dirty = True
    return f"Props of scene '{scene.name}' set to: " + ", ".join(p.name for p in props)


# -------------------------------------------------------------------------
# LOCATION (SET) UPDATES
# -------------------------------------------------------------------------
@function_tool
def update_setting_description(wrapper: RunContextWrapper[APPState],
        series_id: str, setting_id: str, description: str) -> str:
    """
    Update the visual description of a setting (set).

    Args:
        series_id (str): The ID of the series the setting belongs to.
        setting_id (str): The ID of the setting.
        description (str): The new visual description.

    Returns:
        A status message indicating the result of the update.
    """
    from schema import Setting
    pk = {"series_id": series_id, "setting_id": setting_id}
    return update_attribute(wrapper=wrapper, cls=Setting, primary_key=pk, attribute="description", value=description)


@function_tool
def update_setting_props(wrapper: RunContextWrapper[APPState],
        series_id: str, setting_id: str, props: list[Prop]) -> str:
    """
    Set the props that dress a setting (set).  Replaces the existing prop list.
    NOTE: after changing the props, existing master backgrounds for the
    setting are stale and should be re-rendered.

    Args:
        series_id (str): The ID of the series the setting belongs to.
        setting_id (str): The ID of the setting.
        props (list[Prop]): The props that dress the setting.

    Returns:
        A status message indicating the result of the update.
    """
    from schema import Setting
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = {"series_id": series_id, "setting_id": setting_id}
    setting: Setting = storage.read_object(cls=Setting, primary_key=pk)
    if setting is None:
        return f"Setting '{setting_id}' not found in series '{series_id}'."
    setting.props = props
    storage.update_object(data=setting)
    state.is_dirty = True
    stale = ", ".join(setting.images.keys()) if setting.images else None
    note = f"  Plates for style(s) {stale} are now stale and should be re-rendered." if stale else ""
    return f"Props of setting '{setting.name}' set to: " + ", ".join(p.name for p in props) + note


@function_tool
def update_cover_setting(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, cover_id: str, setting_id: Optional[str]) -> str:
    """
    Set the setting for a cover.   The setting's master background (in the cover's
    style) is used as a reference when the cover is rendered, so the cover scene
    matches the interior pages.   Pass null to clear the setting.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the comic book issue.
        cover_id: The ID of the cover to update.
        setting_id: The ID of the setting, or null to clear it.  Must be an existing
            setting in the series (check with read_all_settings).

    Returns:
        A message indicating the result of the update operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    if setting_id is not None:
        if storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": setting_id}) is None:
            return f"Setting '{setting_id}' not found in series '{series_id}'.  Create it first."
    primary_key = {'cover_id': cover_id, 'series_id': series_id, 'issue_id': issue_id}
    return update_attribute(wrapper, Cover, primary_key, 'setting_id', setting_id)
