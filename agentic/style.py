
import os

from typing import Tuple
from agentic.constants import LANGUAGE_MODEL
from agents import Agent, RunContextWrapper, function_tool, Tool
from agentic.tools import read_context, delete_style
from gui.state import APPState
from schema import ComicStyle, ArtStyle, DialogType, BubbleStyle, BubbleStyles, CharacterStyle
from loguru import logger
from storage.generic import GenericStorage
from agentic.instructions import instructions
from gui.selection import SelectedKind


def get_comic_style(state: APPState) -> ComicStyle:
    """
    Get the currently selected comic style.
    
    Returns:
        The ComicStyle object if found, otherwise None.
    """
    selection = state.selection
    storage: GenericStorage = state.storage
    if selection and selection[-1].kind == SelectedKind.STYLE:
        return storage.read_object(cls=ComicStyle, primary_key={"style_id": selection[-1].id})
    return None

@function_tool
def get_description(wrapper: RunContextWrapper[APPState]) -> str:
    """
    Get the description of the currently selected comic style.
    
    Returns:
        The description of the comic style if found, otherwise a message indicating no selection.
    """
    state = wrapper.context
    style = get_comic_style(state)
    if style:
        return style.description
    return "No comic style currently selected."

@function_tool(name_override="update_description")
def update_style_description(wrapper: RunContextWrapper[APPState], new_description: str) -> str:
    """
    Update the description of the currently selected comic style.
    
    Args:
        value (string): The new description for the comic style.
    
    Returns:
        A status message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    style = get_comic_style()
    if style:
        style.description = new_description
        storage.update_object(style)
        state.is_dirty = True
        return f"Description for {style.name} updated."
    return "No comic style selected."

@function_tool
def read_art_style(wrapper: RunContextWrapper[APPState]) -> ArtStyle | None:
    """
    Read the art style of the currently selected comic style.  The art style
    defines the visual aspects of the comic book, such as line style, inking tools,
    shading style, color palette, and more.  It is used by artists to ensure that
    the visual language of the comic is consistent throughout the series.
    
    Returns:
        The ArtStyle object if found, otherwise None.
    """
    state: APPState = wrapper.context
    style = get_comic_style(state)
    if style:
        return style.art_style
    return None

@function_tool
def update_art_style(
        wrapper: RunContextWrapper[APPState],
        line_styles: str | None = None,
        inking_tools: str | None = None,
        shading_style: str | None = None,
        color_palette: str | None = None,
        spot_colors: str | None = None,
        registration: str | None = None,
        lettering_style: str | None = None,
) -> str:
    """
    Update the art style of the currently selected comic style.
    
    Args:
        line_styles: The line styles used in the comic book.
        inking_tools: The inking tools used in the comic book.
        shading_style: The shading style used in the comic book.
        color_palette: The color palette used in the comic book.
        spot_colors: The spot colors used in the comic book.
        registration: The registration method used in the comic book.
        lettering_style: The lettering style used in the comic book.
    
    Returns:
        A status message indicating the result of the operation.
    """
    state = wrapper.context
    storage: GenericStorage = state.storage
    style = get_comic_style(state)
    if style is None:
        return "No comic style selected."
    art_style = style.art_style
    
    if line_styles is not None:
        art_style.line_styles = line_styles
    if inking_tools is not None:
        art_style.inking_tools = inking_tools
    if shading_style is not None:
        art_style.shading_style = shading_style
    if color_palette is not None:
        art_style.color_palette = color_palette
    if spot_colors is not None:
        art_style.spot_colors = spot_colors
    if registration is not None:
        art_style.registration = registration
    if lettering_style is not None:
        art_style.lettering_style = lettering_style
    if any([line_styles, inking_tools, shading_style, color_palette, spot_colors, registration, lettering_style]):
        storage.update_object(style)
        state.is_dirty = True
        return f"Art style for {style.name} updated."
    return "No comic style selected."


@function_tool
def read_character_style(wrapper: RunContextWrapper[APPState]) -> CharacterStyle | None:
    """
    Read the character style of the currently selected comic style.  The character style
    defines the visual aspects of characters in the comic book, such as head to body ratio,
    limb proportions, eye style, and more.  It is used by artests to ensure that all the
    characters in a comic book have the same look and feel, and that they are consistent
    throughout the series.
    
    Returns:
        The CharacterStyle object if found, otherwise None.
    """
    state: APPState = wrapper.context
    style = get_comic_style(state)
    if style:
        return style.character_style
    return None

@function_tool
def read_dialog_style(wrapper: RunContextWrapper[APPState], dialog_type: DialogType) -> BubbleStyles | None:
    """
    Read one of the dialog styles (chat, whisper, shout, thought, sound-effect
    , narration) of the currently selected comic style.  The dialog style
    defines the visual language used for dialog  in the comic book, such as font, fill color,
    and more.  It is used by artists to ensure that the text bubbles in a comic book have
    a consistent look and feel throughout the series.
    
    Args:
        dialog_type: The type of dialog style to read.
    
    Returns:
        The BubbleStyles object if found, otherwise None.
    """
    state: APPState = wrapper.context
    style = get_comic_style(state)
    if style:
        dialog_style = getattr(style.bubble_styles, dialog_type.value.replace("-", "_"), None)
        return dialog_style
    return None

@function_tool(name_override="create_art_style_example_image")
def render_art_style_example(wrapper: RunContextWrapper[APPState]) -> Tuple[str, str]:
    """
    Create a new example image of the art style for the currently selected comic style.
    
    Returns:
        A tuple containing the image filepath and a description of the art style.
    """
    state: APPState = wrapper.context
    style = get_comic_style(state)
    if style:
        return style.render_art_style()
    return None, "No comic style selected."

@function_tool
def delete_art_style_example(wrapper: RunContextWrapper[APPState]) -> str:
    """
    Delete the example of the art style for the currently selected comic style.
    THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
    THIS FUNCTION.
    
    Returns:
        A status message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    style = get_comic_style()
    # if there is no style selected, return an error message
    if not style:
        return "No comic style selected."
    # if the images are not a dictionary, return an error message
    style: ComicStyle = style
    if not isinstance(style.image, dict):
        return "No art style example image to delete."
    # if there is no art style example image selected, return an error message.
    image = style.image.get("art",None)
    if not image:
        return "No art style example image to delete."
    # otherwise, delete the art style example image.
    style.image["art"] = None
    # TODO: This is the wrong filepath.   Use tools!
    image_filepath = os.path.join(style.image_path(img_type="art"), f"{image}.jpg")
    if not os.path.exists(image_filepath):
        return "The file does not exist.  Nothing to delete."
    os.remove(image_filepath)
    storage.update_object(style)
    state.is_dirty = True
    return f"Art style example for {style.name} deleted."


