from typing import Tuple, Optional, List
from loguru import logger
from agents import Agent, function_tool, Tool, RunContextWrapper
from gui.state import APPState
import os
from gui.selection import SelectionItem, SelectedKind
from storage.generic import GenericStorage
from schema import (
    ComicStyle,
    Publisher,
)
from helpers.generator import invoke_generate_image_api, IMAGE_QUALITY
from storage.filepath import generate_unique_id

def render(storage: GenericStorage,publisher: Publisher) -> Optional[str]:
    """
    render the logo for the publisher on success, returns the id of the generated image.
    """
    if publisher.logo is None or publisher.logo == "":
        return None

    prompt = f"""Generate a rendering of the logo for {publisher.id.replace("-"," ").title()} using the following information:\n

    {publisher.logo}

    # Guidelines
    * The image must have a square (1:1) aspect ratio.
    * The logo should be on a neutral background.
    * The logo should be easily recognizable, and not too complex.
    """

    prompt = f"""Generate a rendering of the logo for {publisher.id.replace("-"," ").title()} using the following information:\n

    {publisher.logo}

    # Guidelines
    * The image must have a square (1:1) aspect ratio.
    * The logo should be on a neutral background.
    * The logo should be easily recognizable, and not too complex.
    """
    id = publisher.id.replace(" ", "-").lower()
    raw_image = invoke_generate_image_api(prompt, n=1, size="1024x1024", quality=IMAGE_QUALITY.HIGH)
    image_id = generate_unique_id(savepath, create_folder=False)
    
    savefilepath = os.path.join(savepath,f"{image_id}.jpg")
    if publisher.image is None or publisher.image == "":
        publisher.image = image_id
        storage.update_object(data=publisher)
    with open(savefilepath, "wb") as f:
        f.write(raw_image.getbuffer())
    return image_id


@function_tool
def render_logo(wrapper: RunContextWrapper[APPState], publisher_id: str)  -> str:
    """
    Generate an image of the logo for the given publisher.
    
    Returns:
        A status message indicating the result of the rendering.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    publisher = storage.read_object(cls=Publisher, primary_key={"id": publisher_id})
    if publisher is None:
        msg = f"Publisher with ID '{publisher_id}' not found."
        logger.error(msg)
        return msg
    publisher: Publisher = publisher



    img = publisher.render()
    if img is None:
        msg = f"Logo for publisher '{publisher.name}' could not be rendered."
        logger.error(msg)
        return msg
    
    state["is_dirty"] = True        
    return f"The logo for publisher '{publisher.name}' has been rendered and is saved to {img}.jpg"

@function_tool
def delete_logo_image(wrapper: RunContextWrapper[APPState], publisher_id: str) -> str:
    """
    Delete the logo image for the current publisher.  NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    publisher = storage.read_object(cls=Publisher, primary_key={"id": publisher_id})
    if publisher is None:
        return "Something odd happened.  No publisher is currently selected."
    publisher: Publisher = publisher
    # if the images are not a dictionary, return an error message
    if publisher.image is None:
        return "No logo image to delete."
    # otherwise, delete the image.
    image_filepath = publisher.image
    publisher.image = None
    if not os.path.exists(image_filepath):
        return "The file does not exist.  Nothing to delete."
    os.remove(image_filepath)
    storage.update_object(data=publisher)
    state.is_dirty = True
    return f"logo image for {publisher.name} deleted."

