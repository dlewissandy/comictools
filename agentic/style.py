
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

@function_tool
def delete_dialog_style_example(
    wrapper: RunContextWrapper[APPState],
    style_id: str,
    dialog_type: DialogType) -> str:
    """
    Delete the example for one of the dialog styles (chat, whisper, shout, 
    thought, sound-effect, narration) for the specified comic style.
    THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
    THIS FUNCTION.

    Args:
        style_id: The ID of the comic style to delete the dialog style example for.
        dialog_type: The type of dialog style to delete (chat, whisper, shout, thought, sound-effect, narration).

    Returns:
        A status message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = { "style_id": style_id  }
    style = storage.read_object(ComicStyle, primary_key = pk)
    # if there is no style selected, return an error message
    if not style:
        return "Cannot find comic style {style_id}."
    style: ComicStyle = style
    # if the images are not a dictionary, return an error message
    if not isinstance(style.image, dict):
        return "No dialog style example image to delete."
    # if there is no art style example image selected, return an error message.
    locator = style.image.get(f"{dialog_type.value}",None)
    if not locator:
        return "No dialog style example image to delete."
    # otherwise, delete the character style example image.
    style.image[dialog_type.value] = None
    storage.delete_image(locator)
    storage.update_object(style)
    state.is_dirty = True
    return f"dialog style example for {style.name} deleted."
    