@function_tool
def delete_character_style_example(
        wrapper: RunContextWrapper[APPState],
) -> str:
    """
    Delete the example of the character style for the currently selected comic style.
    THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
    THIS FUNCTION.
    
    Returns:
        A status message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    style = get_comic_style()
    # if there is no style selected, return an error message
    if not style:
        return "No comic style selected."
    
    style: ComicStyle = style
    # if the images are not a dictionary, return an error message
    if not isinstance(style.image, dict):
        return "No character style example image to delete."
    # if there is no art style example image selected, return an error message.
    image = style.image.get("character",None)
    if not image:
        return "No character style example image to delete."
    # otherwise, delete the character style example image.
    # TODO: This is the wrong filepath.   Use tools!
    style.image["character"] = None
    image_filepath = os.path.join(style.image_path(img_type="character"), f"{image}.jpg")
    if not os.path.exists(image_filepath):
        return "The file does not exist.  Nothing to delete."
    os.remove(image_filepath)
    storage.update_object(style)
    state.is_dirty = True
    return f"Character style example for {style.name} deleted."

@function_tool
def delete_dialog_style_example(
    wrapper: RunContextWrapper[APPState],
    dialog_type: DialogType) -> str:
    """
    Delete the example for one of the dialog styles (chat, whisper, shout, 
    thought, sound-effect, narration) for the currently selected comic style.
    THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
    THIS FUNCTION.
    
    Returns:
        A status message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    style = get_comic_style()
    # if there is no style selected, return an error message
    if not style:
        return "No comic style selected."
    style: ComicStyle = style
    # if the images are not a dictionary, return an error message
    if not isinstance(style.image, dict):
        return "No dialog style example image to delete."
    # if there is no art style example image selected, return an error message.
    image = style.image.get(f"{dialog_type.value}",None)
    if not image:
        return "No chat style example image to delete."
    # otherwise, delete the character style example image.
    style.image[dialog_type.value] = None
    # TODO: This is the wrong filepath.   Use tools!
    image_filepath = os.path.join(style.image_path(img_type=dialog_type.value), f"{image}.jpg")
    if not os.path.exists(image_filepath):
        return "The file does not exist.  Nothing to delete."
    os.remove(image_filepath)
    storage.update_object(style)
    state.is_dirty = True
    return f"Character style example for {style.name} deleted."
    
