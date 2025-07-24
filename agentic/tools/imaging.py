from typing import Optional
from loguru import logger
from agents import function_tool, RunContextWrapper
from pydantic import BaseModel

from gui.state import APPState
from schema.character import CharacterModel
from schema.character_variant import CharacterVariant
from storage.generic import GenericStorage
from schema import (
    Cover,
    Publisher,
    CoverLocation,
    CharacterModel,
    ComicStyle,
    Issue,
    FrameLayout,
    SceneModel,
    Series,
    CharacterRef,
)
from .formatting import format_comic_style, format_character_variant, format_issue

from helpers.generator import invoke_edit_image_api, invoke_generate_image_api, IMAGE_QUALITY
from schema.enums import CoverLocation, frame_layout_to_dims, FrameLayout


def generate_object_image(
    wrapper: RunContextWrapper[GenericStorage],
    obj: BaseModel,
    prompt: str,
    reference_images: Optional[list[str]] = [],
    aspect_ratio: str = FrameLayout.SQUARE,
    image_quality: IMAGE_QUALITY = IMAGE_QUALITY.HIGH,
    image_mask: Optional[str] = None,
    name: str = "generated_image"
    ) -> str:
    """
    Generate an image for the given object using the provided prompt.
    Args:
        wrapper: The RunContextWrapper containing the storage context.
        obj: The object for which to generate the image.
        prompt: The prompt to use for image generation.
        reference_images: Optional list of reference images to use.
        aspect_ratio: The aspect ratio for the generated image.
        image_quality: The quality of the generated image.
        image_mask: Optional mask to apply to the image.

    Returns:
        A locator for the generated image.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    dims = frame_layout_to_dims(aspect_ratio)

    if reference_images is None or len(reference_images) == 0:
        logger.debug("No reference images provided for image generation.")
        b64_image = invoke_generate_image_api(
            prompt,
            size=dims,
            quality=image_quality
        )
    else:
        logger.debug("Reference images provided for image generation.")
        b64_image = invoke_edit_image_api(
            prompt,
            reference_images=reference_images,
            mask=image_mask,
            size=dims,
            quality=image_quality
        )

    locator = storage.upload_binary_image(
        obj=obj,
        data=b64_image,
    )

    state.is_dirty = True
    return locator
    

@function_tool
def generate_publisher_logo_image(
    wrapper: RunContextWrapper[APPState],
    publisher_id: str
) -> str:
    """
    Generate an image of the logo for the given publisher.
    
    Args:
        wrapper: The RunContextWrapper containing the storage context.
        publisher_id: The ID of the publisher for which to generate the logo.

    Returns:
        A locator for the generated image.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    primary_key = {"publisher_id": publisher_id}
    publisher = storage.read_object(cls=Publisher, primary_key=primary_key)
    if not publisher:
        raise ValueError(f"Publisher with ID {publisher_id} not found.")

    publisher: Publisher = publisher
    
    if publisher.logo is None or publisher.logo == "":
        return "Cannot generate logo image.  There is no logo description for this publisher."

    prompt = f"""Generate a rendering of the logo for {publisher.name.replace("-"," ").title()} using the following information:\n

    {publisher.logo}

    # Guidelines
    * The image must have a square (1:1) aspect ratio.
    * The logo should be on a neutral background.
    * The logo should be easily recognizable, and not too complex.
    """
    
    locator = generate_object_image(
        wrapper=wrapper,
        obj=publisher,
        prompt=prompt,
        aspect_ratio=FrameLayout.SQUARE,
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{publisher.name.replace(' ', '-').lower()}-logo"
    )

    publisher.image = locator
    storage.update_object(data=publisher)
    return f"Image generated successfully with locator: {locator}"

