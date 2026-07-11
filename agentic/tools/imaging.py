import os
import json
import tempfile
from typing import Optional
from uuid import uuid4
from io import BytesIO
from loguru import logger
from agents import function_tool, RunContextWrapper
from pydantic import BaseModel
from PIL import Image, ImageDraw

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
    Panel,
    SceneModel,
    Series,
    CharacterRef,
    ExampleKind,
    StyleExample
)
from .formatting import format_comic_style, format_character_variant, format_issue, format_bubble_style

from helpers.generator import invoke_edit_image_api, invoke_generate_image_api, IMAGE_QUALITY
from schema.enums import frame_layout_to_dims, FrameLayout
from gui.selection import SelectedKind, SelectionItem


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
def generate_cover_image(wrapper: RunContextWrapper, series_id: str, issue_id: str, cover_id: str, text_layout_instructions: Optional[str] = None) -> str:
    """
    Generate a cover image for the specified comic book issue.

    Args:
        series_id (str): The ID of the comic book series.
        issue_id (str): The ID of the comic book issue.
        cover_id (str): The unique identifier for the cover to render.
        text_layout_instructions (str, optional): Custom instructions for how the text
            elements (title, subtitle, price, issue number, date, credits) should be
            placed and styled on the cover.   If omitted, a standard comic layout is
            used (title across the top, subtitle below, credits at the bottom).

    Returns:
        A string indicating the status of the rendering operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

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

    # Gather reference images the same way panels do: the setting's master
    # background comes FIRST, then character reference sheets, then uploads.
    missing: list[str] = []
    reference_image_locators: list[str] = []
    setting_information = ""
    background_first = False

    if cover.setting_id:
        setting: Setting = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": cover.setting_id})
        if setting is None:
            missing.append(f"setting '{cover.setting_id}' (create_setting)")
        else:
            background = setting.images.get(cover.style_id)
            if background and os.path.exists(background):
                reference_image_locators.append(background)
                background_first = True
            else:
                missing.append(f"master background for '{setting.name}' in style '{cover.style_id}' (generate_setting_background)")
            setting_information = f"# Setting\n{'Interior' if setting.interior else 'Exterior'}: {setting.name}\n{setting.description}\n"

    for name, variant in characters.items():
        # Append the character's styled image if it exists.
        if variant.images.get(cover.style_id, None) is not None:
            reference_image_locators.append(variant.images[cover.style_id])
        else:
            missing.append(f"styled image of '{name}' ({variant.variant_id}) in style '{cover.style_id}' (create_styled_image_for_character_variant)")

    reference_image_locators.extend(storage.list_uploads(obj=cover))
    if not publisher.image is None:
        # Append the logo image if it exists.
        reference_image_locators.append(publisher.image)
    logger.debug(f"Reference image locators: {reference_image_locators}")

    location_name = cover.location.value.title()
    logger.debug(f"cover position: {location_name}")

    character_information = ""
    if len(characters) > 0:
        for name, variant in characters.items():
            character_information += format_character_variant(name, variant, 2) + "\n"
    # Text elements use a standard comic layout unless the caller supplies custom
    # placement/styling instructions.
    if text_layout_instructions:
        text_elements = f"""* ** Title **: "{series.name}"
* ** Subtitle **: "{issue.name}"
{'* ** Price **: ' + str(issue.price) if issue.price else ""}
{'* ** Issue Number **: ' + str(issue.issue_number) if issue.issue_number else ""}
{'* ** Issue Date **: ' + issue.publication_date if issue.publication_date else ""}
{'* ** Artist **: ' + issue.artist if issue.artist else ""}
{'* ** Writer **: ' + issue.writer if issue.writer else ""}
{'* ** Colorist **: ' + issue.colorist if issue.colorist else ""}
{'* ** Creative Minds **: ' + issue.creative_minds if issue.creative_minds else ""}

## Text Layout Instructions
{text_layout_instructions}"""
    else:
        text_elements = f"""* ** Title **: "{series.name}".   This should appear prominently across the top of the cover.
* ** Subtitle **: "{issue.name}".  This should appear in smaller font below the title.
{'* ** Price **: ' + str(issue.price) +".   Place below subtitle on left." if issue.price else ""}
{'* ** Issue Number **: ' + str(issue.issue_number) + ".   Place below subtitle on right." if issue.issue_number else ""}
{'* ** Issue Date **: ' + issue.publication_date + ".   Place below issue number right in small font." if issue.publication_date else ""}
{'* ** Artist **: ' + issue.artist + ".   Place in small font at bottom of image" if issue.artist else ""}
{'* ** Writer **: ' + issue.writer + ".   Place in small font at bottom of image" if issue.writer else ""}
{'* ** Colorist **: ' + issue.colorist + ".   Place in small font at bottom of image" if issue.colorist else ""}
{'* ** Creative Minds **: ' + issue.creative_minds + ".   Place in small font at bottom of image" if issue.creative_minds else ""}"""

    # If we got here, then we have all the information that we need to render the cover.
    background_guidance = ""
    if background_first:
        background_guidance = ("The FIRST reference image is the setting's master background: "
                               "use it as the cover's setting — same architecture, same props, same palette — "
                               "reframed as the cover composition requires.\n")

    prompt = f"""
    Create a comic book {location_name} cover.   The image should be have a {cover.aspect.value} orientation/aspect ratio.
{background_guidance}

