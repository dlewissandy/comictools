import os
from typing import Optional
from loguru import logger
from agents import function_tool, RunContextWrapper
from pydantic import BaseModel

from gui.state import APPState
from schema.character import CharacterModel
from schema.character_variant import CharacterVariant
from schema.style.dialog import DialogType
from schema.styled_variant import StyledVariant
from storage.generic import GenericStorage
from schema import (
    Cover,
    Publisher,
    CharacterModel,
    ComicStyle,
    Issue,
    FrameLayout,
    SceneModel,
    Series,
    CharacterRef,
    ExampleKind,
    StyleExample
)
from .formatting import format_comic_style, format_character_variant, format_issue, format_bubble_style

from helpers.generator import invoke_edit_image_api, invoke_generate_image_api, IMAGE_QUALITY
from schema.enums import frame_layout_to_dims, FrameLayout


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

    logger.debug("Uploading generated image to storage.")
    locator = storage.upload_binary_image(
        obj=obj,
        data=b64_image,
    )
    logger.debug(f"Image uploaded successfully with locator: {locator}")

    state.is_dirty = True
    return locator
    

@function_tool
def generate_publisher_logo_reference_image(
    wrapper: RunContextWrapper[APPState],
    publisher_id: str
) -> str:
    """
    Generate a reference image of the logo for the given publisher.

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
def delete_publisher_logo_reference_image(
    wrapper: RunContextWrapper[APPState],
    publisher_id: str
) -> str:
    """
    Delete the currently assigned logo reference image for a publisher.

    Args:
        publisher_id: The ID of the publisher whose logo reference image to delete.

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
def generate_cover_image(wrapper: RunContextWrapper, series_id: str, issue_id: str, cover_id: str) -> str:
    """
    Generate a cover image for the specified comic book issue.

    Args:
        series_id (str): The ID of the comic book series.
        issue_id (str): The ID of the comic book issue.
        cover_id (str): The unique identifier for the cover to render.

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

    cover = storage.read_object(cls=Cover, primary_key={"series_id": series_id, "issue_id": issue_id, "cover_id": cover_id})
    if not cover:
        logger.error(f"Cover with ID {cover_id} for issue {issue_id} in series {series_id} not found.")
        return f"Cover with ID {cover_id} for issue {issue_id} in series {series_id} not found."
    cover: Cover = cover

    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": cover.style_id})
    if not style:
        logger.error(f"Style {cover.style_id} not found")
        return f"Style {cover.style_id} not found"

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

    location_name = cover.location.value.title()
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

    primary_key = {"series_id": series_id, "issue_id": issue_id, "cover_id": cover_id}

    cover = storage.read_object(cls=Cover, primary_key=primary_key)
    if not cover:
        return "Cannot delete cover image.   The specified cover does not exist."
    cover: Cover = cover

    if not cover.image:
        return "No cover image to delete."

    locator: str = cover.image
    storage.delete_image(locator)
    
    cover.image = None
    storage.update_object(data=cover)
    state.is_dirty = True
    return f"{cover_id} image deleted successfully."


@function_tool
def create_character_style_example_image(
    wrapper: RunContextWrapper[APPState],
    style_id: str
) -> str:
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if not style:
        return f"Style with ID {style_id} not found."
    style: ComicStyle = style

    try:
        with open(os.path.join("data", "prompts", "imaging", "character-style-example.md"), "r") as f:
            template = f.read()
    except FileNotFoundError:
        return "Prompt file not found."

    if not template:
        return "Prompt file is empty."

    style_description = format_comic_style(style, heading_level=2)
    prompt = template.format(
        style_name=style.name,
        style_description=style_description
    )

    style_example = StyleExample(
        style_id=style_id,
        example_type=ExampleKind.CHARACTER.value.lower(),
        image_id=f"{style_id}-character-style-example",
        mime_type="image/jpg"
    )

    locator = generate_object_image(
        wrapper=wrapper,
        obj=style_example,
        prompt=prompt,
        aspect_ratio=FrameLayout.LANDSCAPE,
        image_quality=IMAGE_QUALITY.HIGH,
        name=style_example.image_id
    )

    # Update the variant with the new image locator
    style.image["character"] = locator
    storage.update_object(data=style)

    state.is_dirty = True

    return f"Example created successfully with locator: {locator}"    

    


@function_tool
def create_styled_image_for_character_variant(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    character_id: str,
    variant_id: str,
    style_id: str,
) -> str:
    """
    Create a styled image for a character variant.   This image can be used as a reference image to help artists
    faithfully represent the character in the comic book.

    Args:
        series_id: The ID of the comic book series.
        character_id: The ID of the character.
        variant_id: The ID of the character variant.
        style_id: The ID of the comic style to use for the image.

    Returns:
        A locator for the generated image.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    # Read the series
    series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
    if not series:
        return f"Series with ID {series_id} not found."
    
    # Read the character and variant from storage
    character = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id})
    if not character:
        return f"Character with ID {character_id} not found in series {series_id}."
    character: CharacterModel = character

    variant = storage.read_object(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id, "variant_id": variant_id})
    if not variant:
        return f"Variant with ID {variant_id} for character {character.name} not found in series {series_id}."
    variant: CharacterVariant = variant

    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if not style:
        return f"Style with ID {style_id} not found."
    style: ComicStyle = style
    
    character_name = character.name
    # format the character variant for use
    character_description = format_character_variant(character_name, variant, heading_level=2)

    style_description = format_comic_style(style, heading_level=2)

    # Generate the styled image
    try:
        with open(os.path.join("data","prompts","imaging","styled-variant.md"), "r") as f:
            template = f.read()
    except FileNotFoundError:
        return "Prompt file not found."
    if not template:
        return "Prompt file is empty."

    prompt = template.format(
        character_name=character_name,
        character_description=character_description,
        style_description=style_description
    )
    
    styled_variant = StyledVariant(
        style_id=style_id,
        variant_id=variant_id,
        series_id=series_id,
        character_id=character_id,
        image_id="{character.name}-{variant.name}-{style.name}-styled-image"
    )

    locator = generate_object_image(
        wrapper=wrapper,
        obj=styled_variant,
        prompt=prompt,
        aspect_ratio=FrameLayout.LANDSCAPE,
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{character.name}-{variant.name}-{style.name}-styled-image"
    )

    # Update the variant with the new image locator
    variant.images[style.style_id] = locator
    storage.update_object(data=variant)

    return f"Styled image created successfully with locator: {locator}"