@function_tool
def delete_publisher_logo_image(
    wrapper: RunContextWrapper[APPState],
    publisher_id: str
) -> str:
    """
    Delete the currently assigned logo image for a publisher.

    Args:
        publisher_id: The ID of the publisher whose logo image to delete.

    Returns:
        A message indicating the result of the deletion.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    primary_key = {"publisher_id": publisher_id}
    publisher = storage.read_object(cls=Publisher, primary_key=primary_key)
    if not publisher:
        return "Publisher not found."
    publisher: Publisher = publisher

    if not publisher.image:
        return "No logo image to delete."

    locator: str = publisher.image
    storage.delete_image(locator)
    
    publisher.image = None
    storage.update_object(data=publisher)
    state.is_dirty = True
    return f"Logo image for {publisher.name} deleted successfully."

@function_tool
def generate_cover_image(wrapper: RunContextWrapper, series_id: str, issue_id: str, location: CoverLocation) -> str:
    """
    Generate a cover image for the specified comic book issue.

    Args:
        series_id (str): The ID of the comic book series.
        issue_id (str): The ID of the comic book issue.
        location (CoverLocation): The location of the cover (e.g., front, back, inside-front, inside-back).

    Returns:
        A string indicating the status of the rendering operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    # TODO Change to have configurable elments for title, name, issue number, etc. 
    
    # Read the context (series, issue, style, characters) from the storage
    series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
    if not series:
        logger.error(f"Series with ID {series_id} not found.")
        return f"Series with ID {series_id} not found."
    series: Series = series

    publisher = storage.read_object(cls=Publisher, primary_key={"publisher_id": series.publisher_id}) if series.publisher_id else None
    if not publisher:
        logger.error(f"Publisher with ID {series.publisher_id} not found.")
        return f"Publisher with ID {series.publisher_id}"
    publisher: Publisher = publisher

    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    if not issue:
        logger.error(f"Issue with ID {issue_id} in series {series_id} not found.")
        return f"Issue with ID {issue_id} in series {series_id} not found."
    issue: Issue = issue

    cover = storage.read_object(cls=Cover, primary_key={"series_id": series_id, "issue_id": issue_id, "location": location})
    if not cover:
        logger.error(f"Cover with location {location} for issue {issue_id} in series {series_id} not found.")
        return f"Cover with location {location} for issue {issue_id} in series {series_id} not found."
    cover: Cover = cover

    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": cover.style_id})
    if not style:
        logger.error(f"Style {style_id} not found")
        return f"Style {style_id} not found"

    characters: dict[str,CharacterVariant] = {}
    for char_ref in cover.character_references:
        char_ref: CharacterRef = char_ref
        character = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": char_ref.character_id})
        if not character:
            logger.error(f"Character {char_ref.character_id} not found in series {series_id}.")
            return f"Character {char_ref.character_id} not found in series {series_id}."
        character: CharacterModel = character
        variant = storage.read_object(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": char_ref.character_id, "variant_id": char_ref.variant_id})
        if not variant:
            logger.error(f"Character variant {char_ref.variant_id} for character {char_ref.character_id} not found in series {series_id}.")
            return f"Character variant {char_ref.variant_id} for character {char_ref.character_id} not found in series {series_id}."
        characters[character.name] = variant

    reference_image_locators: list[str] = storage.list_uploads(obj=cover)
    logger.debug(f"Reference image locators: {reference_image_locators}")

    if not publisher.image is None:
        # Append the logo image if it exists.
        reference_image_locators.append(publisher.image) 
    for name, variant in characters.items():
        # Append the character's styled image if it exists.
        if variant.images.get(cover.style_id, None) is not None:
            reference_image_locators.append(variant.images[cover.style_id])

    location_name = location.value.title()
    logger.debug(f"location name: {location_name}")

    character_information = ""
    if len(characters) > 0:
        for name, variant in characters.items():
            character_information += format_character_variant(name, variant, 2) + "\n"
    # If we got here, then we have all the information that we need to render the cover.
    prompt = f"""
    Create a comic book {location_name} cover.   The image should be have a {cover.aspect.value} orientation/aspect ratio.


# Series
* ** Title **: "{series.name}".   This should appear prominently across the top of the cover.
* ** Subtitle **: "{issue.name}".  This should appear in smaller font below the title.
{'* ** Price **: ' + str(issue.price) +".   Place below subtitle on left." if issue.price else ""}
{'* ** Issue Number **: ' + str(issue.issue_number) + ".   Place below subtitle on right." if issue.issue_number else ""}
{'* ** Issue Date **: ' + issue.publication_date + ".   Place below issue number right in small font." if issue.publication_date else ""}
{'* ** Artist **: ' + issue.artist + ".   Place in small font at bottom of image" if issue.artist else ""}
{'* ** Writer **: ' + issue.writer + ".   Place in small font at bottom of image" if issue.writer else ""}
{'* ** Colorist **: ' + issue.colorist + ".   Place in small font at bottom of image" if issue.colorist else ""}
{'* ** Creative Minds **: ' + issue.creative_minds + ".   Place in small font at bottom of image" if issue.creative_minds else ""}


{format_issue(issue,heading_level=1)}

# Publisher
* ** Logo **: (PLACE IN SMALL SQUARE IN LOWER RIGHT CORNER) {publisher.logo} 

# Characters
{character_information}

# Style
{format_comic_style(style, heading_level=1)}

# Cover Design
{cover.description}
"""

    try:
        if len(reference_image_locators) > 0:
            # We have to use the edit image API
            logger.debug(f"invoking generator with prompt {prompt} and reference images {reference_image_locators}")
            raw_image = invoke_edit_image_api(
                prompt=prompt,
                size=frame_layout_to_dims(cover.aspect),
                reference_images=reference_image_locators,
            )
        else:
            logger.debug(f"invoking generator with prompt {prompt}")
            # We can use the generate image API
            raw_image = invoke_generate_image_api(
                prompt=prompt,
                size=frame_layout_to_dims(cover.aspect)
            )
    except Exception as e:
        msg = f"Error generating cover image: {e}"
        logger.error(msg)
        return msg
    
    logger.debug("Uploading image to storage.")
    # Write the image bytes to the image path
    locator = storage.upload_binary_image(
        obj=cover,
        data=raw_image,
    )
    logger.debug(f"Cover image uploaded successfully with locator: {locator}")
    cover.image = locator
    storage.update_object(data=cover)
    return f"Cover image successfully created for issue {issue.name} at location {location_name}."

@function_tool
def delete_cover_image(wrapper: RunContextWrapper, series_id: str, issue_id: str, cover_id: str) -> str:
    """
    Delete the selected cover image.

    Args:
        series_id: The comic series identifier of the cover to delete
        issue_id: The issue identifier of the cover to delete
        cover_id: The unique identifier for the cover whose image to delete

    Returns:
        A message indicating the status of the deletion
    """

    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    issue = storage.read_object(cls=Issue, primary_key={ "series_id": series_id, "issue_id": issue_id})
    if not issue:
        return "Cannot delete cover image.   The specified issue does not exist."
    issue: Issue = issue

    primary_key = {"series_id": series_id, "issue_id": issue_id, "location": cover_id}

    cover = storage.read_object(cls=Cover, primary_key=primary_key)
    if not cover:
        return "Cannot delete cover image.   The specified cover does not exist."
    cover: Cover = cover

    if not cover.image.get(cover_id, None):
        return "No cover image to delete."

    locator: str = cover.image.get(cover_id, None)
    storage.delete_image(locator)
    
    cover.image = None
    storage.update_object(data=cover)
    state.is_dirty = True
    return f"{cover_id} image for {cover.name} deleted successfully."