# Series
{text_elements}


{format_issue(issue,heading_level=1)}

{setting_information}
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
    note = ""
    if missing:
        note = "  NOTE: rendered without: " + "; ".join(missing) + ".  Generate those references and re-render for better consistency."
    return f"{location_name} cover image successfully created for issue {issue.name}.{note}"

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
    if not isinstance(style.image, dict):
        style.image = {}
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
    
    # A variant is a composition: base character + outfit + props.  Their
    # reference art anchors the render, same as panels composite the setting.
    from schema import Outfit, PropAsset
    reference_images: list[str] = []
    missing: list[str] = []
    if variant.outfit_id:
        outfit = storage.read_object(Outfit, {"series_id": series_id, "outfit_id": variant.outfit_id})
        if outfit is None:
            missing.append(f"outfit '{variant.outfit_id}' (asset not found)")
        else:
            art = outfit.images.get(style_id)
            if art and os.path.exists(art):
                reference_images.append(art)
            else:
                missing.append(f"reference art for outfit '{outfit.name}' in style '{style_id}' (generate_outfit_reference)")
            prompt += f"\n\n## Outfit: {outfit.name}\n{outfit.description}"
    for pid in (variant.prop_ids or []):
        prop = storage.read_object(PropAsset, {"series_id": series_id, "prop_id": pid})
        if prop is None:
            missing.append(f"prop '{pid}' (asset not found)")
            continue
        art = prop.images.get(style_id)
        if art and os.path.exists(art):
            reference_images.append(art)
        else:
            missing.append(f"reference art for prop '{prop.name}' in style '{style_id}' (generate_prop_reference)")
        prompt += f"\n\n## Carried prop: {prop.name}\n{prop.description}"

    styled_variant = StyledVariant(
        style_id=style_id,
        variant_id=variant_id,
        series_id=series_id,
        character_id=character_id,
        image_id=f"{character.name}-{variant.name}-{style.name}-styled-image"
    )

    locator = generate_object_image(
        wrapper=wrapper,
        obj=styled_variant,
        prompt=prompt,
        reference_images=reference_images,
        aspect_ratio=FrameLayout.LANDSCAPE,
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{character.name}-{variant.name}-{style.name}-styled-image"
    )

    # Update the variant with the new image locator
    variant.images[style.style_id] = locator
    storage.update_object(data=variant)

    note = ""
    if missing:
        note = "  NOTE: rendered without: " + "; ".join(missing) + ".  Generate those references and re-render for better consistency."
    return f"Styled image created successfully with locator: {locator}.{note}"

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


def _find_selection_id(selection: list, kind: SelectedKind) -> str | None:
    for item in reversed(selection):
        if item.kind == kind:
            return item.id
    return None


def _choose_output_size(width: int, height: int) -> str:
    if height == 0:
        return "1024x1024"
    ratio = width / height
    if ratio >= 1.15:
        return "1536x1024"
    if ratio <= 0.87:
        return "1024x1536"
    return "1024x1024"