@function_tool
def create_art_style_example_image(
    wrapper: RunContextWrapper[APPState],
    style_id: str
) -> str:
    """
    Create an example of an art style as an image.
    
    Returns:
        A message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if not style:
        return f"Cannot create art style image.   Style with ID {style_id} not found."
    style: ComicStyle = style

    REFERENCE_IMAGE = "data/references/art-style.jpg"
    
    # Serialize the descripiton of the style
    style_info = format_comic_style(
        include_bubble_styles=False,
        include_character_style=False,
        style=style,
        heading_level=2

    )

    # Render the image using the OpenAI images API and the art style description
    logger.debug(f"Rendering art style image with style: {style.name}")
    with open(os.path.join("data", "prompts", "imaging", "art-style-example.md"), "r") as f:
        template = f.read()
    prompt = template.format(
        style_name=style.name,
        style_info=style_info
    )
    style_example = StyleExample(
        style_id=style_id,
        example_type=ExampleKind.ART.value.lower(),
        image_id=f"{style_id}-art-style-example",
        mime_type="image/jpg"
    )

    locator = generate_object_image(
        wrapper=wrapper,
        obj=style_example,
        prompt=prompt,
        aspect_ratio=FrameLayout.LANDSCAPE,
        image_quality=IMAGE_QUALITY.HIGH,
        name=style_example.image_id,
        reference_images=[REFERENCE_IMAGE]
    )

    # Update the variant with the new image locator
    style.image["art"] = locator
    storage.update_object(data=style)

    state.is_dirty = True

    return f"Example of art style created successfully with locator: {locator}"    


@function_tool
def create_dialog_style_example_image(
    wrapper: RunContextWrapper[APPState],
    style_id: str,
    dialog_type: DialogType
) -> str:
    """
    Generate an example image of a dialog style (chat, whisper, shout, thought, sound-effect, narration)

    Args:
        style_id: The ID of the comic style.
        dialog_type: The type of dialog (chat, whisper, shout, thought, sound-effect, narration).

    Returns:
        A message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    pk = { "style_id": style_id }
    style = storage.read_object(cls=ComicStyle, primary_key=pk)
    if not style:
        return f"Cannot generate example image.  Style with ID {style_id} not found."
    style: ComicStyle = style

    # Create the prompt
    with open(os.path.join("data", "prompts", "imaging", "dialog-style-example.md"), "r") as f:
        template = f.read()
    logger.debug

    style_description = format_comic_style(
        style=style,
        include_bubble_styles=False,
        include_character_style=False,
        heading_level=2
    )
    logger.debug(f"Style description: {style_description}")
    bubble_type = dialog_type.value
    bubble_text = {
        "chat": "Nice day, isn't it?",
        "narration": "Once upon a time...",
        "whisper": "Shhh.  It's a secret.",
        "thought": "I wonder what will happen...",
        "shout": "Watch out!",
        "sound-effect": "Boom!"
    }.get(bubble_type, "Unknown dialog type")
    logger.debug(f"Bubble type: {bubble_type}, Bubble text: {bubble_text}")

    # get the property from bubble_styles by accessing the attribute by name
    if not hasattr(style.bubble_styles, bubble_type.replace("-", "_")):
        return f"Cannot generate example image.  Style {style_id} does not have a bubble style for {bubble_type}."
    bubble_style = getattr(style.bubble_styles, bubble_type.replace("-", "_"))
    logger.debug(f"Bubble style: {bubble_style}")

    bubble_style_description  = format_bubble_style(
        style = bubble_style,
        heading_level=2
    )
    logger.debug(f"Bubble style description: {bubble_style_description}")
    prompt = template.format(
        style_description=style_description,
        dialog_style_description=bubble_style_description,
        dialog_type=bubble_type,
        dialog_text=bubble_text
    )
    logger.debug(f"Generating the dialog example image with prompt: {prompt}")

    style_example = StyleExample(
        style_id=style_id,
        example_type=bubble_type.lower(),
        image_id=f"{style_id}-{bubble_type}-style-example",
        mime_type="image/jpg"
    )
    logger.debug(f"Generated style example: {style_example}")

    locator = generate_object_image(
        wrapper=wrapper,
        obj=style_example,
        prompt=prompt,
        aspect_ratio=FrameLayout.SQUARE,
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{style_id}-{bubble_type}-dialog-example"
    )
    logger.debug(f"Generated dialog style example image with locator: {locator}")

    # Update the style with the new image locator
    if not style.image:
        style.image = {}
    style.image[dialog_type.value] = locator
    logger.debug(f"Updated style with new image locator: {style.image}")
    storage.update_object(data=style)
    logger.debug("Style updated in storage.")

    state.is_dirty = True   

    return f"Example image for {bubble_type} dialog generated and saved to {locator}"