@function_tool
def create_character_style_example(
        wrapper: RunContextWrapper[APPState],
) -> str:
    """
    Render an example of the character style for the currently selected comic style.
    if this runs successfully, it will create a new image and select it as the current
    example image for the character style
    
    Returns:
        A string indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    style = get_comic_style()

    if style:
        style: ComicStyle = style
        # TODO: REFACTOR SO RENDERING IS A TOOL
        result = style.render_character_style_example()
        state.is_dirty = True
        return result
    return "No style is selected, or the style does not exist."

def render_dialog_example(
    wrapper: RunContextWrapper[APPState],
    bubble_type: str
) -> str:
    """
    Render an example of a dialog bubble as an image.
    
    Returns:
        A message indicating the result of the operation.
    """
    state = wrapper.context
    style = get_comic_style()
    if style:
        style: ComicStyle = style
        # TODO: REFACTOR SO RENDERING IS A TOOL
        img_id = style.render_dialog_example(bubble_type=bubble_type)
        state.is_dirty = True
        return f"Dialog bubble example rendered and saved to {img_id}.jpg"
    return "No comic style selected."

@function_tool
def render_chat_dialog_example(
    wrapper: RunContextWrapper[APPState]
) -> str:
    """Render an example image of the chat dialog style for the currently selected comic style.
    
    Returns:
        A message indicating the result of the operation.
    """
    return render_dialog_example(wrapper=wrapper, bubble_type="chat")

@function_tool
def render_whisper_dialog_example(
    wrapper: RunContextWrapper[APPState]
) -> str:
    """Render an example image of the whisper dialog style for the currently selected comic style.

    Returns:
        A message indicating the result of the operation.
    """
    return render_dialog_example(wrapper=wrapper, bubble_type="whisper")

@function_tool
def render_shout_dialog_example(
    wrapper: RunContextWrapper[APPState]
) -> str:
    """Render an example image of the shout dialog style for the currently selected comic style.
    
    Returns:
        A message indicating the result of the operation.
    """
    return render_dialog_example(wrapper=wrapper, bubble_type="shout")

@function_tool
def render_thought_dialog_example(
    wrapper: RunContextWrapper[APPState]
) -> str:
    """Render an example image of the thought dialog style for the currently selected comic style.

    Returns:
        A message indicating the result of the operation.
    """
    return render_dialog_example(wrapper=wrapper, bubble_type="thought")

@function_tool
def render_sound_effect_dialog_example(
    wrapper: RunContextWrapper[APPState]
) -> str:
    """Render an example image of the sound effect dialog style for the currently selected comic style.

    Returns:
        A message indicating the result of the operation.
    """
    return render_dialog_example(wrapper=wrapper, bubble_type="sound-effect")

@function_tool
def render_narration_dialog_example(
    wrapper: RunContextWrapper[APPState]
) -> str:
    """Render an example image of the narration dialog style for the currently selected comic style.
    Returns:
        A message indicating the result of the operation.
    """
    return render_dialog_example(wrapper=wrapper, bubble_type="narration")

@function_tool
def update_dialog_style(
    wrapper: RunContextWrapper[APPState],
    dialog_type: DialogType,
    dialog_style: BubbleStyle
) -> str:
    """
    Update the dialog style for one of the dialog types (chat, whisper, shout, thought, sound-effect
    , narration).
    
    Args:
        dialog_type: The type of dialog style to update.
        bubble_style: The value of the new dialog style.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    style = get_comic_style()
    if style is None:
        logger.error("No comic style selected.")
        return "No comic style selected."
    style: ComicStyle = style
    dialog_type = dialog_type.value.replace("-", "_")
    old_style = getattr(style.bubble_styles, dialog_type, None)
    if old_style is None:
        logger.debug(f"Unrecognized dialog type: {dialog_type}.")
        return f"Unrecognized dialog type: {dialog_type}."
    
    bubble_styles = style.bubble_styles
    setattr(bubble_styles, dialog_type, dialog_style)
    logger.debug(f"Updated dialog style for {dialog_type}: {dialog_style}")
    storage.update_object(style)
    state.is_dirty = True
    return f"Dialog style for {style.name} updated."


style_agent: Agent = Agent(
        name="style",
        instructions=instructions,
        model=LANGUAGE_MODEL,
        tools=[
            # UPDATERS
            update_style_description,
            update_art_style,
            update_dialog_style,
            
            # READ
            get_description,
            read_art_style,
            read_character_style,
            read_dialog_style,
            # RENDER
            render_chat_dialog_example,
            render_whisper_dialog_example,
            render_shout_dialog_example,
            render_thought_dialog_example,
            render_sound_effect_dialog_example,
            render_narration_dialog_example,
            render_art_style_example,
            create_character_style_example,
            # DELETE
            delete_style,
            delete_art_style_example,
            delete_character_style_example,
            delete_dialog_style_example


        ],
    )