def _save_image_bytes(image_bytes: bytes, source_path: str, prefix: str = "edit") -> str:
    output_dir = os.path.dirname(source_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    ext = os.path.splitext(source_path)[1].lower().lstrip(".") or "png"
    if ext not in ["png", "jpg", "jpeg", "webp"]:
        ext = "png"
    filename = f"{prefix}-{uuid4().hex[:8]}.{ext}"
    output_path = os.path.join(output_dir, filename)
    try:
        img = Image.open(BytesIO(image_bytes))
        save_format = "JPEG" if ext in ["jpg", "jpeg"] else ext.upper()
        img.save(output_path, format=save_format)
    except Exception:
        with open(output_path, "wb") as f:
            f.write(image_bytes)
    return output_path


def _ensure_session_id(state: APPState) -> str:
    if not state.image_editor_session_id:
        state.image_editor_session_id = uuid4().hex[:8]
    return state.image_editor_session_id


def _choices_manifest_path(image_locator: str, session_id: str) -> str:
    folder = os.path.dirname(image_locator)
    return os.path.join(folder, f".choices-{session_id}.json")


def _write_choices_manifest(image_locator: str, session_id: str, choices: list[str]) -> None:
    path = _choices_manifest_path(image_locator, session_id)
    payload = {
        "image": image_locator,
        "choices": choices,
        "session_id": session_id,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def _is_intent_only(text: str, mode: str) -> bool:
    lowered = " ".join(text.lower().strip().split())
    if mode == "inpaint":
        return lowered in {
            "i would like to inpaint a region of this image.",
            "i would like to inpaint a region of this image",
            "inpaint",
            "inpaint a region",
            "inpaint a region of this image",
        }
    if mode == "outpaint":
        return lowered in {
            "i would like to outpaint a region of this image.",
            "i would like to outpaint a region of this image",
            "outpaint",
            "outpaint a region",
            "outpaint a region of this image",
        }
    return False


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("'s", "")
    return lowered


def _text_has_any(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def _collect_reference_images(state: APPState, instruction: str, max_refs: int = 3) -> list[str]:
    selection = state.selection
    series_id = _find_selection_id(selection, SelectedKind.SERIES)
    issue_id = _find_selection_id(selection, SelectedKind.ISSUE)
    scene_id = _find_selection_id(selection, SelectedKind.SCENE)
    panel_id = _find_selection_id(selection, SelectedKind.PANEL)
    cover_id = _find_selection_id(selection, SelectedKind.COVER)

    storage: GenericStorage = state.storage
    text = _normalize_text(instruction or "")

    candidates: list[tuple[str, int]] = []

    def add_candidate(path: str | None, score: int):
        if not path:
            return
        if not os.path.exists(path):
            return
        candidates.append((path, score))

    relation_keywords = {
        "background": ["background", "sky", "setting"],
        "left": ["left"],
        "right": ["right"],
        "above": ["above", "top"],
        "below": ["below", "bottom", "under"],
        "before": ["before"],
        "after": ["after"],
    }

    def relation_score(relation_value: str) -> int:
        keywords = relation_keywords.get(relation_value, [])
        return 3 if _text_has_any(text, keywords) else 1

    if panel_id and scene_id and issue_id and series_id:
        panel = storage.read_object(Panel, primary_key={
            "series_id": series_id,
            "issue_id": issue_id,
            "scene_id": scene_id,
            "panel_id": panel_id,
        })
        if panel:
            for ref in panel.reference_images:
                add_candidate(ref.image, relation_score(ref.relation.value))

            for char_ref in panel.character_references:
                char_model = storage.read_object(CharacterModel, primary_key={
                    "series_id": char_ref.series_id,
                    "character_id": char_ref.character_id,
                })
                name = char_model.name.lower() if char_model else char_ref.character_id.replace("-", " ")
                if _text_has_any(text, [name, char_ref.character_id.replace("-", " ")]):
                    if hasattr(storage, "find_variant_image"):
                        img = storage.find_variant_image(
                            series_id=char_ref.series_id,
                            character_id=char_ref.character_id,
                            variant_id=char_ref.variant_id,
                        )
                        add_candidate(img, 4)

    if cover_id and issue_id and series_id:
        cover = storage.read_object(Cover, primary_key={
            "series_id": series_id,
            "issue_id": issue_id,
            "cover_id": cover_id,
        })
        if cover:
            for ref in cover.reference_images:
                add_candidate(ref.image, relation_score(ref.relation.value))

            for char_ref in cover.character_references:
                char_model = storage.read_object(CharacterModel, primary_key={
                    "series_id": char_ref.series_id,
                    "character_id": char_ref.character_id,
                })
                name = char_model.name.lower() if char_model else char_ref.character_id.replace("-", " ")
                if _text_has_any(text, [name, char_ref.character_id.replace("-", " ")]):
                    if hasattr(storage, "find_variant_image"):
                        img = storage.find_variant_image(
                            series_id=char_ref.series_id,
                            character_id=char_ref.character_id,
                            variant_id=char_ref.variant_id,
                        )
                        add_candidate(img, 4)

    if _text_has_any(text, ["logo", "publisher"]):
        if series_id:
            series = storage.read_object(Series, primary_key={"series_id": series_id})
            if series and series.publisher_id:
                publisher = storage.read_object(Publisher, primary_key={"publisher_id": series.publisher_id})
                if publisher and publisher.image:
                    add_candidate(publisher.image, 4)

    candidates.sort(key=lambda item: item[1], reverse=True)
    selected: list[str] = []
    seen = set()
    for path, _score in candidates:
        if path in seen:
            continue
        seen.add(path)
        selected.append(path)
        if len(selected) >= max_refs:
            break
    return selected


def _merge_reference_images(base: str, refs: list[str]) -> list[str]:
    images = [base]
    for ref in refs:
        if ref and ref != base:
            images.append(ref)
    return images


def _normalize_selection(selection: dict, width: int, height: int) -> dict:
    x = int(selection.get("x", 0))
    y = int(selection.get("y", 0))
    w = int(selection.get("width", 0))
    h = int(selection.get("height", 0))
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = max(1, min(w, width - x))
    h = max(1, min(h, height - y))
    return {"x": x, "y": y, "width": w, "height": h}


def _create_full_mask(image_path: str) -> tuple[str, tuple[int, int]]:
    img = Image.open(image_path).convert("RGBA")
    mask = Image.new("RGBA", img.size, (0, 0, 0, 0))
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    mask.save(tmp.name)
    return tmp.name, img.size


def _create_inpaint_mask(image_path: str, selection: dict) -> tuple[str, tuple[int, int]]:
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    selection = _normalize_selection(selection, width, height)
    mask = Image.new("RGBA", img.size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(mask)
    x = selection["x"]
    y = selection["y"]
    w = selection["width"]
    h = selection["height"]
    draw.rectangle([x, y, x + w, y + h], fill=(0, 0, 0, 0))
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    mask.save(tmp.name)
    return tmp.name, img.size


def _prepare_outpaint_assets(image_path: str, padding: dict) -> tuple[str, str, tuple[int, int]]:
    img = Image.open(image_path).convert("RGBA")
    top = max(0, int(padding.get("top", 0)))
    bottom = max(0, int(padding.get("bottom", 0)))
    left = max(0, int(padding.get("left", 0)))
    right = max(0, int(padding.get("right", 0)))
    new_width = img.width + left + right
    new_height = img.height + top + bottom
    base = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    base.paste(img, (left, top))
    mask = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(mask)
    draw.rectangle([left, top, left + img.width, top + img.height], fill=(255, 255, 255, 255))
    base_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    mask_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    base.save(base_tmp.name)
    mask.save(mask_tmp.name)
    return base_tmp.name, mask_tmp.name, (new_width, new_height)


def _update_parent_selection(
    state: APPState,
    storage: GenericStorage,
    original_locator: str,
    new_locator: str,
) -> str | None:
    selection = state.selection
    series_id = _find_selection_id(selection, SelectedKind.SERIES)
    issue_id = _find_selection_id(selection, SelectedKind.ISSUE)
    scene_id = _find_selection_id(selection, SelectedKind.SCENE)
    panel_id = _find_selection_id(selection, SelectedKind.PANEL)
    cover_id = _find_selection_id(selection, SelectedKind.COVER)
    publisher_id = _find_selection_id(selection, SelectedKind.PUBLISHER)
    style_id = _find_selection_id(selection, SelectedKind.STYLE)
    character_id = _find_selection_id(selection, SelectedKind.CHARACTER)
    variant_id = _find_selection_id(selection, SelectedKind.VARIANT)
    styled_variant_style_id = _find_selection_id(selection, SelectedKind.STYLED_VARIANT)
    reference_image_id = _find_selection_id(selection, SelectedKind.REFERENCE_IMAGE)

    if panel_id and scene_id and issue_id and series_id:
        panel = storage.read_object(Panel, primary_key={
            "series_id": series_id,
            "issue_id": issue_id,
            "scene_id": scene_id,
            "panel_id": panel_id,
        })
        if panel:
            panel.image = new_locator
            storage.update_object(panel)
            state.is_dirty = True
            return "panel"

    if cover_id and issue_id and series_id:
        cover = storage.read_object(Cover, primary_key={
            "series_id": series_id,
            "issue_id": issue_id,
            "cover_id": cover_id,
        })
        if cover:
            cover.image = new_locator
            storage.update_object(cover)
            state.is_dirty = True
            return "cover"

    if publisher_id:
        publisher = storage.read_object(Publisher, primary_key={"publisher_id": publisher_id})
        if publisher:
            publisher.image = new_locator
            storage.update_object(publisher)
            state.is_dirty = True
            return "publisher"

    if styled_variant_style_id and variant_id and character_id and series_id:
        variant = storage.read_object(CharacterVariant, primary_key={
            "series_id": series_id,
            "character_id": character_id,
            "variant_id": variant_id,
        })
        if variant:
            variant.images[styled_variant_style_id] = new_locator
            storage.update_object(variant)
            state.is_dirty = True
            return "styled-variant"

    if style_id:
        style = storage.read_object(ComicStyle, primary_key={"style_id": style_id})
        if style:
            if not isinstance(style.image, dict):
                style.image = {}
            key = None
            for k, v in style.image.items():
                if v == original_locator:
                    key = k
                    break
            if key is None:
                key = next(iter(style.image.keys()), "art")
            style.image[key] = new_locator
            storage.update_object(style)
            state.is_dirty = True
            return "style"

    if reference_image_id:
        if panel_id and scene_id and issue_id and series_id:
            panel = storage.read_object(Panel, primary_key={
                "series_id": series_id,
                "issue_id": issue_id,
                "scene_id": scene_id,
                "panel_id": panel_id,
            })
            if panel:
                ref = next((r for r in panel.reference_images if r.id == reference_image_id or r.image == original_locator), None)
                if ref:
                    ref.image = new_locator
                    storage.update_object(panel)
                    state.is_dirty = True
                    return "panel-reference"
        if cover_id and issue_id and series_id:
            cover = storage.read_object(Cover, primary_key={
                "series_id": series_id,
                "issue_id": issue_id,
                "cover_id": cover_id,
            })
            if cover:
                ref = next((r for r in cover.reference_images if r.id == reference_image_id or r.image == original_locator), None)
                if ref:
                    ref.image = new_locator
                    storage.update_object(cover)
                    state.is_dirty = True
                    return "cover-reference"

    return None


@function_tool
def inpaint_image_region(wrapper: RunContextWrapper[APPState], instruction: str) -> str:
    """
    Inpaint a selected region of the current image editor image using the given instruction.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    selection = state.image_editor_selection
    image_locator = state.image_editor_image

    if not instruction or instruction.strip() == "":
        return "No instruction provided. Describe the change in chat and try again."
    if _is_intent_only(instruction, "inpaint"):
        return "Tell me what you want to change in the image."

    if image_locator is None:
        if state.selection and state.selection[-1].id:
            image_locator = state.selection[-1].id
        else:
            return "No image is selected for editing."

    if not os.path.exists(image_locator):
        return f"Image not found: {image_locator}"

    mask_path = None
    try:
        session_id = _ensure_session_id(state)
        if selection:
            mask_path, (w, h) = _create_inpaint_mask(image_locator, selection)
        else:
            mask_path, (w, h) = _create_full_mask(image_locator)
        size = _choose_output_size(w, h)
        refs = _collect_reference_images(state, instruction)
        images = invoke_edit_image_api(
            prompt=instruction,
            reference_images=_merge_reference_images(image_locator, refs),
            mask=mask_path,
            size=size,
            quality=IMAGE_QUALITY.HIGH,
            n=4,
        )
        if isinstance(images, bytes):
            images = [images]
        choices = [_save_image_bytes(img, image_locator, prefix=f"choice-{session_id}") for img in images]
    finally:
        if mask_path and os.path.exists(mask_path):
            os.remove(mask_path)

    if not choices:
        return "No images were generated. Try again."

    _write_choices_manifest(image_locator, session_id, choices)
    state.image_editor_choices = choices
    state.image_editor_choice_selected = choices[0] if choices else None
    state.image_editor_original_image = image_locator
    state.image_editor_image = image_locator
    state.image_editor_mode = "inpaint"

    new_sel = [s for s in state.selection]
    new_sel.append(SelectionItem(name="Choices", id=f"{session_id}|{image_locator}", kind=SelectedKind.IMAGE_EDITOR_CHOICES))
    state.change_selection(new=new_sel)
    return "Generated 4 options. Pick one to apply, or cancel."


@function_tool
def outpaint_image_region(wrapper: RunContextWrapper[APPState], instruction: str) -> str:
    """
    Outpaint the current image editor image using the given instruction.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    image_locator = state.image_editor_image

    if not instruction or instruction.strip() == "":
        return "No instruction provided. Describe the change in chat and try again."
    if _is_intent_only(instruction, "outpaint"):
        return "Tell me what you want to extend or add beyond the image."

    if image_locator is None:
        if state.selection and state.selection[-1].id:
            image_locator = state.selection[-1].id
        else:
            return "No image is selected for editing."

    if not os.path.exists(image_locator):
        return f"Image not found: {image_locator}"

    padding = {"top": 256, "bottom": 256, "left": 256, "right": 256}
    base_path = None
    mask_path = None
    try:
        session_id = _ensure_session_id(state)
        base_path, mask_path, (w, h) = _prepare_outpaint_assets(image_locator, padding)
        size = _choose_output_size(w, h)
        refs = _collect_reference_images(state, instruction)
        images = invoke_edit_image_api(
            prompt=instruction,
            reference_images=_merge_reference_images(base_path, refs),
            mask=mask_path,
            size=size,
            quality=IMAGE_QUALITY.HIGH,
            n=4,
        )
        if isinstance(images, bytes):
            images = [images]
        choices = [_save_image_bytes(img, image_locator, prefix=f"choice-{session_id}") for img in images]
    finally:
        for path in [base_path, mask_path]:
            if path and os.path.exists(path):
                os.remove(path)

    if not choices:
        return "No images were generated. Try again."

    _write_choices_manifest(image_locator, session_id, choices)
    state.image_editor_choices = choices
    state.image_editor_choice_selected = choices[0] if choices else None
    state.image_editor_original_image = image_locator
    state.image_editor_image = image_locator
    state.image_editor_mode = "outpaint"

    new_sel = [s for s in state.selection]
    new_sel.append(SelectionItem(name="Choices", id=f"{session_id}|{image_locator}", kind=SelectedKind.IMAGE_EDITOR_CHOICES))
    state.change_selection(new=new_sel)
    return "Generated 4 options. Pick one to apply, or cancel."
    


# -------------------------------------------------------------------------
# MASTER BACKGROUNDS AND PANEL RENDERING
#
# A setting's master background is inked once per style (the empty setting,
# dressed with its props).  Panels are then composed ON TOP of that background
# with the cast's styled reference sheets, so the setting stays visually
# consistent across every panel that takes place there.
# -------------------------------------------------------------------------
from schema import Setting, SceneModel

@function_tool
def generate_setting_background(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    setting_id: str,
    style_id: str,
) -> str:
    """
    Render the master background for a setting in a given comic style: the empty
    setting, dressed with its props, with NO characters.   The master background is
    stored on the setting keyed by style and is reused as the shared background for
    every panel that takes place there — ink the setting once, reuse it across pages.

    If reference images have been uploaded for the setting, they are used to
    steer the rendering for real-world or previously-established looks.

    Args:
        series_id: The ID of the series the setting belongs to.
        setting_id: The ID of the setting to render.
        style_id: The comic style to render the master background in.

    Returns:
        A status message with the locator of the rendered master background.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    setting: Setting = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": setting_id})
    if setting is None:
        return f"Setting '{setting_id}' not found in series '{series_id}'."
    style: ComicStyle = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if style is None:
        return f"Style '{style_id}' not found."

    prop_lines = "\n".join(f"* **{p.name}**: {p.description}" for p in setting.props)
    interior_or_exterior = "an interior" if setting.interior else "an exterior"

    prompt = f"""Render a comic book master background of {interior_or_exterior} setting: "{setting.name}".

This is an EMPTY SETTING: render the setting fully dressed with its props but with
absolutely NO characters, people, or creatures in it.   Compose it as a wide
establishing view with generous negative space where characters can later be
placed.   The rendering must strictly follow the comic style below so that
panels composed on top of this background match the rest of the issue.

# Setting
{setting.description}

# Props
{prop_lines if prop_lines else "* (no props)"}

{format_comic_style(style, include_bubble_styles=False, include_character_style=False, heading_level=1)}
"""

    # Uploaded reference images (e.g. multi-angle sketches or photos) steer the render.
    reference_images = storage.list_uploads(obj=setting)

    locator = generate_object_image(
        wrapper=wrapper,
        obj=setting,
        prompt=prompt,
        reference_images=reference_images,
        aspect_ratio=FrameLayout.LANDSCAPE,
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{setting_id}-{style_id}-background",
    )

    setting.images[style_id] = locator
    storage.update_object(data=setting)
    state.is_dirty = True
    return f"Master background for '{setting.name}' rendered in style '{style_id}': {locator}"


@function_tool
def generate_panel_image(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    issue_id: str,
    scene_id: str,
    panel_id: str,
) -> str:
    """
    Render the artwork for a panel by compositing its reference objects: the
    scene's master background is reused as the panel's setting, the cast's styled
    reference sheets keep the characters on-model, and the panel's own uploaded
    reference images (if any) steer the composition.   Dialogue balloons and
    narration boxes are lettered per the style's bubble styles.

    Prerequisites for best consistency (the tool degrades gracefully without them):
    * the scene has a setting whose master background has been rendered in the
      scene's style (generate_setting_background),
    * each character in the panel has a styled image for the scene's style
      (create_styled_image_for_character_variant).

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.
        scene_id: The ID of the scene the panel belongs to.
        panel_id: The ID of the panel to render.

    Returns:
        A status message with the locator of the rendered panel image.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    panel: Panel = storage.read_object(cls=Panel, primary_key={
        "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id})
    if panel is None:
        return f"Panel '{panel_id}' not found in scene '{scene_id}'."
    scene: SceneModel = storage.read_object(cls=SceneModel, primary_key={
        "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
    if scene is None:
        return f"Scene '{scene_id}' not found in issue '{issue_id}'."
    style: ComicStyle = storage.read_object(cls=ComicStyle, primary_key={"style_id": scene.style_id})
    if style is None:
        return f"Style '{scene.style_id}' not found."

    reference_images: list[str] = []
    missing: list[str] = []

    # 1) The setting's master background is shared by every panel in the scene.
    setting: Setting | None = None
    if scene.setting_id:
        setting = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": scene.setting_id})
        if setting is not None:
            background = setting.images.get(scene.style_id)
            if background and os.path.exists(background):
                reference_images.append(background)
            else:
                missing.append(f"master background for '{setting.name}' in style '{scene.style_id}' (generate_setting_background)")

    # 2) The cast's styled reference sheets keep the characters on-model.
    cast_info = ""
    for ref in panel.character_references:
        variant: CharacterVariant = storage.read_object(cls=CharacterVariant, primary_key={
            "series_id": series_id, "character_id": ref.character_id, "variant_id": ref.variant_id})
        if variant is None:
            missing.append(f"variant '{ref.variant_id}' of character '{ref.character_id}'")
            continue
        styled = variant.images.get(scene.style_id)
        if styled and os.path.exists(styled):
            reference_images.append(styled)
        else:
            missing.append(f"styled image of '{ref.character_id}' ({ref.variant_id}) in style '{scene.style_id}' (create_styled_image_for_character_variant)")
        cast_info += format_character_variant(ref.character_id, variant, 2) + "\n"

    # 3) Panel-specific uploaded reference images.
    reference_images.extend(storage.list_uploads(obj=panel))

    # Assemble the dialogue/narration script for the letterer.
    script_lines = []
    for n in panel.narration:
        script_lines.append(f"* **Narration ({n.position.value})**: {n.text}")
    for d in panel.dialogue:
        script_lines.append(f"* **{d.character_id}** ({d.emphasis.value}): {d.text}")
    script = "\n".join(script_lines)

    setting_line = ""
    if setting is not None:
        setting_line = f"{'Interior' if setting.interior else 'Exterior'}: {setting.name}" + (f", {scene.time_of_day}" if scene.time_of_day else "")

    prompt = f"""Render a single comic book panel.  Aspect/orientation: {panel.aspect.value}.
{f"Setting: {setting_line}" if setting_line else ""}
{f"Mood: {scene.mood}" if scene.mood else ""}

The FIRST reference image (when present) is the setting's master background: use it
as the panel's setting — same architecture, same props, same palette — reframed as
the panel requires.   The character reference sheets show exactly how each character
must look; keep them strictly on-model.

# Beat
{panel.beat}

# Panel description
{panel.description}

{f"# Scene blocking{chr(10)}{scene.blocking}" if scene.blocking else ""}

# Characters in panel
{cast_info if cast_info else "* (no characters in panel)"}

# Lettering (render these balloons/boxes per the style's bubble styles)
{script if script else "* (silent panel — no lettering)"}

{format_comic_style(style, heading_level=1)}
"""

    locator = generate_object_image(
        wrapper=wrapper,
        obj=panel,
        prompt=prompt,
        reference_images=reference_images,
        aspect_ratio=panel.aspect,
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{panel_id}-render",
    )

    panel.image = locator
    storage.update_object(data=panel)
    state.is_dirty = True

    note = ""
    if missing:
        note = "  NOTE: rendered without: " + "; ".join(missing) + ".  Generate those references and re-render for better consistency."
    return f"Panel {panel.panel_number} rendered: {locator}.{note}"


@function_tool
def export_issue_pdf(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    Bind the issue into a PDF book: covers full-bleed, interior panels laid down
    each page in reading order.   Reports any unrendered panels or covers so they
    can be generated first — a complete issue is one where nothing is missing.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the issue to export.

    Returns:
        A status message with the PDF locator, the page count, and anything
        still missing from a complete issue.
    """
    from helpers.binder import bind_issue_pdf
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    issue: Issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    if issue is None:
        return f"Issue '{issue_id}' not found in series '{series_id}'."

    output = os.path.join(str(storage.base_path), "series", series_id, "issues", issue_id, "exports", f"{issue_id}.pdf")
    try:
        page_count, missing = bind_issue_pdf(storage, series_id, issue_id, output)
    except Exception as e:
        logger.error(f"Failed to bind issue {issue_id}: {e}")
        return f"Failed to bind the issue: {e}"

    if page_count == 0:
        return "Nothing to bind yet: no rendered covers or panels.  " + "; ".join(missing)
    note = ""
    if missing:
        note = f"  Still missing for a complete issue: " + "; ".join(missing)
    state.is_dirty = True
    return f"Issue '{issue.name}' bound to {output} ({page_count} pages).{note}"


@function_tool
def preflight_issue(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    Production preflight: everything standing between this issue and a complete,
    bindable book — unrendered panels, missing covers.   Run this before export,
    or whenever the user asks 'what's left?'.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the issue.

    Returns:
        A human-readable completeness report.
    """
    from helpers.binder import collect_issue
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    front, panels, back, missing = collect_issue(storage, series_id, issue_id)
    total = len(panels) + len(missing) - (0 if front else 1)
    report = [f"Rendered panels: {len(panels)}",
              f"Front cover: {'rendered' if front else 'MISSING'}",
              f"Back cover: {'rendered' if back else 'none'}"]
    if missing:
        report.append("To complete the issue:")
        report += [f"  - {m}" for m in missing]
    else:
        report.append("The issue is complete — ready to export (export_issue_pdf).")
    return "\n".join(report)


@function_tool
def layout_issue_pages(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str, pages: list[list[list[str]]]) -> str:
    """
    Lay out the issue's pages: assign every panel to a page grid.   Each page is
    a list of rows; each row is a list of 1-3 panel ids placed left to right.
    A page with one row of one panel is a splash page.   Replaces any existing
    page layout for the issue.

    Propose the page breakdown to the user BEFORE calling this: pacing lives in
    the page turn.   Panels are identified by panel_id alone (they are unique
    within an issue); every panel of the issue should appear exactly once.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.
        pages: The page grids, in reading order.  e.g. [[[p1],[p2,p3]], [[p4]]]
            = page 1 has panel p1 full-width above panels p2|p3; page 2 is a
            splash of p4.

    Returns:
        A status message summarizing the layout.
    """
    from schema import Page, PanelRef
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    # panel_id -> scene_id map for the whole issue
    scene_of: dict[str, str] = {}
    for scene in storage.read_all_objects(SceneModel, {"series_id": series_id, "issue_id": issue_id}):
        for p in storage.read_all_objects(Panel, {"series_id": series_id, "issue_id": issue_id, "scene_id": scene.scene_id}):
            scene_of[p.panel_id] = scene.scene_id

    unknown = [pid for page in pages for row in page for pid in row if pid not in scene_of]
    if unknown:
        return f"Unknown panel id(s): {', '.join(unknown[:5])}.  Check the shot list (read_all_panels per scene)."

    # replace existing layout
    for old in storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id}):
        storage.delete_object(cls=Page, primary_key=old.primary_key)

    placed = 0
    for i, page_rows in enumerate(pages, start=1):
        page = Page(page_id=f"page-{i}", issue_id=issue_id, series_id=series_id, page_number=i,
                    rows=[[PanelRef(scene_id=scene_of[pid], panel_id=pid) for pid in row] for row in page_rows])
        storage.create_object(data=page, overwrite=True)
        placed += sum(len(r) for r in page_rows)

    leftover = len(scene_of) - placed
    note = f"  NOTE: {leftover} panel(s) of the issue are not placed on any page." if leftover > 0 else ""
    state.is_dirty = True
    return f"Laid out {len(pages)} pages ({placed} panels placed).{note}"


def _render_asset_reference(wrapper, cls, key, series_id, asset_id, style_id, subject_line, guidance):
    """Shared renderer: reference art for a prop/outfit in a style, anchored to the style's art example."""
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    asset = storage.read_object(cls, {"series_id": series_id, key: asset_id})
    if asset is None:
        return f"{cls.__name__} '{asset_id}' not found in series '{series_id}'."
    style: ComicStyle = storage.read_object(ComicStyle, {"style_id": style_id})
    if style is None:
        return f"Style '{style_id}' not found."

    reference_images = []
    art_anchor = style.image.get("art") if isinstance(style.image, dict) else None
    if art_anchor and os.path.exists(art_anchor):
        reference_images.append(art_anchor)
    reference_images.extend(storage.list_uploads(obj=asset))

    prompt = f"""Render comic reference art of {subject_line}: "{asset.name}".
{guidance}
The rendering must strictly follow the comic style below so that composites
using this reference match the rest of the issue.

# {asset.name}
{asset.description}

{format_comic_style(style, include_bubble_styles=False, include_character_style=False, heading_level=1)}
"""
    locator = generate_object_image(
        wrapper=wrapper, obj=asset, prompt=prompt,
        reference_images=reference_images,
        aspect_ratio=FrameLayout.SQUARE, image_quality=IMAGE_QUALITY.HIGH,
        name=f"{asset_id}-{style_id}-reference")
    asset.images[style_id] = locator
    storage.update_object(data=asset)
    state.is_dirty = True
    return f"Reference art for '{asset.name}' rendered in style '{style_id}': {locator}"


@function_tool
def generate_prop_reference(wrapper: RunContextWrapper[APPState], series_id: str, prop_id: str, style_id: str) -> str:
    """
    Render a prop's reference art in a comic style: the prop alone on a neutral
    background, from a clear three-quarter view.   Stored on the prop keyed by
    style; composited into settings, variant sheets, and panels that use it.

    Args:
        series_id: The series that owns the prop.
        prop_id: The prop to render.
        style_id: The comic style to render in.
    """
    from schema import PropAsset
    return _render_asset_reference(
        wrapper, PropAsset, "prop_id", series_id, prop_id, style_id,
        "a single prop",
        "Show ONLY the prop on a neutral background — no characters, no scene — in a clear three-quarter view.")


@function_tool
def generate_outfit_reference(wrapper: RunContextWrapper[APPState], series_id: str, outfit_id: str, style_id: str) -> str:
    """
    Render an outfit's reference art in a comic style: the attire presented on
    a neutral display form (no face, no identity), front and back.   Stored on
    the outfit keyed by style; composited into variant reference sheets.

    Args:
        series_id: The series that owns the outfit.
        outfit_id: The outfit to render.
        style_id: The comic style to render in.
    """
    from schema import Outfit
    return _render_asset_reference(
        wrapper, Outfit, "outfit_id", series_id, outfit_id, style_id,
        "an outfit (wardrobe)",
        "Present the attire on a neutral, featureless display form — NO character identity, no face — front view and back view side by side, neutral background.")