@function_tool
def delete_art_style_example(wrapper: RunContextWrapper[APPState], 
    style_id: str) -> str:
    """
    Delete the example of the art style for the given comic style.
    THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
    THIS FUNCTION.
    
    Args: 
        style_id: The ID of the art style to delete.

    Returns:
        A status message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = { "style_id": style_id  }
    style = storage.read_object(ComicStyle, primary_key = pk)
    # if there is no style selected, return an error message
    if not style:
        return "The specified style does not exist"
    # if the images are not a dictionary, return an error message
    style: ComicStyle = style
    if not isinstance(style.image, dict):
        return "No art style example image to delete."
    # if there is no art style example image selected, return an error message.
    locator = style.image.get("art",None)
    if not locator:
        return "No art style example image to delete."
    # otherwise, delete the art style example image.
    style.image["art"] = None
    storage.delete_image(locator)
    storage.update_object(style)
    state.is_dirty = True
    return f"Art style example for {style.name} deleted."

@function_tool
def delete_character_style_example(
        wrapper: RunContextWrapper[APPState],
        style_id: str
) -> str:
    """
    Delete the example of the character style for the specified comic style.
    THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
    THIS FUNCTION.

    Args:
        style_id: The ID of the character style example image to delete.

    Returns:
        A status message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    pk = { "style_id": style_id  }
    style = storage.read_object(ComicStyle, primary_key = pk)
    # if there is no style selected, return an error message
    if not style:
        return "The specified style does not exist"
    # if the images are not a dictionary, return an error message
    style: ComicStyle = style
    if not isinstance(style.image, dict):
        return "No character style example image to delete."
    # if there is no art style example image selected, return an error message.
    locator = style.image.get("character",None)
    if not locator:
        return "No character style example image to delete."
    style.image["character"] = None
    storage.delete_image(locator)
    storage.update_object(style)
    state.is_dirty = True
    return f"Character style example for {style.name} deleted."


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
    
