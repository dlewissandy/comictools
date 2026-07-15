import asyncio
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
    name: str = "generated_image",
    background: Optional[str] = None
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
            quality=image_quality,
            background=background
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
async def generate_publisher_logo_reference_image(
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

    return await asyncio.to_thread(_generate_publisher_logo_reference_image_sync, wrapper, publisher_id)


def _generate_publisher_logo_reference_image_sync(
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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"publisher_id": publisher_id}, state.storage)

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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"publisher_id": publisher_id}, state.storage)

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
async def generate_cover_image(wrapper: RunContextWrapper, series_id: str, issue_id: str, cover_id: str, text_layout_instructions: Optional[str] = None, takes: int = 1) -> str:
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
        takes (int): How many takes to render (1-4).  More takes = a contact sheet
            in the cover's image grid for the user to choose from (each costs money).

    Returns:
        A string indicating the status of the rendering operation.
    """

    return await asyncio.to_thread(_generate_cover_image_sync, wrapper, series_id, issue_id, cover_id, text_layout_instructions, takes)


def _generate_cover_image_sync(wrapper: RunContextWrapper, series_id: str, issue_id: str, cover_id: str, text_layout_instructions: Optional[str] = None, takes: int = 1) -> str:
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
        takes (int): How many takes to render (1-4).  More takes = a contact sheet
            in the cover's image grid for the user to choose from (each costs money).

    Returns:
        A string indicating the status of the rendering operation.
    """
    takes = max(1, min(int(takes or 1), 4))
    notes = [_generate_cover_image_body(wrapper, series_id, issue_id, cover_id, text_layout_instructions)
             for _ in range(takes)]
    if takes == 1:
        return notes[0]
    return (f"{takes} takes rendered — they're in the cover's image grid; the last is selected.  "
            f"Ask the user to pick a favorite.  " + notes[-1])


def _compose_table_rough(storage, board, scene) -> str | None:
    """Composite the board's visible acetates into the author's ROUGH — the
    literal pencils the inker finishes.  Returns the path of the composited
    image, or None when nothing is blocked on the table (then the render is
    composed free-form from the text brief alone)."""
    from uuid import uuid4
    from storage.filepath import obj_to_imagepath

    blk = board.figure_blocking or {}

    def on(key, default=1):
        return bool((blk.get(key) or {}).get('on', default))

    # blocking defaults MUST match what the light table displays with — the
    # rough the inker receives has to look like the rough the author saw
    layers = []
    for i, ref in enumerate(board.character_references or []):
        key = f"{ref.character_id}/{ref.variant_id}"
        path = (board.figure_images or {}).get(key)
        if path and os.path.exists(path) and on(key):
            layers.append((key, path, {"x": (18, 50, 82)[i % 3], "y": 0, "h": 78, "z": i}))
    for key, path in (board.figure_images or {}).items():
        if key.startswith('element/') and path and os.path.exists(path) and on(key):
            layers.append((key, path, {"x": 50, "y": 0, "h": 45, "z": 40}))
    # a reworked take laid down as the plate is authored content too — even
    # with no figure acetates over it, it IS the rough
    plate = (board.figure_images or {}).get('background/plate')
    if not layers and not (plate and os.path.exists(plate) and on('background')):
        return None

    from helpers.compositor import base_canvas, paste_acetates, collect_letters, paste_letters
    from helpers.stitcher import laid_aspect
    # THE ROUGH IS THE PAGE'S SHAPE: composite at the shape the layout gave this
    # panel (the flow may have flexed it), so the inked rough fills its cell
    _ba = laid_aspect(storage, board).value
    src, _ = _resolve_layer_source(board, scene, storage, board.series_id, 'background')
    base = base_canvas(_ba, src if (src and on('background')) else None)
    paste_acetates(base, _ba,
                   [(path, {**dflt, **(blk.get(key) or {})}) for key, path, dflt in layers])
    # the author's blocked letters ride the rough too, so the inker sees
    # where the balloons and captions land (placeholders never composite)
    paste_letters(base, _ba, collect_letters(board))

    figures_dir = os.path.join(os.path.dirname(obj_to_imagepath(obj=board, base_path=storage.base_path)), "figures")
    os.makedirs(figures_dir, exist_ok=True)
    out = os.path.join(figures_dir, f"rough--{uuid4().hex[:8]}.png")
    base.convert('RGB').save(out, 'PNG')
    return out


def _table_layout_brief(board, storage=None) -> str:
    """The author's light-table blocking as prompt lines — figure positions,
    depths, mirroring, and element OMIT/placement notes.  A board is anything
    composed on the light table: a panel or a cover."""
    blk = board.figure_blocking or {}

    def _pct(v):
        return f"{round(float(v))}%"

    lines = []
    from schema import CharacterModel as _CM
    _names = {}
    try:
        if storage is None:
            from storage import registry as _reg
            slug = _reg.house_of_series(board.series_id)
            storage = _reg.storage_for(slug) if slug else None
        if storage is not None:
            _names = {c.character_id: c.name for c in
                      storage.read_all_objects(_CM, {"series_id": board.series_id})}
    except Exception:
        pass

    def _who(cid):
        # a raw id reads as gibberish and can get lettered into the art
        return _names.get(cid) or cid.replace('-', ' ')

    for ref in (board.character_references or []):
        b = blk.get(f"{ref.character_id}/{ref.variant_id}") or {}
        if not b:
            continue
        if not b.get('on', 1):
            # the author lifted this acetate off the table — honor that
            lines.append(f"* OMIT {_who(ref.character_id)} from this image entirely")
            continue
        h = float(b.get('h', 60))
        depth = "in the near foreground, large" if h >= 88 else ("far in the background, small" if h <= 45 else "in the mid-ground")
        lines.append(f"* {_who(ref.character_id)} stands at {_pct(b.get('x', 50))} from left, {depth}"
                     + (f", raised {_pct(b['y'])} above the frame bottom" if float(b.get('y', 0)) > 5 else "")
                     + ("; only partly in frame, rising from below the bottom edge" if float(b.get('y', 0)) < -5 else "")
                     + ("; MIRRORED left-to-right versus their reference sheet" if b.get('flip') else "")
                     + (f"; TILTED {float(b['rot']):g} degrees clockwise" if b.get('rot') else ""))
    for key, path in sorted((board.figure_images or {}).items()):
        if not key.startswith('element/'):
            continue
        b = blk.get(key) or {}
        if not b.get('on', 1):
            lines.append(f"* OMIT the {key.split('/', 1)[1].replace('-', ' ')} entirely")
        elif b:
            lines.append(f"* the {key.split('/', 1)[1].replace('-', ' ')} sits at {_pct(b.get('x', 50))} from left")
    return "\n".join(lines)


def _generate_cover_image_body(wrapper, series_id: str, issue_id: str, cover_id: str, text_layout_instructions: Optional[str] = None) -> str:
    state: APPState = wrapper.context
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

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

    # a LIST, not a dict keyed by name — the same character can appear
    # in two variants on a cover and both must reach the artist
    characters: list[tuple[str, CharacterVariant]] = []
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
        characters.append((character.name, variant))

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
            from helpers.masters import master_for
            background, _exact = master_for(setting, cover.style_id, cover.aspect)
            if background and os.path.exists(background):
                reference_image_locators.append(background)
                background_first = True
            else:
                missing.append(f"master background for '{setting.name}' in style '{cover.style_id}' (generate_setting_background)")
            setting_information = f"# Setting\n{'Interior' if setting.interior else 'Exterior'}: {setting.name}\n{setting.description}\n"

    for name, variant in characters:
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
        for name, variant in characters:
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

    # THE ROUGH IS THE PENCILS: when the author blocked acetates on the
    # cover's light table, composite them and hand them to the cover artist.
    rough_ref = _compose_table_rough(storage, cover, None)
    if rough_ref:
        reference_image_locators.insert(0, rough_ref)
        background_guidance = (
            "The FIRST reference image is the author's ROUGH of this cover — the exact "
            "composition assembled on the light table.   It is AUTHORITATIVE and OVERRIDES the "
            "cover design text for composition: keep every figure and element at its position, "
            "scale and facing, draw only what it shows, then finish and ink it in the style and "
            "letter the trade dress over it (the cover-design text is for identity and detail "
            "only).\n"
            + ("The NEXT reference image is the setting's master background — same architecture, "
               "same palette, reframed as the composition requires.\n" if background_first else ""))

    # THE OFFICIAL MASTHEAD: when the series has title art in this style,
    # the cover's title lettering is held to it
    masthead_guidance = ""
    title_art = (series.title_images or {}).get(cover.style_id)
    if title_art and os.path.exists(title_art):
        reference_image_locators.append(title_art)
        masthead_guidance = ("One reference image shows THE OFFICIAL MASTHEAD — the series title "
                             "wordmark.  Wherever the design shows the series title, reproduce that "
                             "exact lettering.\n")

    # honor whatever the author arranged on the cover's light table
    table_layout = _table_layout_brief(cover, storage)

    prompt = f"""
    Create a comic book {location_name} cover.   The image should be have a {cover.aspect.value} orientation/aspect ratio.
{background_guidance}{masthead_guidance}

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

{f"# Layout — the author BLOCKED this on the light table; honor positions and depths{chr(10)}{table_layout}" if table_layout else ""}

# One hand, one finish
Redraw EVERY element — background, characters, props, trade dress — in ONE unified hand:
the same line weight, level of detail, shading, palette and finish, as if a single artist
painted the whole cover in one pass.   The reference images fix identity and composition
ONLY — never copy one at its own resolution or finish; the background must not read as more
photographic or more finely rendered than the figures.   Flatten everything to the single
style above so nothing looks pasted in.
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
    # persist onto a FRESH read: the render takes minutes and the author may
    # have kept working on the cover meanwhile — never write back a stale copy
    fresh = storage.read_object(cls=Cover, primary_key=cover.primary_key) or cover
    fresh.image = locator
    storage.update_object(data=fresh)
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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

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
async def create_character_style_example_image(
    wrapper: RunContextWrapper[APPState],
    style_id: str
) -> str:
    """
    Render the CHARACTER exemplar image for a comic style — the style's
    reference figure drawing that character sheets are held to.  Use when a
    style is missing its character example or the author asks to redo it.

    Args:
        style_id: The ID of the comic style to render the character exemplar for.

    Returns:
        A status message with the rendered image locator.
    """
    return await asyncio.to_thread(_create_character_style_example_image_sync, wrapper, style_id)


def _create_character_style_example_image_sync(
    wrapper: RunContextWrapper[APPState],
    style_id: str
) -> str:
    state: APPState = wrapper.context
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"style_id": style_id}, state.storage)

    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if not style:
        return f"Style with ID {style_id} not found."
    style: ComicStyle = style

    try:
        with open(os.path.join(str(storage.base_path), "prompts", "imaging", "character-style-example.md"), "r") as f:
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

    


def create_styled_image_body(state, series_id: str, character_id: str,
                             variant_id: str, style_id: str,
                             peer_anchor_ids: list = None) -> str:
    """Render a variant's styled reference sheet in one style — callable
    directly from the GUI (background job) or via the tool.

    peer_anchor_ids: character ids whose base sheets DEFINE the hand this
    render must match (the 'artist').  When given, those anchor the cast's
    shared hand instead of an arbitrary pair — this is how 'ink the cast in
    one hand' holds everyone to one lead, and the hook a future named
    ARTIST plugs into."""
    class _W:  # minimal wrapper shim for generate_object_image
        context = state
    wrapper = _W()
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

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
        with open(os.path.join(str(storage.base_path), "prompts", "imaging", "styled-variant.md"), "r") as f:
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
    # THE EXEMPLARS LEAD: the variant's uploads (a sculpted exemplar, a
    # pasted face, a family-look anchor) hold every sheet to the same person
    exemplars = [u for u in storage.list_uploads(obj=variant) if u and os.path.exists(u)]
    if exemplars:
        reference_images.extend(exemplars[:3])
        prompt += ("\n\n## EXEMPLARS\nThe first reference image(s) show THIS EXACT "
                   "CHARACTER — hold the face, build, and identity to them precisely.")

    # THE BASE ANCHORS CONTINUITY: a look is the SAME PERSON in different
    # wardrobe — so a non-base look must carry the base's reference image
    # (the face and build to hold to) AND the base's identity text, or the
    # render drifts into a different character.
    _nm = (variant.name or "").strip().lower()
    is_base_look = (variant_id == "base" or _nm == "base" or _nm.endswith(" base"))
    if not is_base_look:
        _looks = storage.read_all_objects(CharacterVariant,
            {"series_id": series_id, "character_id": character_id})
        base_variant = next((v for v in _looks
            if v.variant_id == "base" or (v.name or "").strip().lower() == "base"
            or (v.name or "").strip().lower().endswith(" base")), None)
        if base_variant is None:   # no formal base — the fullest OTHER look anchors it
            base_variant = next((v for v in _looks
                if v.variant_id != variant_id and ((v.images or {}) or v.appearance)), None)
        if base_variant is not None:
            # INK THE BASE FIRST: if the character has no sheet in this style
            # yet, render it now (from its own description/exemplars) so this
            # look anchors to a clean style-matched identity, not nothing.
            # ONLY a GENUINE base is cascade-inked — a fallback anchor (some
            # other look) is used as-is, never recursively inked, or two
            # baseless looks would ink each other forever.  A re-entrancy
            # guard is the belt to that suspenders.
            _bnm = (base_variant.name or "").strip().lower()
            base_is_true = (base_variant.variant_id == "base"
                            or _bnm == "base" or _bnm.endswith(" base"))
            _guard = getattr(state, "_inking_looks", None)
            if _guard is None:
                _guard = set(); state._inking_looks = _guard
            _key = (character_id, base_variant.variant_id, style_id)
            if (base_is_true
                    and not ((base_variant.images or {}).get(style_id)
                             and os.path.exists(base_variant.images[style_id]))
                    and _key not in _guard):
                _guard.add(_key)
                try:
                    create_styled_image_body(state, series_id, character_id,
                                             base_variant.variant_id, style_id)
                    base_variant = storage.read_object(CharacterVariant, base_variant.primary_key) or base_variant
                except Exception as ex:
                    logger.warning(f"cascade-ink of base look failed: {ex}")
                finally:
                    _guard.discard(_key)
            base_img = (base_variant.images or {}).get(style_id) or next(
                (i for i in (base_variant.images or {}).values() if i and os.path.exists(i)), None)
            base_ups = [u for u in storage.list_uploads(obj=base_variant) if u and os.path.exists(u)]
            anchor = base_img if (base_img and os.path.exists(base_img)) else (base_ups[0] if base_ups else None)
            if anchor:
                # the identity anchor leads every other reference
                reference_images.insert(0, anchor)
                prompt += (f"\n\n## THE CHARACTER — identity anchor (FIRST reference image)\n"
                           f"The first reference image IS {character_name}.  Hold their FACE, "
                           f"BUILD, SKIN, HAIR and every identifying feature to it EXACTLY — "
                           f"this look changes only their wardrobe and what they carry, never "
                           f"who they are.")
            else:
                missing.append(f"the base look's reference sheet — render {character_name}'s "
                               f"base look first, or this look won't match the character")
            # identity is inherited from the base, in text too
            prompt += (f"\n\n## Identity (unchanging across every look)\n"
                       f"* Race: {base_variant.race}\n* Gender: {base_variant.gender}\n"
                       f"* Age: {base_variant.age}\n* Height: {base_variant.height}\n"
                       f"* Physical appearance: {base_variant.appearance}\n"
                       f"* Behavior/bearing: {base_variant.behavior}")

    # INK EVERY DEPENDENCY FIRST: a composite is only as consistent as its
    # parts.  Anything not yet inked in THIS style — the wardrobe, a prop —
    # gets rendered from its exemplar NOW, so the composite always draws
    # from clean style-matched references, never a raw dropped photo.
    def _inked_art(asset, render_body, kind_label):
        art = (asset.images or {}).get(style_id)
        if art and os.path.exists(art):
            return art
        exemplars_ = [u for u in storage.list_uploads(obj=asset) if u and os.path.exists(u)]
        if exemplars_ or asset.description:
            try:
                render_body()
                fresh_asset = storage.read_object(type(asset), asset.primary_key)
                art = (fresh_asset.images or {}).get(style_id) if fresh_asset else None
                if art and os.path.exists(art):
                    return art
            except Exception as ex:
                logger.warning(f"cascade-ink of {kind_label} '{asset.name}' failed: {ex}")
        return None

    if variant.outfit_id:
        outfit = storage.read_object(Outfit, {"series_id": series_id, "outfit_id": variant.outfit_id})
        if outfit is None:
            missing.append(f"outfit '{variant.outfit_id}' (asset not found)")
        else:
            art = _inked_art(outfit,
                             lambda: render_outfit_reference_body(state, series_id, outfit.outfit_id, style_id),
                             "outfit")
            if art:
                reference_images.append(art)
            else:
                missing.append(f"reference art for outfit '{outfit.name}' in style '{style_id}' "
                               f"(needs an exemplar or description to ink)")
            prompt += f"\n\n## Outfit: {outfit.name}\n{outfit.description}"
    for pid in (variant.prop_ids or []):
        prop = storage.read_object(PropAsset, {"series_id": series_id, "prop_id": pid})
        if prop is None:
            missing.append(f"prop '{pid}' (asset not found)")
            continue
        art = _inked_art(prop,
                         lambda prop=prop: render_prop_reference_body(state, series_id, prop.prop_id, style_id),
                         "prop")
        if art:
            reference_images.append(art)
        else:
            missing.append(f"reference art for prop '{prop.name}' in style '{style_id}' "
                           f"(needs an exemplar or description to ink)")
        prompt += f"\n\n## Carried prop: {prop.name}\n{prop.description}"

    # ONE HAND FOR THE WHOLE CAST: pass up to two ALREADY-INKED castmates
    # (other characters' base looks in THIS style) as a shared-style anchor,
    # so a new character is drawn by the same artist as the established cast
    # — not a fresh interpretation of the style prose.  Labeled hard as
    # DIFFERENT PEOPLE so their faces and builds never bleed in.
    # when an ANCHOR set is named (an 'artist', or the lead of a one-hand
    # pass), those characters define the hand; otherwise any two inked
    # castmates do
    _others = storage.read_all_objects(CharacterModel, {"series_id": series_id})
    if peer_anchor_ids:
        _rank = {cid: i for i, cid in enumerate(peer_anchor_ids)}
        _others = sorted((o for o in _others if o.character_id in _rank),
                         key=lambda o: _rank[o.character_id])
    peers = []
    for other in _others:
        if other.character_id == character_id:
            continue
        # only a peer whose sheet is in THIS style anchors the shared hand
        ov = next((v for v in storage.read_all_objects(CharacterVariant,
                   {"series_id": series_id, "character_id": other.character_id})
                   if (v.images or {}).get(style_id) and os.path.exists(v.images[style_id])), None)
        if ov is not None:
            peers.append((other.name, ov.images[style_id]))
        if len(peers) >= 2:
            break
    if peers:
        reference_images.extend(p for _n, p in peers)
        who = ", ".join(n for n, _p in peers)
        prompt += (f"\n\n## THE CAST'S SHARED HAND (last reference image(s))\n"
                   f"The final reference image(s) show OTHER characters of this book "
                   f"({who}) already drawn in this style.  Match their ARTIST'S HAND "
                   f"exactly — the same linework weight, inking, palette, shading, level "
                   f"of detail and rendering — so the whole cast looks drawn by one "
                   f"artist.  They are DIFFERENT PEOPLE: do NOT copy their faces, hair, "
                   f"builds or wardrobe; take ONLY the drawing style from them.")

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

    # Update the variant with the new image locator — onto a FRESH read; the
    # render takes minutes and the variant may have changed meanwhile.
    # NON-DESTRUCTIVE RE-ROLL: every take is kept (newest first); the new
    # one becomes the current pick, the prior sheet waits to be compared.
    fresh = storage.read_object(cls=CharacterVariant, primary_key=variant.primary_key) or variant
    takes = list((fresh.image_takes or {}).get(style.style_id, []))
    prior = fresh.images.get(style.style_id)
    if prior and prior not in takes:      # fold an untracked existing sheet in
        takes.insert(0, prior)
    takes = [locator] + [t for t in takes if t != locator]
    fresh.image_takes = {**(fresh.image_takes or {}), style.style_id: takes}
    fresh.images[style.style_id] = locator
    storage.update_object(data=fresh)

    note = ""
    if missing:
        note = "  NOTE: rendered without: " + "; ".join(missing) + ".  Generate those references and re-render for better consistency."
    return f"Styled image created successfully with locator: {locator}.{note}"


@function_tool
def ink_cast_in_one_hand(wrapper: RunContextWrapper[APPState], series_id: str,
                         style_id: str, lead_character_id: Optional[str] = None) -> str:
    """
    Redraw EVERY character's base reference sheet in one style so the whole
    cast is drawn by a single artist's hand.  A lead character (whose current
    sheet defines the hand) is inked first; the rest are held to it.  Runs in
    the background; each sheet posts a receipt as it lands.

    Args:
        series_id: The series whose cast to unify.
        style_id: The comic style to draw the whole cast in.
        lead_character_id: The character whose sheet sets the hand (optional).
    """
    from helpers.render_queue import enqueue_renders
    state: APPState = wrapper.context
    jobs = ink_cast_in_one_hand_body(state, series_id, style_id, lead_character_id)
    if not jobs:
        return "No character base looks to redraw yet — create the cast first."
    enqueue_renders(state, jobs, role="the Character Designer")
    return (f"Redrawing {len(jobs)} character sheets in one hand"
            + (f" led by {lead_character_id}" if lead_character_id else "")
            + " — they land as they finish.")


def ink_cast_in_one_hand_body(state, series_id: str, style_id: str,
                              lead_character_id: str = None) -> list:
    """Re-ink every character's BASE look in one style so the whole cast is
    drawn by a single hand.  Returns [(label, job)] render jobs to enqueue.

    A LEAD (an 'artist') whose sheet defines the hand is inked/kept first;
    every other character is then re-inked HELD TO THE LEAD.  With no lead,
    the cast is inked in order, each held to those already done (a chain).
    """
    from schema import CharacterModel as _CM, CharacterVariant as _CV

    def _base_id(cid):
        looks = state.storage.read_all_objects(_CV, {"series_id": series_id, "character_id": cid})
        base = next((v for v in looks if v.variant_id == "base"
                     or (v.name or "").strip().lower() == "base"
                     or (v.name or "").strip().lower().endswith(" base")), None)
        if base is None and looks:
            base = looks[0]
        return base.variant_id if base else None

    chars = state.storage.read_all_objects(_CM, {"series_id": series_id})
    order = [c for c in chars if c.character_id != lead_character_id]
    jobs = []
    if lead_character_id:
        lead = next((c for c in chars if c.character_id == lead_character_id), None)
        lead_base = _base_id(lead_character_id)
        if lead is not None and lead_base:
            # the lead is inked FIRST (if it isn't already the hand) — every
            # other character is then held to it
            jobs.append((f"the lead — {lead.name} (defines the hand)",
                         lambda cid=lead_character_id, vid=lead_base:
                         create_styled_image_body(state, series_id, cid, vid, style_id)))
        for c in order:
            vid = _base_id(c.character_id)
            if vid:
                jobs.append((f"{c.name} — redrawn in {lead.name if lead else 'the'} hand",
                             lambda cid=c.character_id, vid=vid:
                             create_styled_image_body(state, series_id, cid, vid, style_id,
                                                      peer_anchor_ids=[lead_character_id])))
    else:
        done = []
        for c in chars:
            vid = _base_id(c.character_id)
            if not vid:
                continue
            anchors = list(done)
            jobs.append((f"{c.name} — in the cast's shared hand",
                         lambda cid=c.character_id, vid=vid, a=anchors:
                         create_styled_image_body(state, series_id, cid, vid, style_id,
                                                  peer_anchor_ids=a or None)))
            done.append(c.character_id)
    return jobs


@function_tool
async def create_styled_image_for_character_variant(
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

    return await asyncio.to_thread(_create_styled_image_for_character_variant_sync, wrapper, series_id, character_id, variant_id, style_id)


def _create_styled_image_for_character_variant_sync(
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
    return create_styled_image_body(wrapper.context, series_id, character_id, variant_id, style_id)

@function_tool
async def create_art_style_example_image(
    wrapper: RunContextWrapper[APPState],
    style_id: str
) -> str:
    """
    Create an example of an art style as an image.
    
    Returns:
        A message indicating the result of the operation.
    """

    return await asyncio.to_thread(_create_art_style_example_image_sync, wrapper, style_id)


def _create_art_style_example_image_sync(
    wrapper: RunContextWrapper[APPState],
    style_id: str
) -> str:
    """
    Create an example of an art style as an image.
    
    Returns:
        A message indicating the result of the operation.
    """
    state: APPState = wrapper.context
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"style_id": style_id}, state.storage)
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if not style:
        return f"Cannot create art style image.   Style with ID {style_id} not found."
    style: ComicStyle = style

    REFERENCE_IMAGE = os.path.join(str(storage.base_path), "references", "art-style.jpg")
    
    # Serialize the descripiton of the style
    style_info = format_comic_style(
        include_bubble_styles=False,
        include_character_style=False,
        style=style,
        heading_level=2

    )

    # Render the image using the OpenAI images API and the art style description
    logger.debug(f"Rendering art style image with style: {style.name}")
    with open(os.path.join(str(storage.base_path), "prompts", "imaging", "art-style-example.md"), "r") as f:
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
async def create_dialog_style_example_image(
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

    return await asyncio.to_thread(_create_dialog_style_example_image_sync, wrapper, style_id, dialog_type)


def _create_dialog_style_example_image_sync(
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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"style_id": style_id}, state.storage)

    pk = { "style_id": style_id }
    style = storage.read_object(cls=ComicStyle, primary_key=pk)
    if not style:
        return f"Cannot generate example image.  Style with ID {style_id} not found."
    style: ComicStyle = style

    # Create the prompt
    with open(os.path.join(str(storage.base_path), "prompts", "imaging", "dialog-style-example.md"), "r") as f:
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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"style_id": style_id}, state.storage)
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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"style_id": style_id}, state.storage)
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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"style_id": style_id}, state.storage)
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


def _write_choices_manifest(image_locator: str, session_id: str, choices: list[str],
                            region: dict | None = None, mode: str | None = None) -> None:
    import time as _time
    from uuid import uuid4 as _uuid4
    path = _choices_manifest_path(image_locator, session_id)
    payload = {
        "image": image_locator,
        "choices": choices,
        "session_id": session_id,
        "written_at": _time.time(),
        "region": region,
        "mode": mode,
    }
    tmp = f"{path}.{_uuid4().hex[:6]}.tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)


def _is_intent_only(text: str, mode: str) -> bool:
    lowered = " ".join(text.lower().strip().split())
    if mode == "inpaint":
        return lowered in {
            "i would like to inpaint a region of this image.",
            "i would like to inpaint a region of this image",
            "inpaint",
            "inpaint a region",
            "inpaint a region of this image",
            "heal the marked patch of this image.",
            "heal the marked patch of this image",
            "heal the patch",
            "heal the marked patch",
        }
    if mode == "outpaint":
        return lowered in {
            "i would like to outpaint a region of this image.",
            "i would like to outpaint a region of this image",
            "outpaint",
            "outpaint a region",
            "outpaint a region of this image",
            "extend the paper on this image.",
            "extend the paper on this image",
            "extend the paper",
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


def _has_real_alpha(path: str) -> bool:
    """True when the image actually uses transparency — an acetate, not a
    print.  Heals of acetates must come back clear, not on a slab."""
    try:
        from PIL import Image
        img = Image.open(path)
        if img.mode in ('RGBA', 'LA'):
            a_min, _ = img.getchannel('A').getextrema()
            return a_min < 250
        return 'transparency' in img.info
    except Exception:
        return False


def _choices_epilogue(state, image_locator: str, session_id: str, mode: str):
    """The on-loop epilogue for a queued heal: when the takes land, the
    editor state points at them and the choices sheet opens itself —
    UI work stays on the event loop, paint work stays off it."""
    def after(choices):
        if isinstance(choices, tuple):
            choices = choices[0]
        here = state.selection[-1] if state.selection else None
        still_here = (getattr(state, 'image_editor_image', None) == image_locator
                      and here is not None
                      and here.kind.value in ('image-editor', 'image-editor-choices'))
        if not still_here:
            # the author moved on — the manifest waits; the editor's
            # recovery door offers the takes back whenever they return
            return
        state.image_editor_choices = choices
        state.image_editor_choice_selected = choices[0] if choices else None
        state.image_editor_original_image = image_locator
        state.image_editor_image = image_locator
        state.image_editor_session_id = session_id
        state.image_editor_mode = mode
        new_sel = [s for s in state.selection
                   if s.kind.value != 'image-editor-choices']
        new_sel.append(SelectionItem(name="Choices", id=f"{session_id}|{image_locator}",
                                     kind=SelectedKind.IMAGE_EDITOR_CHOICES))
        state.change_selection(new=new_sel)
    return after


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

    # NOTHING BLOCKS THE BRUSH: the mask is cut here (fast), the paint job
    # goes on the drawing board, and the choices sheet opens on the loop
    # when the four takes land — the studio never freezes
    from uuid import uuid4 as _uuid4
    session_id = _uuid4().hex[:8]          # per-HEAL, never shared
    state.image_editor_session_id = session_id
    if selection:
        mask_path, (w, h) = _create_inpaint_mask(image_locator, selection)
    else:
        mask_path, (w, h) = _create_full_mask(image_locator)
    try:
        size = _choose_output_size(w, h)
        refs = _collect_reference_images(state, instruction)
    except Exception:
        if mask_path and os.path.exists(mask_path):
            os.remove(mask_path)
        raise

    is_acetate = _has_real_alpha(image_locator)

    def job():
        try:
            kwargs = {}
            if is_acetate:
                # CLEAR ACETATE: the heal keeps the transparency and the
                # exact pixels outside the patch
                kwargs = {"background": "transparent", "input_fidelity": "high"}
            images = invoke_edit_image_api(
                prompt=instruction,
                reference_images=_merge_reference_images(image_locator, refs),
                mask=mask_path,
                size=size,
                quality=IMAGE_QUALITY.HIGH,
                n=4,
                **kwargs,
            )
        finally:
            if mask_path and os.path.exists(mask_path):
                os.remove(mask_path)
        if isinstance(images, bytes):
            images = [images]
        choices = [_save_image_bytes(img, image_locator, prefix=f"choice-{session_id}")
                   for img in images]
        if not choices:
            raise RuntimeError("no images came back — try again")
        _write_choices_manifest(image_locator, session_id, choices,
                                region=selection, mode="inpaint")
        if is_acetate and not any(_has_real_alpha(c) for c in choices):
            return (choices, "NOTE: the takes came back OPAQUE — applying one "
                             "restores the acetate's transparency outside the "
                             "healed patch, but check the result.")
        return choices

    _open_choices_after = _choices_epilogue(state, image_locator, session_id, mode="inpaint")
    from helpers.render_queue import enqueue_renders
    enqueue_renders(state, [(f"healing {os.path.basename(image_locator)} — four takes",
                             job, _open_choices_after)], role='the Inker')
    return ("The heal is on the drawing board — four takes land here shortly, "
            "and the choices sheet opens by itself. Nothing is applied until "
            "one is picked.")


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

    # NOTHING BLOCKS THE BRUSH: assets prepared here (fast), the paint job
    # goes on the drawing board, the choices sheet opens when takes land
    padding = {"top": 256, "bottom": 256, "left": 256, "right": 256}
    from uuid import uuid4 as _uuid4
    session_id = _uuid4().hex[:8]          # per-HEAL, never shared
    state.image_editor_session_id = session_id
    base_path, mask_path, (w, h) = _prepare_outpaint_assets(image_locator, padding)
    try:
        size = _choose_output_size(w, h)
        refs = _collect_reference_images(state, instruction)
    except Exception:
        for _pth in (base_path, mask_path):
            if _pth and os.path.exists(_pth):
                os.remove(_pth)
        raise

    def job():
        try:
            images = invoke_edit_image_api(
                prompt=instruction,
                reference_images=_merge_reference_images(base_path, refs),
                mask=mask_path,
                size=size,
                quality=IMAGE_QUALITY.HIGH,
                n=4,
            )
        finally:
            for path in [base_path, mask_path]:
                if path and os.path.exists(path):
                    os.remove(path)
        if isinstance(images, bytes):
            images = [images]
        choices = [_save_image_bytes(img, image_locator, prefix=f"choice-{session_id}")
                   for img in images]
        if not choices:
            raise RuntimeError("no images came back — try again")
        _write_choices_manifest(image_locator, session_id, choices, mode="outpaint")
        return choices

    _open_choices_after = _choices_epilogue(state, image_locator, session_id, mode="outpaint")
    from helpers.render_queue import enqueue_renders
    enqueue_renders(state, [(f"extending {os.path.basename(image_locator)} — four takes",
                             job, _open_choices_after)], role='the Inker')
    return ("The extension is on the drawing board — four takes land here "
            "shortly, and the choices sheet opens by itself. Nothing is "
            "applied until one is picked.")



# -------------------------------------------------------------------------
# MASTER BACKGROUNDS AND PANEL RENDERING
#
# A setting's master background is inked once per style (the empty setting,
# as described).  Panels are then composed ON TOP of that background
# with the cast's styled reference sheets, so the setting stays visually
# consistent across every panel that takes place there.
# -------------------------------------------------------------------------
from schema import Setting, SceneModel

def generate_series_title_art_body(state, series_id: str, style_id: str,
                                   notes: str | None = None) -> str:
    """Render THE TITLE ART: the series masthead — the title hand-lettered in
    one comic style on transparent acetate.  Stored on the series keyed by
    style; covers hold their title lettering to it, and art-only covers can
    wear it as an overlay on the light table.  `notes` is the author's
    lettering direction ('drippy horror letters', 'chrome sci-fi')."""
    from helpers.generator import invoke_edit_image_api, invoke_generate_image_api

    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
    if series is None:
        return f"Series '{series_id}' not found."
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if style is None:
        return f"Style '{style_id}' not found."

    prompt = f"""Design THE MASTHEAD for a comic book series: the title
"{series.name}" as hand-lettered display lettering — a comic logo/wordmark.

Wide banner composition, lettering only: NO characters, NO scenery, NO frame,
NO other text.  Bold and readable at cover size, with the inking, palette and
energy of the comic style below.  COMPLETELY TRANSPARENT background — this is
an acetate overlay to be composited onto cover art.
{("THE AUTHOR'S LETTERING DIRECTION: " + notes) if notes else ""}

{format_comic_style(style, include_bubble_styles=False, include_character_style=False, heading_level=1)}
"""
    art = style.image.get('art') if isinstance(style.image, dict) else style.image
    refs = [art] if art and os.path.exists(art) else []
    refs.extend(storage.list_uploads(obj=series))
    if refs:
        image_bytes = invoke_edit_image_api(
            prompt, reference_images=refs, size="1536x1024",
            quality=IMAGE_QUALITY.HIGH, background="transparent")
    else:
        image_bytes = invoke_generate_image_api(prompt, size="1536x1024",
                                                quality=IMAGE_QUALITY.HIGH)
    locator = storage.upload_binary_image(obj=series, data=image_bytes)

    # persist onto a FRESH read — renders take minutes
    fresh = storage.read_object(cls=Series, primary_key={"series_id": series_id}) or series
    fresh.title_images[style_id] = locator
    storage.update_object(data=fresh)
    state.is_dirty = True
    return f"Title art for '{series.name}' inked in style '{style_id}': {locator}"


@function_tool
async def generate_series_title_art(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    style_id: str,
    notes: Optional[str] = None,
) -> str:
    """
    Render THE TITLE ART for a series: the series title hand-lettered as a comic
    masthead (logo/wordmark) in the given style, on a transparent background.
    Stored on the series keyed by style.   Covers hold their title lettering to
    this reference, and art-only covers can wear it as a composited overlay.

    Args:
        series_id: The ID of the series whose title to letter.
        style_id: The comic style to letter the masthead in.
        notes: The author's lettering direction, e.g. 'drippy horror letters',
            'chrome sci-fi', 'circus poster woodtype'.  Optional.

    Returns:
        A status message with the locator of the rendered title art.
    """

    return await asyncio.to_thread(_generate_series_title_art_sync, wrapper, series_id, style_id, notes)


def _generate_series_title_art_sync(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    style_id: str,
    notes: Optional[str] = None,
) -> str:
    """
    Render THE TITLE ART for a series: the series title hand-lettered as a comic
    masthead (logo/wordmark) in the given style, on a transparent background.
    Stored on the series keyed by style.   Covers hold their title lettering to
    this reference, and art-only covers can wear it as a composited overlay.

    Args:
        series_id: The ID of the series whose title to letter.
        style_id: The comic style to letter the masthead in.
        notes: The author's lettering direction, e.g. 'drippy horror letters',
            'chrome sci-fi', 'circus poster woodtype'.  Optional.

    Returns:
        A status message with the locator of the rendered title art.
    """
    return generate_series_title_art_body(wrapper.context, series_id, style_id, notes)


def generate_setting_background_body(state, series_id: str, setting_id: str, style_id: str,
                                     aspect: FrameLayout | str | None = None) -> str:
    """Render a setting's master background in one style — callable directly
    from the GUI (background job) or via the tool.  `aspect` should be the
    ASPECT OF THE BOARD the master is for (portrait covers get portrait
    masters); defaults to landscape for a classic establishing view."""
    class _W:  # minimal wrapper shim for generate_object_image
        context = state
    wrapper = _W()
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    if isinstance(aspect, str):
        aspect = FrameLayout(aspect)
    aspect = aspect or FrameLayout.LANDSCAPE

    setting: Setting = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": setting_id})
    if setting is None:
        return f"Setting '{setting_id}' not found in series '{series_id}'."
    style: ComicStyle = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if style is None:
        return f"Style '{style_id}' not found."

    interior_or_exterior = "an interior" if setting.interior else "an exterior"
    view_line = {"landscape": "a wide establishing view",
                 "portrait": "a tall establishing view (portrait orientation, as for a cover)",
                 "square": "a square establishing view"}[aspect.value]

    prompt = f"""Render a comic book master background of {interior_or_exterior} setting: "{setting.name}".

This is an EMPTY SETTING: render the place exactly as described — its furniture
and dressing live in the description below — with absolutely NO characters,
people, or creatures in it.   Compose it as {view_line}
with generous negative space where characters can later be
placed.   The rendering must strictly follow the comic style below so that
panels composed on top of this background match the rest of the issue.

# Setting
{setting.description}

{format_comic_style(style, include_bubble_styles=False, include_character_style=False, heading_level=1)}
"""

    # Uploaded reference images (e.g. multi-angle sketches or photos) steer the render.
    reference_images = storage.list_uploads(obj=setting)

    locator = generate_object_image(
        wrapper=wrapper,
        obj=setting,
        prompt=prompt,
        reference_images=reference_images,
        aspect_ratio=aspect,
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{setting_id}-{style_id}-background",
    )

    # persist onto a FRESH read: the render takes minutes and the author may
    # have kept working on the setting meanwhile
    fresh = storage.read_object(cls=Setting, primary_key=setting.primary_key) or setting
    from helpers.masters import master_key
    _mk = master_key(style_id, aspect)
    fresh.images[_mk] = locator
    if _mk in (fresh.images_stale or []):
        fresh.images_stale = [k for k in fresh.images_stale if k != _mk]
    storage.update_object(data=fresh)
    state.is_dirty = True
    return f"Master background for '{setting.name}' rendered in style '{style_id}': {locator}"


def generate_setting_shot_body(state, series_id: str, setting_id: str, shot_id: str,
                               style_id: str, aspect: FrameLayout | str | None = None) -> str:
    """Render a reusable SHOT of a setting — the establishing master re-framed at
    the shot's angle and time of day — in one style.  A shot is a durable
    reference asset (finished panels composite it), so it inks at HIGH like a
    master, not at the throwaway LOW of a blocking pose.  Callable from the GUI
    (background job) or a tool."""
    class _W:
        context = state
    wrapper = _W()
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    if isinstance(aspect, str):
        aspect = FrameLayout(aspect)
    aspect = aspect or FrameLayout.LANDSCAPE

    setting: Setting = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": setting_id})
    if setting is None:
        return f"Setting '{setting_id}' not found in series '{series_id}'."
    shot = next((s for s in (setting.shots or []) if s.shot_id == shot_id), None)
    if shot is None:
        return f"Shot '{shot_id}' not found on setting '{setting.name}'."
    style: ComicStyle = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
    if style is None:
        return f"Style '{style_id}' not found."

    interior_or_exterior = "an interior" if setting.interior else "an exterior"
    orient_line = {"landscape": "landscape orientation", "portrait": "portrait orientation",
                   "square": "square orientation"}[aspect.value]

    # THE MASTER IS THE ANCHOR: re-frame the SAME place, so the shot stays on
    # the establishing view's architecture, dressing and palette.
    from helpers.masters import master_for, master_key
    master_img, _exact = master_for(setting, style_id, aspect)
    if not (master_img and os.path.exists(master_img)):
        # no master in this style yet: any master of this setting still anchors
        # the place; else we fall back to the description alone
        master_img = next((i for i in (setting.images or {}).values()
                           if i and os.path.exists(i)), None)

    direction = ", ".join(x for x in [shot.angle.strip(), shot.time_of_day.strip()] if x) \
        or shot.name
    anchor_line = ("The attached reference image is this setting's establishing MASTER.  "
                   "Render the SAME place — identical architecture, identical dressing, "
                   "identical palette — but RE-FRAMED as the shot below.\n\n"
                   if master_img else "")

    prompt = f"""Render a comic book background — a reusable SHOT of {interior_or_exterior} setting: "{setting.name}".

{anchor_line}This is an EMPTY SETTING: render the place exactly as described — its
furniture and dressing live in the description — with absolutely NO characters,
people, or creatures.   Compose it in {orient_line} with
generous negative space where characters can later be placed.

# The shot (re-frame the master as this)
* Angle / framing: {shot.angle or '(as the master, reconsidered for this shot)'}
* Time of day / light: {shot.time_of_day or '(as the master)'}
{f"* Note: {shot.description}" if shot.description else ""}

# Setting
{setting.description}

{format_comic_style(style, include_bubble_styles=False, include_character_style=False, heading_level=1)}
"""

    reference_images = ([master_img] if master_img else []) + list(storage.list_uploads(obj=setting))

    locator = generate_object_image(
        wrapper=wrapper,
        obj=setting,
        prompt=prompt,
        reference_images=reference_images,
        aspect_ratio=aspect,
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{setting_id}-{shot_id}-{style_id}-shot",
    )

    # persist onto a FRESH read: the render takes minutes and the author may
    # have kept working on the setting meanwhile
    fresh = storage.read_object(cls=Setting, primary_key=setting.primary_key) or setting
    _mk = master_key(style_id, aspect)
    fshot = next((s for s in (fresh.shots or []) if s.shot_id == shot_id), None)
    if fshot is None:
        return f"Shot '{shot_id}' vanished from '{setting.name}' while rendering."
    fshot.images[_mk] = locator
    if _mk in (fshot.images_stale or []):
        fshot.images_stale = [k for k in fshot.images_stale if k != _mk]
    storage.update_object(data=fresh)
    state.is_dirty = True
    return f"Shot '{shot.name}' of '{setting.name}' rendered in style '{style_id}': {locator}"


# ---------------------------------------------------------------------------
# REFRAME: move + scale an EXISTING master into a different aspect ratio — the
# same painting cropped to fill a new frame, no re-render.
# ---------------------------------------------------------------------------
_REFRAME_DIMS = {"landscape": (1536, 1024), "portrait": (1024, 1536), "square": (1024, 1024)}


def _reframe_crop_box(W: int, H: int, orient: str, z: float, px: float, py: float):
    """The source-pixel crop rectangle (x, y, w, h) for a reframe: at zoom 1 it's
    the largest target-aspect rectangle that fits the source; higher zoom crops
    tighter; pan (px, py in -1..1) slides the rectangle within the source."""
    tw, th = _REFRAME_DIMS[orient]
    tr = tw / th
    if W / H > tr:
        h0 = float(H); w0 = H * tr
    else:
        w0 = float(W); h0 = W / tr
    z = max(1.0, float(z))
    w = w0 / z; h = h0 / z
    x = (W - w) / 2.0 * (1 + float(px))
    y = (H - h) / 2.0 * (1 + float(py))
    return int(round(x)), int(round(y)), int(round(w)), int(round(h))


def _reframe_region(source_img: str, orient: str, z: float, px: float, py: float):
    from PIL import Image
    im = Image.open(source_img).convert("RGB")
    W, H = im.size
    x, y, w, h = _reframe_crop_box(W, H, orient, z, px, py)
    x = max(0, min(x, W - 1)); y = max(0, min(y, H - 1))
    w = max(1, min(w, W - x)); h = max(1, min(h, H - y))
    return im.crop((x, y, x + w, y + h))


def reframe_preview(source_img: str, orient: str, z: float, px: float, py: float,
                    out_path: str, maxside: int = 420) -> str:
    """Write a small preview PNG of the reframed region (for the live dialog)."""
    region = _reframe_region(source_img, orient, z, px, py)
    tw, th = _REFRAME_DIMS[orient]
    from PIL import Image
    scale = min(maxside / tw, maxside / th)
    region = region.resize((max(1, int(tw * scale)), max(1, int(th * scale))), Image.LANCZOS)
    region.save(out_path, "PNG")
    return out_path


def reframe_setting_master(state, series_id: str, setting_id: str, style_id: str,
                           source_img: str, orient: str, z: float, px: float, py: float) -> str | None:
    """Crop the source master to the reframed region, resize to the target
    orientation's dims, and save it as the style's master for that orientation."""
    from io import BytesIO
    from PIL import Image
    from schema import Setting, FrameLayout
    from helpers.masters import master_key
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    if not (source_img and os.path.exists(source_img)):
        return None
    setting = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": setting_id})
    if setting is None:
        return None
    region = _reframe_region(source_img, orient, z, px, py).resize(_REFRAME_DIMS[orient], Image.LANCZOS)
    buf = BytesIO(); region.save(buf, "PNG")
    locator = storage.upload_binary_image(obj=setting, data=buf.getvalue())
    fresh = storage.read_object(cls=Setting, primary_key=setting.primary_key) or setting
    mk = master_key(style_id, FrameLayout(orient))
    fresh.images[mk] = locator
    fresh.images_stale = [k for k in (fresh.images_stale or []) if k != mk]
    storage.update_object(data=fresh)
    state.is_dirty = True
    return locator


@function_tool
async def generate_setting_background(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    setting_id: str,
    style_id: str,
    aspect: Optional[str] = None,
) -> str:
    """
    Render the master background for a setting in a given comic style: the empty
    setting, furnished exactly as described, with NO characters.   The master background is
    stored on the setting keyed by style and is reused as the shared background for
    every panel that takes place there — ink the setting once, reuse it across pages.

    If reference images have been uploaded for the setting, they are used to
    steer the rendering for real-world or previously-established looks.

    Args:
        series_id: The ID of the series the setting belongs to.
        setting_id: The ID of the setting to render.
        style_id: The comic style to render the master background in.

        aspect: The aspect of the board the master is for — 'landscape', 'portrait'
            or 'square'.  Match the panel/cover it will sit behind; defaults to landscape.

    Returns:
        A status message with the locator of the rendered master background.
    """

    return await asyncio.to_thread(_generate_setting_background_sync, wrapper, series_id, setting_id, style_id, aspect)


def _generate_setting_background_sync(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    setting_id: str,
    style_id: str,
    aspect: Optional[str] = None,
) -> str:
    """
    Render the master background for a setting in a given comic style: the empty
    setting, furnished exactly as described, with NO characters.   The master background is
    stored on the setting keyed by style and is reused as the shared background for
    every panel that takes place there — ink the setting once, reuse it across pages.

    If reference images have been uploaded for the setting, they are used to
    steer the rendering for real-world or previously-established looks.

    Args:
        series_id: The ID of the series the setting belongs to.
        setting_id: The ID of the setting to render.
        style_id: The comic style to render the master background in.

        aspect: The aspect of the board the master is for — 'landscape', 'portrait'
            or 'square'.  Match the panel/cover it will sit behind; defaults to landscape.

    Returns:
        A status message with the locator of the rendered master background.
    """
    return generate_setting_background_body(wrapper.context, series_id, setting_id, style_id, aspect)


def render_panel_impl(state: APPState, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str:
    """Implementation of the panel render (see generate_panel_image)."""
    class _W:  # minimal wrapper shim for generate_object_image
        context = state
    return _generate_panel_image_body(_W(), series_id, issue_id, scene_id, panel_id)


@function_tool
async def generate_panel_image(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    issue_id: str,
    scene_id: str,
    panel_id: str,
    takes: int = 1,
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
        takes: How many takes to render (1-4).  More takes = a contact sheet in
            the panel's image grid for the user to choose from (each costs money).

    Returns:
        A status message with the locator of the rendered panel image.
    """

    return await asyncio.to_thread(_generate_panel_image_sync, wrapper, series_id, issue_id, scene_id, panel_id, takes)


def _generate_panel_image_sync(
    wrapper: RunContextWrapper[APPState],
    series_id: str,
    issue_id: str,
    scene_id: str,
    panel_id: str,
    takes: int = 1,
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
        takes: How many takes to render (1-4).  More takes = a contact sheet in
            the panel's image grid for the user to choose from (each costs money).

    Returns:
        A status message with the locator of the rendered panel image.
    """
    takes = max(1, min(int(takes or 1), 4))
    notes = [ _generate_panel_image_body(wrapper, series_id, issue_id, scene_id, panel_id)
              for _ in range(takes) ]
    if takes == 1:
        return notes[0]
    return (f"{takes} takes rendered — they're all in the panel's image grid; the last one is "
            f"selected.  Ask the user to pick a favorite (or which to refine).  " + notes[-1])


def _generate_panel_image_body(wrapper, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str:
    state: APPState = wrapper.context
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

    # THE SHAPE IS READ FRESH: the render matches the page cell the layout
    # gives this panel — restitch first, or an aspect changed since the book
    # last painted would render at a STALE shape (money spent on the wrong
    # frame).  Hand-designed layouts are never touched by this.
    try:
        from helpers.stitcher import remember_stitch
        remember_stitch(storage, series_id, issue_id)
    except Exception as _ex:
        logger.debug(f"pre-render restitch skipped: {_ex}")

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

    # DID THE AUTHOR ROUGH THIS PANEL?  A rough — figures or props laid, a plate
    # dropped — is authoritative: compose from the board.  A BARE board is a
    # FROM-BRIEF render: READ the brief and pull ONLY the reference objects it
    # actually calls for — no rough required, no scene furniture auto-stamped.
    roughed = bool(panel.character_references) or bool(panel.figure_images)
    brief_plan = None
    if not roughed:
        _brief = f"{panel.beat or ''}\n\n{panel.description or ''}".strip()
        if _brief:
            try:
                brief_plan = breakdown_brief(state, series_id, _brief, False)
            except Exception as _bex:
                logger.error(f"brief breakdown for render failed: {_bex}")

    # 1) The setting's master background.  Roughed → the scene's setting (the
    # plate the author works over).  From-brief → ONLY the setting the brief
    # NAMES; a brief that describes no place gets no background at all.
    setting: Setting | None = None
    background_first = False
    _setting_id = (scene.setting_id if roughed
                   else (brief_plan.get('setting_id') if brief_plan else None))
    if _setting_id:
        setting = storage.read_object(cls=Setting, primary_key={"series_id": series_id, "setting_id": _setting_id})
        if setting is not None:
            from helpers.masters import scene_background
            # the scene's chosen SHOT (angle + time of day) wins over the master
            background, _exact = scene_background(setting, scene.style_id, panel.aspect,
                                                  getattr(scene, 'setting_shot_id', None))
            if background and os.path.exists(background):
                reference_images.append(background)
                background_first = True
            else:
                missing.append(f"master background for '{setting.name}' in style '{scene.style_id}' (generate_setting_background)")

    # 2) The cast's styled reference sheets keep the characters on-model.
    # Roughed → the panel's own cast.  From-brief → ONLY the characters the
    # brief NAMES (breakdown), each reconciled to the scene cast for their
    # wardrobe — never the whole scene stamped in.
    cast_info = ""
    char_names: dict[str, str] = {}
    if roughed:
        cast_refs = list(panel.character_references or [])
    else:
        cast_refs = []
        _scene_var = {c.character_id: c.variant_id for c in (getattr(scene, 'cast', None) or [])}
        for _f in ((brief_plan.get('figures') if brief_plan else None) or []):
            _cid = _f.get('character_id')
            if not _cid:
                continue
            _vid = _scene_var.get(_cid)
            if not _vid:   # a character the brief names but the scene never cast
                _vs = list(storage.read_all_objects(CharacterVariant, {
                    "series_id": series_id, "character_id": _cid}))
                _vid = _vs[0].variant_id if _vs else None
            if _vid:
                cast_refs.append(CharacterRef(series_id=series_id, character_id=_cid, variant_id=_vid))
    for ref in cast_refs:
        variant: CharacterVariant = storage.read_object(cls=CharacterVariant, primary_key={
            "series_id": series_id, "character_id": ref.character_id, "variant_id": ref.variant_id})
        if variant is None:
            missing.append(f"variant '{ref.variant_id}' of character '{ref.character_id}'")
            continue
        # the prompt speaks the character's NAME — a raw id reads as
        # gibberish and can get lettered straight into the art
        _c = storage.read_object(cls=CharacterModel, primary_key={
            "series_id": series_id, "character_id": ref.character_id})
        char_names[ref.character_id] = (_c.name if _c is not None
                                        else ref.character_id.replace('-', ' '))
        styled = variant.images.get(scene.style_id)
        if styled and os.path.exists(styled):
            reference_images.append(styled)
        else:
            missing.append(f"styled image of '{ref.character_id}' ({ref.variant_id}) in style '{scene.style_id}' (create_styled_image_for_character_variant)")
        cast_info += format_character_variant(char_names[ref.character_id], variant, 2) + "\n"

    # 2b) THE PROPS ARE PER-PANEL.  Roughed → the props laid on THIS panel's
    # light table (element/* acetates).  From-brief → the standalone props the
    # brief NAMES (breakdown elements), matched to library art.  Never the whole
    # scene's props stamped onto every panel.
    props_info = ""
    _prop_lines = []
    _seen_props = set()
    import re as _re
    from schema import PropAsset as _PropAsset
    from agentic.tools.normalization import normalize_id as _nid
    _assets_by_nid = {_nid(a.name): a for a in storage.read_all_objects(
        _PropAsset, {"series_id": series_id})}

    def _add_prop(_name, _desc, _asset):
        _nmk = (_name or "").strip().lower()
        if not _nmk or _nmk in _seen_props:
            return
        _seen_props.add(_nmk)
        _prop_lines.append(f"* **{_name}**: {_desc}" if _desc else f"* **{_name}**")
        _art = (_asset.images or {}).get(scene.style_id) if _asset is not None else None
        if _art and os.path.exists(_art):
            reference_images.append(_art)
        elif _asset is not None:
            missing.append(f"reference art for prop '{_name}' in style "
                           f"'{scene.style_id}' (generate_prop_reference)")

    if roughed:
        _pblk = panel.figure_blocking or {}
        for _key, _path in sorted((panel.figure_images or {}).items()):
            if not _key.startswith('element/'):
                continue
            if not (_pblk.get(_key) or {}).get('on', 1):
                continue   # the author lifted this prop off the table
            _pid = _key.split('/', 1)[1]
            # library props key as <slug> (a de-duplicated instance as <slug>-2, …)
            _asset = _assets_by_nid.get(_pid) or _assets_by_nid.get(_re.sub(r'-\d+$', '', _pid))
            _name = _asset.name if _asset is not None else _pid.replace('-', ' ')
            _add_prop(_name, (getattr(_asset, 'description', '') or '') if _asset is not None else '', _asset)
    else:
        for _el in ((brief_plan.get('elements') if brief_plan else None) or []):
            _name = (_el.get('name') or '').strip()
            _asset = _assets_by_nid.get(_nid(_name)) if _name else None
            _desc = (_el.get('description')
                     or (getattr(_asset, 'description', '') if _asset is not None else '') or '')
            _add_prop(_name, _desc, _asset)
    props_info = chr(10).join(_prop_lines)

    # 3) Panel-specific uploaded reference images.
    reference_images.extend(storage.list_uploads(obj=panel))

    # Assemble the dialogue/narration script for the letterer, honoring the
    # author's light-table arrangement: positions, tail targets, emphasis,
    # and letters lifted off the table.
    blk = panel.figure_blocking or {}

    def _pct(v):
        return f"{round(float(v))}%"

    script_lines = []
    for pos in ('top', 'bottom'):
        for i, n in enumerate([n for n in panel.narration if n.position.value == pos]):
            b = blk.get(f'caption/{pos}/{i}') or {}
            if not b.get('on', 1):
                continue
            line = f"* **Narration ({pos})**: {n.text}"
            if b:
                line += f"   [box at {_pct(b.get('x', 4))} from left, {_pct(b.get('y', 88))} up from the bottom]"
            script_lines.append(line)
    for i, d in enumerate(panel.dialogue):
        b = blk.get(f'balloon/{i}') or {}
        if not b.get('on', 1):
            continue
        line = f"* **{char_names.get(d.character_id, d.character_id.replace('-', ' '))}** ({d.emphasis.value}): {d.text}"
        if b:
            line += f"   [balloon at {_pct(b.get('x', 50))} from left, {_pct(b.get('y', 70))} up"
            if b.get('tx') is not None:
                line += f"; tail tip at {_pct(b['tx'])} across, {_pct(b.get('ty', 0))} up"
            line += "]"
        script_lines.append(line)
    script = "\n".join(script_lines)

    # The author's figure blocking from the light table.
    table_layout = _table_layout_brief(panel, storage)

    setting_line = ""
    if setting is not None:
        setting_line = f"{'Interior' if setting.interior else 'Exterior'}: {setting.name}" + (f", {scene.time_of_day}" if scene.time_of_day else "")

    # THE ROUGH IS THE PENCILS: when the author blocked acetates on the light
    # table, composite them and hand the inker the actual image to finish.
    rough_ref = _compose_table_rough(storage, panel, scene)
    if rough_ref:
        reference_images.insert(0, rough_ref)
        ref_guidance = """The FIRST reference image is the author's ROUGH of this panel — the exact
composition they assembled on the light table.   It is AUTHORITATIVE and OVERRIDES the
written description below for composition: draw EXACTLY the figures and elements it shows,
each at its position, scale and facing, and NOTHING it does not show.   Do not add,
remove, move, or re-stage anything to match the beat or panel description — those are for
identity, costume and surface detail ONLY, never for what appears or where.   Finish and
ink the rough in the style below.   The remaining references show the setting and the
on-model cast."""
    elif not roughed:
        # FROM-BRIEF: the panel description IS the exact visual brief.
        ref_guidance = (
            "The Panel description below is the EXACT visual brief — draw precisely what it "
            "specifies and NOTHING it excludes. If it says no background, no characters, or "
            "empty space, then there are none; let the negative space carry it. The Beat is "
            "narrative intent (why this moment matters), NOT a license to add characters, "
            "objects, or scenery the description does not call for. Render one single panel — "
            "never a multi-panel page."
            + (" The reference images show the setting and the on-model cast the brief names; "
               "keep them strictly on-model." if reference_images else ""))
    elif background_first:
        ref_guidance = """The FIRST reference image is the setting's master background: use it
as the panel's setting — same architecture, same props, same palette — reframed as
the panel requires.   The character reference sheets show exactly how each character
must look; keep them strictly on-model."""
    else:
        ref_guidance = """The character reference sheets show exactly how each character
must look; keep them strictly on-model."""

    prompt = f"""Render a single comic book panel.  Aspect/orientation: {panel.aspect.value}.
{f"Setting: {setting_line}" if setting_line else ""}
{f"Mood: {scene.mood}" if scene.mood else ""}

{ref_guidance}

# Beat
{panel.beat}

# Panel description
{panel.description}

{f"# Scene blocking{chr(10)}{scene.blocking}" if (scene.blocking and roughed) else ""}

# Characters in panel
{cast_info if cast_info else "* (no characters in panel)"}

{f"# Props on this panel (draw them as their reference art shows){chr(10)}{props_info}" if props_info else ""}

{f"# Layout — the author BLOCKED this on the light table; honor positions and depths{chr(10)}{table_layout}{chr(10)}" if table_layout else ""}
# Lettering (render these balloons/boxes per the style's bubble styles;
# bracketed placements are the author's — put each balloon and tail there)
{script if script else "* (silent panel — no lettering)"}

# One hand, one finish
Redraw EVERY element the panel calls for — whatever setting, characters, and props appear —
in ONE unified hand: the same line weight, the same level of detail and shading, the same
palette and finish, as if a single artist inked the whole panel in one pass.   The
reference images fix identity, placement and composition ONLY — never copy a reference at
its own resolution or level of finish.   In particular the setting/background must not read
as more photographic or more finely rendered than the figures and props (or the reverse):
flatten everything to the single style below so nothing looks pasted in from another source.

{format_comic_style(style, heading_level=1)}
"""

    from helpers.stitcher import laid_aspect as _laid_aspect
    locator = generate_object_image(
        wrapper=wrapper,
        obj=panel,
        prompt=prompt,
        reference_images=reference_images,
        # render at the shape the PAGE gave this panel (the flow may have flexed
        # it), so the art fills its cell instead of being letterboxed/cropped
        aspect_ratio=_laid_aspect(storage, panel),
        image_quality=IMAGE_QUALITY.HIGH,
        name=f"{panel_id}-render",
    )

    # persist onto a FRESH read: the render takes minutes and the author may
    # have kept working on the panel meanwhile — never write back a stale copy
    fresh = storage.read_object(cls=Panel, primary_key=panel.primary_key) or panel
    fresh.image = locator
    storage.update_object(data=fresh)
    state.is_dirty = True

    note = ""
    if missing:
        note = "  NOTE: rendered without: " + "; ".join(missing) + ".  Generate those references and re-render for better consistency."
    return f"Panel {panel.panel_number} rendered: {locator}.{note}"


@function_tool
async def export_issue_pdf(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
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

    return await asyncio.to_thread(_export_issue_pdf_sync, wrapper, series_id, issue_id)


def _export_issue_pdf_sync(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

    issue: Issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    if issue is None:
        return f"Issue '{issue_id}' not found in series '{series_id}'."

    _refresh_machine_layout(storage, series_id, issue_id)
    from helpers.binder import export_basename
    from helpers.binder import export_basename
    output = os.path.join(str(storage.base_path), "series", series_id, "issues", issue_id,
                          "exports", f"{export_basename(storage, series_id, issue_id)}.pdf")
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
    url = "/" + output.replace(os.sep, "/")
    return (f"Issue '{issue.name}' bound to {output} ({page_count} pages).  "
            f"Give the author this link: [Download the bound PDF]({url}){note}")


def _refresh_machine_layout(storage, series_id: str, issue_id: str) -> None:
    """ONE HOME: compose_book refreshes the drifted layout itself now — this
    thin alias stays for its callers."""
    from helpers.binder import refresh_machine_layout
    refresh_machine_layout(storage, series_id, issue_id)


@function_tool
async def export_issue_cbz(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    Bind the issue into a CBZ comic book archive — the format comic reader
    apps open natively.   Same sheets as the PDF: covers, indicia, designed
    pages with folios.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the issue to export.

    Returns:
        A status message with a download link, the page count, and anything
        still missing from a complete issue.
    """

    return await asyncio.to_thread(_export_issue_cbz_sync, wrapper, series_id, issue_id)


def _export_issue_cbz_sync(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    Bind the issue into a CBZ comic book archive — the format comic reader
    apps open natively.   Same sheets as the PDF: covers, indicia, designed
    pages with folios.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the issue to export.

    Returns:
        A status message with a download link, the page count, and anything
        still missing from a complete issue.
    """
    from helpers.binder import bind_issue_cbz
    state: APPState = wrapper.context
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

    issue: Issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    if issue is None:
        return f"Issue '{issue_id}' not found in series '{series_id}'."

    _refresh_machine_layout(storage, series_id, issue_id)
    from helpers.binder import export_basename
    output = os.path.join(str(storage.base_path), "series", series_id, "issues", issue_id, "exports", f"{export_basename(storage, series_id, issue_id)}.cbz")
    try:
        page_count, missing = bind_issue_cbz(storage, series_id, issue_id, output)
    except Exception as e:
        logger.error(f"Failed to bind issue {issue_id} to CBZ: {e}")
        return f"Failed to bind the issue: {e}"

    if page_count == 0:
        return "Nothing to bind yet: no rendered covers or panels.  " + "; ".join(missing)
    note = ""
    if missing:
        note = f"  Still missing for a complete issue: " + "; ".join(missing)
    state.is_dirty = True
    url = "/" + output.replace(os.sep, "/")
    return (f"Issue '{issue.name}' bound to {output} ({page_count} pages).  "
            f"Give the author this link: [Download the CBZ]({url}){note}")


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
    # ONE PRODUCTION LEDGER: this tool, the colophon, the masthead badge
    # and the Editor's opener all quote helpers/ledger.py — one truth
    from helpers.ledger import issue_ledger
    state: APPState = wrapper.context
    # THE SERIES NAMES ITS HOUSE: a status ask can point at any series on
    # the wall — the ledger must read the house that HOLDS it, never the
    # one the author happens to be standing in (a wrong mount reads an
    # empty issue and reports lies: 'no script', 'no cover')
    from storage import registry as _reg
    storage: GenericStorage = _reg.storage_for_key(
        {"series_id": series_id}, state.storage)
    ledger = issue_ledger(storage, series_id, issue_id)

    report = [("[ok] " if line.ok else "[--] ") + line.text for line in ledger.lines]
    todos = [item for line in ledger.todos for item in line.items]
    if todos:
        report.append("To complete the issue:")
        report += [f"  - {t}" for t in todos]
    if ledger.complete:
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
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

    # panel_id -> scene_id map for the whole issue
    scene_of: dict[str, str] = {}
    for scene in storage.read_all_objects(SceneModel, {"series_id": series_id, "issue_id": issue_id}):
        for p in storage.read_all_objects(Panel, {"series_id": series_id, "issue_id": issue_id, "scene_id": scene.scene_id}):
            scene_of[p.panel_id] = scene.scene_id

    unknown = [pid for page in pages for row in page for pid in row if pid not in scene_of]
    if unknown:
        return f"Unknown panel id(s): {', '.join(unknown[:5])}.  Check the panel list (read_all_panels per scene)."
    for pi, page_rows in enumerate(pages, start=1):
        if not page_rows:
            return f"Page {pi} has no rows — every page needs at least one row of panels."
        for ri, row in enumerate(page_rows, start=1):
            if not row:
                return f"Page {pi} row {ri} has no panels — remove the empty row or fill it."

    # snapshot the outgoing layout so it can be brought back (delete+recreate
    # under the same ids blocks trash restore — a wastebasket JSON does not)
    import json as _json
    from uuid import uuid4 as _uuid4
    old_pages = storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id},
                                         order_by="page_number")
    if old_pages:
        try:
            snap_dir = os.path.join(str(storage.base_path), "series", series_id, "issues", issue_id)
            os.makedirs(snap_dir, exist_ok=True)
            snap = os.path.join(snap_dir, f".trash--layout--{_uuid4().hex[:6]}.json")
            with open(snap, "w") as fh:
                _json.dump([p.model_dump() for p in old_pages], fh, indent=1)
            logger.info(f"page-layout snapshot: {snap}")
        except Exception as ex:
            logger.warning(f"layout snapshot skipped: {ex}")
    for old_page in old_pages:
        storage.delete_object(cls=Page, primary_key=old_page.primary_key)

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


@function_tool
async def stitch_issue_pages(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    STITCH THE BOOK: lay every scene's panels, in reading order, onto pages
    automatically — the studio's banding algorithm on the printed page's
    6x10 unit grid (portrait panels lead tall bands beside stacked landscape
    panels; pairs share rows; a lone wide panel becomes a splash).   Replaces
    any existing page layout (the old one is snapshotted).   Use this for a
    complete first layout in one step; layout_issue_pages remains the tool
    for hand-designed page grids.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.

    Returns:
        A status message summarizing the stitched book.
    """

    return await asyncio.to_thread(_stitch_issue_pages_sync, wrapper, series_id, issue_id)


def _stitch_issue_pages_sync(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str) -> str:
    """
    STITCH THE BOOK: lay every scene's panels, in reading order, onto pages
    automatically — the studio's banding algorithm on the printed page's
    6x10 unit grid (portrait panels lead tall bands beside stacked landscape
    panels; pairs share rows; a lone wide panel becomes a splash).   Replaces
    any existing page layout (the old one is snapshotted).   Use this for a
    complete first layout in one step; layout_issue_pages remains the tool
    for hand-designed page grids.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.

    Returns:
        A status message summarizing the stitched book.
    """
    from helpers.stitcher import apply_stitch
    state: APPState = wrapper.context
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    new_pages, _old = apply_stitch(storage, series_id, issue_id)
    if not new_pages:
        return "Nothing to stitch yet — break the scenes into panels first."
    placed = sum(len(p.cells) for p in new_pages)
    state.is_dirty = True
    return (f"Stitched the whole issue onto {len(new_pages)} page(s) — all {placed} panels "
            f"placed in reading order.  The author can rearrange any page from the issue view.")


def _render_asset_reference(wrapper, cls, key, series_id, asset_id, style_id, subject_line, guidance,
                            aspect=FrameLayout.SQUARE):
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
        aspect_ratio=aspect, image_quality=IMAGE_QUALITY.HIGH,
        name=f"{asset_id}-{style_id}-reference",
        background="transparent")
    # persist onto a FRESH read — renders take minutes
    fresh = storage.read_object(cls, {"series_id": series_id, key: asset_id}) or asset
    fresh.images[style_id] = locator
    storage.update_object(data=fresh)
    state.is_dirty = True
    return f"Reference art for '{asset.name}' rendered in style '{style_id}': {locator}"


def render_outfit_reference_body(state, series_id: str, outfit_id: str, style_id: str) -> str:
    """Render an outfit's reference art from its exemplar — GUI/callable."""
    class _W:
        context = state
    return _generate_outfit_reference_sync(_W(), series_id, outfit_id, style_id)


def render_prop_reference_body(state, series_id: str, prop_id: str, style_id: str) -> str:
    """Render a prop's reference art — GUI-callable (background job)."""
    from schema import PropAsset

    class _W:
        context = state
    return _render_asset_reference(
        _W(), PropAsset, "prop_id", series_id, prop_id, style_id,
        "a single prop",
        "Show ONLY the prop — no characters, no scene, no ground — in a clear three-quarter "
        "view on a COMPLETELY TRANSPARENT background: a cut-out acetate to be layered onto boards.")


@function_tool
async def generate_prop_reference(wrapper: RunContextWrapper[APPState], series_id: str, prop_id: str, style_id: str) -> str:
    """
    Render a prop's reference art in a comic style: the prop alone on a neutral
    background, from a clear three-quarter view.   Stored on the prop keyed by
    style; composited into settings, variant sheets, and panels that use it.

    Args:
        series_id: The series that owns the prop.
        prop_id: The prop to render.
        style_id: The comic style to render in.
    """

    return await asyncio.to_thread(_generate_prop_reference_sync, wrapper, series_id, prop_id, style_id)


def _generate_prop_reference_sync(wrapper: RunContextWrapper[APPState], series_id: str, prop_id: str, style_id: str) -> str:
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
        "Show ONLY the prop — no characters, no scene, no ground — in a clear three-quarter "
        "view on a COMPLETELY TRANSPARENT background: a cut-out acetate to be layered onto boards.")


@function_tool
async def generate_outfit_reference(wrapper: RunContextWrapper[APPState], series_id: str, outfit_id: str, style_id: str) -> str:
    """
    Render an outfit's reference art in a comic style: the attire presented on
    a neutral display form (no face, no identity), front and back.   Stored on
    the outfit keyed by style; composited into variant reference sheets.

    Args:
        series_id: The series that owns the outfit.
        outfit_id: The outfit to render.
        style_id: The comic style to render in.
    """

    return await asyncio.to_thread(_generate_outfit_reference_sync, wrapper, series_id, outfit_id, style_id)


def _generate_outfit_reference_sync(wrapper: RunContextWrapper[APPState], series_id: str, outfit_id: str, style_id: str) -> str:
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
    # WARDROBE PRINTS LANDSCAPE: a wardrobe turnaround is three angles side by
    # side, so its reference art is always a 3x2 landscape plate
    return _render_asset_reference(
        wrapper, Outfit, "outfit_id", series_id, outfit_id, style_id,
        "an outfit (wardrobe)", aspect=FrameLayout.LANDSCAPE,
        guidance="Present the attire on a TAILOR'S MANNEQUIN (a neutral gray dress-form — "
        "NO character identity, no face, no hair) as a WARDROBE TURNAROUND: "
        "three angles side by side — front, three-quarter, and back — the same "
        "mannequin and garment at the same scale in each, on a plain neutral "
        "background, like a costume shop's reference sheet.")


@function_tool
def render_missing_panels(wrapper: RunContextWrapper[APPState], series_id: str, issue_id: str,
                          scene_id: Optional[str] = None, confirm: bool = False) -> str:
    """
    Render every unrendered panel of a scene (or the whole issue) in the
    BACKGROUND: the conversation stays open, each finished panel posts a
    receipt into the chat, and a summary lands at the end.

    Costs real money per image, so the first call returns a quote; call again
    with confirm=true after the user agrees.

    Args:
        series_id: The series.
        issue_id: The issue.
        scene_id: Limit to one scene (omit for the whole issue).
        confirm: Set true only after the user has approved the quoted batch.

    Returns:
        A quote (confirm=false) or a started-in-background message.
    """
    from functools import partial
    from helpers.render_queue import enqueue_renders
    state: APPState = wrapper.context
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

    scenes = ([storage.read_object(SceneModel, {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})]
              if scene_id else
              storage.read_all_objects(SceneModel, {"series_id": series_id, "issue_id": issue_id}, order_by="scene_number"))
    scenes = [s for s in scenes if s is not None]
    if not scenes:
        return "No such scene(s) found."

    jobs = []
    for scene in scenes:
        for p in storage.read_all_objects(Panel, {"series_id": series_id, "issue_id": issue_id, "scene_id": scene.scene_id}, order_by="panel_number"):
            if not (p.image and os.path.exists(p.image)):
                jobs.append((f"Panel {p.panel_number} of '{scene.name}'",
                             partial(render_panel_impl, state, series_id, issue_id, scene.scene_id, p.panel_id)))

    if not jobs:
        return "Nothing to render — every panel already has artwork."
    if not confirm:
        est = len(jobs) * 0.20
        return (f"{len(jobs)} panel(s) need rendering.  Estimated cost ≈ ${est:.2f} "
                f"(high-quality images).  Ask the user to confirm, then call again with confirm=true.")

    enqueue_renders(state, jobs, role="the Penciller")
    return (f"Started rendering {len(jobs)} panel(s) in the background — receipts will land in the "
            f"chat as each one finishes.  The conversation stays open meanwhile.")


# ---------------------------------------------------------------------------
# FIGURE ACETATES: a posed, scene-scaled cut-out of one character for one
# panel — the figure layer the light table stacks over the background.
# ---------------------------------------------------------------------------
def generate_figure_acetate_body(state, series_id: str, issue_id: str, scene_id: str | None = None,
                                 panel_id: str | None = None, character_id: str = "", variant_id: str = "",
                                 pose_direction: str | None = None,
                                 cover_id: str | None = None,
                                 insert_id: str | None = None) -> str:
    """Render a transparent posed figure for a board (a panel, a cover, or a
    full-page insert) and remember it there.  Callable directly from the GUI
    (background job) or via the tool."""
    from storage.filepath import obj_to_imagepath
    from helpers.generator import invoke_edit_image_api

    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    if cover_id:
        panel = storage.read_object(cls=Cover, primary_key={
            "series_id": series_id, "issue_id": issue_id, "cover_id": cover_id})
        if panel is None:
            return f"Cover '{cover_id}' not found."
        scene = None
    elif insert_id:
        from schema import Insert as _Insert
        panel = storage.read_object(cls=_Insert, primary_key={
            "series_id": series_id, "issue_id": issue_id, "insert_id": insert_id})
        if panel is None:
            return f"Insert '{insert_id}' not found."
        scene = None
    else:
        panel = storage.read_object(cls=Panel, primary_key={
            "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id})
        if panel is None:
            return f"Panel '{panel_id}' not found."
        scene = storage.read_object(cls=SceneModel, primary_key={
            "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
    # a cover is its own scene: style comes from the scene, or the board itself
    style_id = getattr(scene if scene is not None else panel, 'style_id', None)
    variant: CharacterVariant = storage.read_object(cls=CharacterVariant, primary_key={
        "series_id": series_id, "character_id": character_id, "variant_id": variant_id})
    if variant is None:
        return f"Variant '{variant_id}' of '{character_id}' not found."

    # the best on-model reference we have: styled sheet, else any sheet —
    # and if we settle for another style's sheet, we SAY so
    sheet = variant.images.get(style_id) if (style_id and variant.images) else None
    style_fallback = None
    if not (sheet and os.path.exists(sheet)):
        sheet = storage.find_variant_image(series_id=series_id, character_id=character_id, variant_id=variant_id)
        if sheet and style_id:
            worn = next((sid for sid, pth in (variant.images or {}).items() if pth == sheet), None)
            style_fallback = (f"NOTE: no reference sheet in this scene's style ('{style_id}') — "
                              f"the figure was posed from the "
                              f"{'sheet in style ' + repr(worn) if worn else 'unstyled sheet'} instead.  "
                              f"Ink their sheet in this style (create_styled_image_for_character_variant) "
                              f"and re-pose for an on-style figure.")
    if not (sheet and os.path.exists(sheet)):
        return (f"No reference art for '{character_id}' ({variant_id}) yet — "
                f"create the variant's reference sheet first.")

    # the prompt speaks the character's NAME — a raw id reads as gibberish
    # and the model then follows the moment text instead of the sheet
    _char = storage.read_object(cls=CharacterModel, primary_key={
        "series_id": series_id, "character_id": character_id})
    char_name = (_char.name if _char is not None else character_id).replace('-', ' ')
    if pose_direction:
        pose_ask = f"POSE (follow this exactly): {pose_direction}"
    else:
        pose_ask = (f"POSE the figure for this moment: {getattr(panel, 'beat', None) or panel.description}"
                    + (f"  Blocking: {scene.blocking}" if scene is not None and scene.blocking else ""))
    pose_ask += (f"\n\nIf the moment above mentions OTHER characters, they are context "
                 f"only — do NOT draw them.  Draw {char_name} and nobody else.")

    prompt = f"""The attached reference sheet shows {char_name}.
Draw THIS character — identical face, identical costume, identical colors,
identical proportions, same ink and palette as the sheet — in ONE new pose.

{pose_ask}

Render a single FULL-BODY figure, head to toe, feet at the bottom edge, on a
COMPLETELY TRANSPARENT background.  No scenery, no ground, no frame, no text,
no speech balloons, no turnaround strip — ONE figure only, posed as directed.
This is a cut-out acetate to be layered over a background."""
    # A pose acetate is a spatial guide the final ink redraws, and identity is
    # anchored twice over (input_fidelity holds the sheet here, and the final
    # render gets the styled sheet directly) — but LOW read too rough on the
    # table, so poses ink at MEDIUM: legible enough to block by.
    image_bytes = invoke_edit_image_api(
        prompt,
        reference_images=[sheet],
        size="1024x1536",
        quality=IMAGE_QUALITY.MEDIUM,
        background="transparent",
        input_fidelity="high",
    )

    from uuid import uuid4
    images_dir = obj_to_imagepath(obj=panel, base_path=storage.base_path)
    figures_dir = os.path.join(os.path.dirname(images_dir), "figures")
    os.makedirs(figures_dir, exist_ok=True)
    # unique filename per pose: re-poses never collide with a cached URL
    filepath = os.path.join(figures_dir, f"{character_id}--{variant_id}--{uuid4().hex[:8]}.png")
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    # persist onto a FRESH read of the board (panel or cover): the pose takes
    # a while and the author kept arranging the table meanwhile
    fresh = storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel
    fresh.figure_images[f"{character_id}/{variant_id}"] = filepath
    storage.update_object(data=fresh)
    state.is_dirty = True
    return (f"Posed figure acetate for {character_id} ({variant_id}): {filepath}"
            + (f"\n{style_fallback}" if style_fallback else ""))


def pose_element_acetate_body(state, series_id: str, issue_id: str, key: str,
                              pose_direction: str | None = None,
                              scene_id: str | None = None, panel_id: str | None = None,
                              cover_id: str | None = None, insert_id: str | None = None,
                              style_id: str | None = None) -> str:
    """POSE A PROP: re-render an element cut-out (a prop, an object) in a new
    orientation or state as a transparent acetate — the prop twin of posing a
    figure.  Sources from the linked prop asset's on-model reference art when the
    element names one (so a re-pose never drifts off a prior pose), else from the
    element's current image.

    Like a figure pose, this is a spatial guide the final ink redraws — inked at
    MEDIUM (LOW read too rough to block by)."""
    from helpers.generator import invoke_edit_image_api
    from storage.filepath import obj_to_imagepath
    from agentic.tools.normalization import normalize_id
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

    if cover_id:
        board = storage.read_object(cls=Cover, primary_key={
            "series_id": series_id, "issue_id": issue_id, "cover_id": cover_id})
    elif insert_id:
        from schema import Insert as _Insert
        board = storage.read_object(cls=_Insert, primary_key={
            "series_id": series_id, "issue_id": issue_id, "insert_id": insert_id})
    else:
        board = storage.read_object(cls=Panel, primary_key={
            "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id})
    if board is None:
        return "Board not found for posing the element."

    name = (key.split('/', 1)[1].replace('-', ' ') if key.startswith('element/') else key)
    current = (board.figure_images or {}).get(key)

    # THE ON-MODEL SOURCE: a prop asset whose slug matches this element, so a
    # re-pose always renders from the clean reference art, never off a prior
    # (possibly drifted) pose.  Fall back to the element's current image.
    source = None
    if key.startswith('element/'):
        import re as _re
        slug = _re.sub(r'-\d+$', '', key.split('/', 1)[1])
        from schema import PropAsset as _PA
        for pa in storage.read_all_objects(_PA, {"series_id": series_id}):
            if normalize_id(pa.name) == slug:
                art = (pa.images or {}).get(style_id) if style_id else None
                art = art or next((i for i in (pa.images or {}).values()
                                   if i and os.path.exists(i)), None)
                if art and os.path.exists(art):
                    source = art
                break
    if not (source and os.path.exists(source)):
        source = current if (current and os.path.exists(current)) else None
    if not (source and os.path.exists(source)):
        return f"No art to pose for '{name}' yet — lay the prop's reference first."

    orient = (pose_direction or "").strip() or "shown at a natural three-quarter angle"
    prompt = f"""The attached image shows {name}.
Draw THIS exact object — identical design, identical materials, identical
colors, identical wear and detailing as the reference — in ONE new orientation.

ORIENTATION / STATE (follow exactly): {orient}

Render the SINGLE object only, on a COMPLETELY TRANSPARENT background.  No
scenery, no ground, no cast shadow, no frame, no text — just the object, posed
as directed.  This is a cut-out acetate to be layered over a background."""
    image_bytes = invoke_edit_image_api(
        prompt, reference_images=[source], size="1024x1024",
        quality=IMAGE_QUALITY.MEDIUM, background="transparent", input_fidelity="high")

    from uuid import uuid4
    images_dir = obj_to_imagepath(obj=board, base_path=storage.base_path)
    figures_dir = os.path.join(os.path.dirname(images_dir), "figures")
    os.makedirs(figures_dir, exist_ok=True)
    slug2 = (key.split('/', 1)[1] if key.startswith('element/') else 'element')
    filepath = os.path.join(figures_dir, f"element--{slug2}--{uuid4().hex[:8]}.png")
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    fresh = storage.read_object(cls=type(board), primary_key=board.primary_key) or board
    fresh.figure_images[key] = filepath
    storage.update_object(data=fresh)
    state.is_dirty = True
    return f"Posed element acetate for {name}: {filepath}"


def dress_setting_acetate_body(state, series_id: str, issue_id: str,
                               direction: str | None = None,
                               scene_id: str | None = None, panel_id: str | None = None,
                               cover_id: str | None = None, insert_id: str | None = None,
                               style_id: str | None = None) -> str:
    """DRESS THE SETTING: re-render the board's background plate under new light,
    time of day, weather, or camera angle — the setting twin of posing a figure or
    a prop.  Same place, new dressing; lands back on the board's background/plate.

    Like a pose, this is a spatial guide the final ink redraws — inked at MEDIUM."""
    from helpers.generator import invoke_edit_image_api
    from storage.filepath import obj_to_imagepath
    from helpers.stitcher import laid_aspect as _laid_aspect
    from schema import SceneModel as _Scene
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)

    if cover_id:
        board = storage.read_object(cls=Cover, primary_key={
            "series_id": series_id, "issue_id": issue_id, "cover_id": cover_id})
    elif insert_id:
        from schema import Insert as _Insert
        board = storage.read_object(cls=_Insert, primary_key={
            "series_id": series_id, "issue_id": issue_id, "insert_id": insert_id})
    else:
        board = storage.read_object(cls=Panel, primary_key={
            "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id})
    if board is None:
        return "Board not found for dressing the setting."

    # the scene owns the setting/style (a cover or insert is its own scene)
    scene = (storage.read_object(cls=_Scene, primary_key={
        "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
        if (scene_id and not (cover_id or insert_id)) else None)
    owner = scene if scene is not None else board
    _style = style_id or getattr(owner, 'style_id', None) or 'vintage-four-color'
    style: ComicStyle = storage.read_object(cls=ComicStyle, primary_key={"style_id": _style})

    # SOURCE: the plate already on the table (a re-dress builds on it), else the
    # scene's setting master
    source = (board.figure_images or {}).get('background/plate')
    if not (source and os.path.exists(source)):
        sid = getattr(owner, 'setting_id', None)
        if sid:
            setting = storage.read_object(cls=Setting, primary_key={
                "series_id": series_id, "setting_id": sid})
            if setting is not None:
                from helpers.masters import scene_background
                cand, _ = scene_background(setting, _style, getattr(board, 'aspect', 'landscape'),
                                           getattr(owner, 'setting_shot_id', None))
                source = cand
    if not (source and os.path.exists(source)):
        return "No background to dress — lay a setting on the table first."

    aspect = _laid_aspect(storage, board) if hasattr(board, 'panel_id') else board.aspect
    cond = (direction or "").strip() or "the same light and time of day, a touch more atmosphere"
    style_block = format_comic_style(style, include_bubble_styles=False,
                                     include_character_style=False, heading_level=1) if style else ""
    prompt = f"""The attached image is the master background of a comic setting.
Re-render THIS exact place — same architecture, same furniture and dressing, same
layout and palette identity — under new conditions.

CONDITIONS (follow exactly): {cond}

Keep it an EMPTY setting: the same furniture and dressing, but NO characters, people,
or creatures, with generous negative space where figures are later placed.  A full-frame
background — no transparency, no frame, no text — in the style below.

{style_block}"""
    image_bytes = invoke_edit_image_api(
        prompt, reference_images=[source], size=frame_layout_to_dims(aspect),
        quality=IMAGE_QUALITY.MEDIUM, input_fidelity="high")

    from uuid import uuid4
    images_dir = obj_to_imagepath(obj=board, base_path=storage.base_path)
    figures_dir = os.path.join(os.path.dirname(images_dir), "figures")
    os.makedirs(figures_dir, exist_ok=True)
    filepath = os.path.join(figures_dir, f"plate--dressed--{uuid4().hex[:8]}.png")
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    fresh = storage.read_object(cls=type(board), primary_key=board.primary_key) or board
    fresh.figure_images['background/plate'] = filepath
    # keep its place and scale if the author set one; else it lands full-frame,
    # and a fresh dressing always shows (clear any stale hide flag)
    fresh.figure_blocking.setdefault('background/plate', {"x": 50, "y": 0, "h": 100, "z": -9})
    fresh.figure_blocking.pop('background', None)
    storage.update_object(data=fresh)
    state.is_dirty = True
    return f"Dressed the setting for the board: {filepath}"


@function_tool
async def generate_figure_acetate(wrapper: RunContextWrapper, series_id: str, issue_id: str,
                            scene_id: str, panel_id: str, character_id: str, variant_id: str,
                            pose_direction: Optional[str] = None) -> str:
    """
    Render a POSED FIGURE ACETATE for one character in one panel: a full-body,
    transparent-background cut-out of the character posed for this panel's
    moment, scaled for layering over the setting's master background on the
    light table.   Use after casting a character into the panel, or to re-pose
    a figure when the beat/blocking changes.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the issue.
        scene_id: The ID of the scene the panel belongs to.
        panel_id: The ID of the panel.
        character_id: The character to pose.
        variant_id: The variant (wardrobe) they wear.
        pose_direction: Optional explicit description of the pose/expression/action,
            e.g. from the user; followed exactly when given.

    Returns:
        A status message with the acetate's locator.
    """

    return await asyncio.to_thread(_generate_figure_acetate_sync, wrapper, series_id, issue_id, scene_id, panel_id, character_id, variant_id, pose_direction)


def _generate_figure_acetate_sync(wrapper: RunContextWrapper, series_id: str, issue_id: str,
                            scene_id: str, panel_id: str, character_id: str, variant_id: str,
                            pose_direction: Optional[str] = None) -> str:
    """
    Render a POSED FIGURE ACETATE for one character in one panel: a full-body,
    transparent-background cut-out of the character posed for this panel's
    moment, scaled for layering over the setting's master background on the
    light table.   Use after casting a character into the panel, or to re-pose
    a figure when the beat/blocking changes.

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the issue.
        scene_id: The ID of the scene the panel belongs to.
        panel_id: The ID of the panel.
        character_id: The character to pose.
        variant_id: The variant (wardrobe) they wear.
        pose_direction: Optional explicit description of the pose/expression/action,
            e.g. from the user; followed exactly when given.

    Returns:
        A status message with the acetate's locator.
    """
    return generate_figure_acetate_body(wrapper.context, series_id, issue_id, scene_id,
                                        panel_id, character_id, variant_id, pose_direction)


# ---------------------------------------------------------------------------
# LAYER SPLITTING: decompose a layer into its constituent elements.  A vision
# pass RECOGNIZES the entities and their bounds; each chosen entity is lifted
# onto its own transparent acetate placed at its recognized position; the base
# is repainted with everything lifted removed — revealing what was beneath
# (split a figure and its props/wardrobe come off, revealing the character).
# ---------------------------------------------------------------------------
def recognize_layer_entities(image_path: str, max_entities: int = 8,
                             cast: list[dict] | None = None) -> list[dict]:
    """Vision pass: name the distinct liftable entities in a layer image and
    their bounding boxes (percent coordinates).  When the series cast is
    given ([{character_id, name}]), each entity is also matched against it.
    Returns [{name, box, beneath, character_id}]."""
    import base64
    import json as _json
    import re as _re

    import openai
    openai.api_key = os.getenv('OPENAI_API_KEY')
    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    mime = 'image/png' if image_path.lower().endswith('.png') else 'image/jpeg'
    cast_block = ""
    if cast:
        roster = "\n".join(f'  - id "{c["character_id"]}": {c.get("name") or c["character_id"]}'
                           + (f' — {c["notes"][:160]}' if c.get("notes") else '')
                           for c in cast[:20])
        cast_block = f"""

KNOWN CAST — characters from this comic who may appear in the image:
{roster}
If an entity IS one of these characters (a person, creature or figure that
matches), use the character's proper name as the entity name and set its
"character_id" to the matching id.   Otherwise set "character_id" to null."""
    prompt = f"""Identify the distinct visual entities in this image that could be lifted
onto separate layers: people/characters, props, furniture, signage,
garments/wardrobe pieces, carried objects, creatures, vehicles, distinct
scenery pieces.   Skip the overall background itself and skip anything cut
off at the image edge unless it is prominent.   At most {max_entities}
entities, most prominent first.{cast_block}

Respond with STRICT JSON only, no prose:
{{"entities": [{{"name": "<2-4 word name>",
                "box": {{"x": <left %>, "y": <top %>, "w": <width %>, "h": <height %>}},
                "beneath": "<one phrase: what is revealed when it is removed>",
                "character_id": <matching cast id or null>}}]}}"""
    resp = openai.chat.completions.create(
        model=os.getenv('VISION_MODEL', 'gpt-5.2'),
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]}],
    )
    text = resp.choices[0].message.content or ""
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if not m:
        return []
    try:
        data = _json.loads(m.group(0))
        known = {c["character_id"] for c in (cast or [])}
        out = []
        for e in data.get("entities", [])[:max_entities]:
            if e.get("name"):
                cid = e.get("character_id")
                out.append({"name": str(e["name"]), "box": e.get("box") or {},
                            "beneath": e.get("beneath", ""),
                            "character_id": cid if cid in known else None})
        return out
    except Exception as ex:
        logger.error(f"entity recognition parse failed: {ex}")
        return []


def breakdown_brief(state, series_id: str, description: str, is_cover: bool) -> dict | None:
    """Break a written board brief into LIGHT TABLE acetates: which setting,
    which cast figures (with pose directions lifted from the brief), which
    standalone elements deserve their own acetate, and whether the masthead
    is called for.  Text-only LLM pass; strict JSON; matches only KNOWN ids."""
    import json as _json
    import re as _re

    import openai
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    roster = series_cast_roster(storage, series_id)
    settings = [{"setting_id": s.setting_id, "name": s.name}
                for s in storage.read_all_objects(Setting, primary_key={"series_id": series_id})]
    openai.api_key = os.getenv('OPENAI_API_KEY')
    roster_txt = "\n".join(f'- id "{c["character_id"]}": {c.get("name")}' for c in roster[:30])
    settings_txt = "\n".join(f'- id "{s["setting_id"]}": {s["name"]}' for s in settings[:30])
    prompt = f"""Break this comic {'cover' if is_cover else 'panel'} brief into LIGHT TABLE acetates.

BRIEF:
{description}

KNOWN CAST (figures may ONLY come from these ids):
{roster_txt or '- (none)'}

KNOWN SETTINGS (match the place to one of these when it fits):
{settings_txt or '- (none)'}

Respond with STRICT JSON only, no prose:
{{"setting_id": <matching known setting id, or null>,
  "new_setting": {{"name": "<2-5 words>", "description": "<visual description>", "interior": <bool>}} or null,
  "figures": [{{"character_id": "<known cast id>", "pose": "<1-2 sentences: pose, expression, action, exactly as the brief directs>"}}],
  "elements": [{{"name": "<2-4 words>", "description": "<visual description from the brief>"}}],
  "wants_masthead": <true when the brief calls for the series title lettering>}}

Rules: new_setting only when no known setting fits AND the brief describes a
place.   elements are standalone visual pieces (props, signage, vehicles,
creatures-that-are-not-cast, effects) worth their own acetate — not the
background scenery, not the cast, not text.   At most 5 elements."""
    resp = openai.chat.completions.create(
        model=os.getenv('VISION_MODEL', 'gpt-5.2'),
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content or ""
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if not m:
        return None
    try:
        data = _json.loads(m.group(0))
    except Exception as ex:
        logger.error(f"brief breakdown parse failed: {ex}")
        return None
    known = {c["character_id"] for c in roster}
    known_settings = {s["setting_id"] for s in settings}
    return {
        "setting_id": data.get("setting_id") if data.get("setting_id") in known_settings else None,
        "new_setting": data.get("new_setting") or None,
        "figures": [f for f in (data.get("figures") or [])
                    if isinstance(f, dict) and f.get("character_id") in known][:6],
        "elements": [e for e in (data.get("elements") or [])
                     if isinstance(e, dict) and e.get("name")][:5],
        "wants_masthead": bool(data.get("wants_masthead")),
    }


def series_cast_roster(storage, series_id: str) -> list[dict]:
    """The series' characters as a recognition roster: [{character_id, name, notes}]."""
    from schema import CharacterModel
    roster = []
    for c in storage.read_all_objects(CharacterModel, primary_key={"series_id": series_id}):
        roster.append({"character_id": c.character_id, "name": c.name,
                       "notes": (getattr(c, 'description', '') or '')})
    return roster


def assess_brief(state, series_id: str, description: str, is_cover: bool) -> dict:
    """THE MINIMUM BAR: judge whether a written brief carries enough to STAGE
    the panel — who is present and roughly what they're doing, WHERE it happens,
    and the gist of the shot/mood — so an artist needn't invent the whole scene.
    Text-only, strict JSON.  Deliberately CONSERVATIVE: prefer ready:true and
    only flag a brief that plainly lacks the staging essentials.  Fails OPEN
    (ready=True) on any error, so a flaky judge never blocks the author.

    Returns {"ready": bool, "gaps": [short strings], "note": one friendly line}."""
    import json as _json
    import re as _re

    import openai
    try:
        from storage import registry as _reg
        # the key names its own house — read/write where the object LIVES
        storage = _reg.storage_for_key({"series_id": series_id}, state.storage)
        roster = series_cast_roster(storage, series_id)
        roster_txt = ", ".join(c.get("name") or c["character_id"] for c in roster[:30]) or "(none yet)"
        openai.api_key = os.getenv('OPENAI_API_KEY')
        kind = 'cover' if is_cover else 'panel'
        prompt = f"""You are a comics art director sanity-checking whether a {kind}'s written
brief is detailed enough to hand an artist to ROUGH (stage) — you are NOT judging
its prose, only whether the scene can be staged from it.

BRIEF:
{description}

KNOWN CAST (for reference only): {roster_txt}

A brief is READY when an artist could stage it without inventing the scene: it is
clear WHO (if anyone) is present and roughly what they are doing or feeling, WHERE
it takes place, and the gist of the SHOT or mood.  Not every detail is required —
a spare establishing shot of a place can be ready with no cast at all.

It is NOT ready when the staging essentials are missing — e.g. a character is
named with no action, expression, or blocking; there is no sense of place; or it
is so terse the artist would have to make up the whole scene.

Respond with STRICT JSON only, no prose:
{{"ready": <bool>,
  "gaps": ["<short, concrete missing piece>", ...],
  "note": "<one friendly sentence proposing what to pin down together, or ''>"}}

Be conservative — prefer ready:true unless the brief is clearly too thin to stage."""
        resp = openai.chat.completions.create(
            model=os.getenv('VISION_MODEL', 'gpt-5.2'),
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content or ""
        m = _re.search(r"\{.*\}", text, _re.DOTALL)
        if not m:
            return {"ready": True, "gaps": [], "note": ""}
        data = _json.loads(m.group(0))
        return {
            "ready": bool(data.get("ready", True)),
            "gaps": [str(g) for g in (data.get("gaps") or []) if str(g).strip()][:6],
            "note": str(data.get("note") or "").strip(),
        }
    except Exception as ex:
        logger.error(f"brief readiness assessment failed: {ex}")
        return {"ready": True, "gaps": [], "note": ""}


def _resolve_layer_source(panel, scene, storage, series_id: str, layer: str):
    """Resolve a layer key to (image_path, kind): kind is 'background',
    'figure' or 'element'.  Setting/style come from the scene — or from the
    board itself when it IS its own scene (a cover)."""
    owner = scene if scene is not None else panel
    if layer == 'background':
        # THE SETTING IS A LAYER: the rough shows a background only when the
        # author LAID one on the table (background/plate) — never auto-derived
        # from the scene's setting, so the rough matches the light table.
        plate = (panel.figure_images or {}).get("background/plate")
        if plate and os.path.exists(plate):
            return plate, 'background'
        return None, 'background'
    path = (panel.figure_images or {}).get(layer)
    if path and os.path.exists(path):
        return path, ('element' if layer.startswith('element/') else 'figure')
    return None, 'figure'


def split_layer_body(state, series_id: str, issue_id: str, scene_id: str | None = None,
                     panel_id: str | None = None, layer: str = 'background',
                     entities: list | None = None, cover_id: str | None = None,
                     insert_id: str | None = None) -> str:
    """Split one layer of a board (a panel, a cover, or a full-page insert)
    into its constituent elements.

    layer: 'background', a figure key 'character_id/variant_id', or an
    'element/<slug>' key.   entities: optional list of {name, box} dicts (or
    plain names) chosen by the user; when None, a vision pass recognizes them.
    """
    import re as _re
    from uuid import uuid4
    from storage.filepath import obj_to_imagepath
    from helpers.generator import invoke_edit_image_api

    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    if cover_id:
        panel = storage.read_object(cls=Cover, primary_key={
            "series_id": series_id, "issue_id": issue_id, "cover_id": cover_id})
        if panel is None:
            return f"Cover '{cover_id}' not found."
        scene = None
    elif insert_id:
        from schema import Insert as _Insert
        panel = storage.read_object(cls=_Insert, primary_key={
            "series_id": series_id, "issue_id": issue_id, "insert_id": insert_id})
        if panel is None:
            return f"Insert '{insert_id}' not found."
        scene = None
    else:
        panel = storage.read_object(cls=Panel, primary_key={
            "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id, "panel_id": panel_id})
        if panel is None:
            return f"Panel '{panel_id}' not found."
        scene = storage.read_object(cls=SceneModel, primary_key={
            "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})

    source, kind = _resolve_layer_source(panel, scene, storage, series_id, layer)
    if source is None:
        return f"Layer '{layer}' has no image to split."

    if entities is None:
        entities = recognize_layer_entities(source, max_entities=6,
                                            cast=series_cast_roster(storage, series_id))
    entities = [{"name": e, "box": {}} if isinstance(e, str) else e for e in (entities or [])]
    if not entities:
        return "No liftable entities were recognized on that layer."

    # A recognized entity that IS a cast member lands as that character's
    # posed acetate — cast, named and linked to their reference sheets —
    # not an anonymous element.
    def _variant_for(cid: str) -> str:
        for r in (panel.character_references or []):
            if r.character_id == cid:
                return r.variant_id
        for r in ((scene.cast or []) if scene is not None else []):
            if r.character_id == cid:
                return r.variant_id
        vs = list(storage.read_all_objects(CharacterVariant, primary_key={
            "series_id": series_id, "character_id": cid}))
        return vs[0].variant_id if vs else "default"

    images_dir = obj_to_imagepath(obj=panel, base_path=storage.base_path)
    figures_dir = os.path.join(os.path.dirname(images_dir), "figures")
    os.makedirs(figures_dir, exist_ok=True)

    # FIDELITY RULE: the recomposited stack must look like the original.
    # So we don't re-render entities free-form — we CROP the source at the
    # recognized bounds, erase everything around the entity to transparency
    # (input_fidelity keeps its exact pixels/style), and place the acetate
    # exactly where the crop came from.
    from PIL import Image as _ImgSrc
    src_img = _ImgSrc.open(source).convert('RGBA')
    W0, H0 = src_img.size
    canvas_ar = {"landscape": 1.5, "portrait": 2 / 3, "square": 1.0}[panel.aspect.value]
    layer_blocking = dict((panel.figure_blocking or {}).get(layer) or {})
    lifted = []
    lifted_keys = []
    identified = []
    added_refs = []   # cast the SPLIT added — the only refs the merge may re-add
    used_rects = []   # where things were lifted — the ONLY regions the repaint may touch
    for e in entities:
        name = e["name"]
        slug = _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "element"
        cid = e.get("character_id")
        vid = _variant_for(cid) if cid else None
        key = f"{cid}/{vid}" if cid else f"element/{slug}"
        if key == layer:   # a layer can't be split into itself
            cid, key = None, f"element/{slug}"
        box = e.get("box") or {}
        crop_rect = None
        wipe_rect = None
        if box:
            pad = 0.08
            left = int(max(0.0, float(box.get("x", 0)) / 100 - pad) * W0)
            top = int(max(0.0, float(box.get("y", 0)) / 100 - pad) * H0)
            right = int(min(1.0, (float(box.get("x", 0)) + float(box.get("w", 100))) / 100 + pad) * W0)
            bottom = int(min(1.0, (float(box.get("y", 0)) + float(box.get("h", 100))) / 100 + pad) * H0)
            if right - left >= 32 and bottom - top >= 32:
                crop_rect = (left, top, right, bottom)
            # THE WIPE WINDOW is more generous than the crop: the repaint may
            # only show through here, so it must cover the WHOLE entity even
            # when it pokes past the vision box — anything less leaves a
            # ghost copy of the lifted thing on the remainder.  A degenerate
            # box still gets a real window (never silently unwiped).
            gx, gy = int(W0 * 0.06), int(H0 * 0.06)
            wl, wt = max(0, left - gx), max(0, top - gy)
            wr, wb = min(W0, right + gx), min(H0, bottom + gy)
            if wr - wl < 128:
                cx = (wl + wr) // 2
                wl, wr = max(0, cx - 64), min(W0, cx + 64)
            if wb - wt < 128:
                cy = (wt + wb) // 2
                wt, wb = max(0, cy - 64), min(H0, cy + 64)
            wipe_rect = (wl, wt, wr, wb)

        if crop_rect:
            crop = src_img.crop(crop_rect)
            tmp = os.path.join(figures_dir, f"crop-{uuid4().hex[:6]}.png")
            crop.save(tmp)
            ar = crop.width / crop.height
            size = "1536x1024" if ar > 1.2 else ("1024x1536" if ar < 0.83 else "1024x1024")
            try:
                cut_bytes = invoke_edit_image_api(
                    f"""Reproduce this image EXACTLY — identical pixels, identical style,
identical scale and position within the frame — but keep ONLY the {name}:
erase everything that is not part of the {name} to FULL TRANSPARENCY.
Do not redraw, restyle, move or resize the {name}.""",
                    reference_images=[tmp],
                    size=size,
                    quality=IMAGE_QUALITY.MEDIUM,
                    background="transparent",
                    input_fidelity="high",
                )
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        else:
            cut_bytes = invoke_edit_image_api(
                f"""Render ONLY the {name} exactly as it appears in the reference image —
same angle, same colors, same lighting, same art style.   Nothing else.
COMPLETELY TRANSPARENT background: a cut-out acetate.""",
                reference_images=[source],
                size="1024x1024",
                quality=IMAGE_QUALITY.MEDIUM,
                background="transparent",
                input_fidelity="high",
            )
        stem = f"{cid}--{vid}" if cid else f"element--{slug}"
        cut_path = os.path.join(figures_dir, f"{stem}--{uuid4().hex[:8]}.png")
        with open(cut_path, "wb") as f:
            f.write(cut_bytes)
        panel.figure_images[key] = cut_path
        if cid:
            # cast them into the panel so the acetate rides the figure row
            from schema.character_reference import CharacterRef
            if not any(r.character_id == cid and r.variant_id == vid
                       for r in (panel.character_references or [])):
                ref = CharacterRef(series_id=series_id, character_id=cid, variant_id=vid)
                panel.character_references = (panel.character_references or []) + [ref]
                added_refs.append(ref)
            identified.append(f"{name} = {cid}")

        # place the acetate exactly where its crop came from
        if crop_rect:
            left, top, right, bottom = crop_rect
            cx_pct = (left + right) / 2 / W0 * 100
            h_pct = (bottom - top) / H0 * 100
            y_pct = 100 - bottom / H0 * 100
            if kind == 'background':
                panel.figure_blocking[key] = {"x": round(cx_pct, 1), "y": round(y_pct, 1),
                                              "h": round(h_pct, 1), "z": 40}
            else:
                # map through the parent figure's placement on the canvas —
                # a MIRRORED parent shows its crop on the opposite side, and
                # the lifted acetate inherits the mirroring to keep the look
                fh = float(layer_blocking.get("h", 60))
                fx = float(layer_blocking.get("x", 50))
                fy = float(layer_blocking.get("y", 0))
                fig_w = fh * ((W0 / H0) / canvas_ar)   # display width in canvas %
                rel = (cx_pct - 50)
                if layer_blocking.get('flip'):
                    rel = -rel
                panel.figure_blocking[key] = {
                    "x": round(fx + rel / 100 * fig_w, 1),
                    "y": round(fy + y_pct / 100 * fh, 1),
                    "h": round(h_pct / 100 * fh, 1),
                    "z": int(layer_blocking.get("z", 0)) + 1,
                    **({"flip": 1} if layer_blocking.get('flip') else {})}
        else:
            panel.figure_blocking[key] = {"x": 50, "y": 0, "h": 45, "z": 40}
        lifted.append(name)
        lifted_keys.append(key)
        if wipe_rect:
            used_rects.append(wipe_rect)
        else:
            # no box at all: the wipe can't be localized — open the whole
            # frame to the repaint rather than leave a copy of the lifted
            # thing sitting on the remainder
            logger.warning(f"split: no box for '{name}' — whole-frame repaint window")
            used_rects.append((0, 0, W0, H0))

    # repaint the base with everything lifted removed — revealing what was
    # beneath (a figure keeps its transparency; a background stays opaque)
    names = ", ".join(lifted)
    from PIL import Image as _Img
    with _Img.open(source) as _s:
        # the repaint keeps the SOURCE's orientation — figure acetates are
        # not always portrait (a lifted element can be any shape)
        base_size = "1536x1024" if _s.width > _s.height else ("1024x1536" if _s.height > _s.width else "1024x1024")

    # A MASK MAKES THE REMOVAL RELIABLE: the edit API regenerates ONLY the
    # transparent (lifted) regions, so it CAN'T leave a ghost of the lifted
    # thing on the remainder — the failure the free-form "remove X" prompt hit.
    # (The crop-paste below still guarantees everything outside is untouched.)
    mask_img = _Img.new("RGBA", (W0, H0), (0, 0, 0, 255))          # opaque = KEEP
    for (rl, rt, rr, rb) in (used_rects or [(0, 0, W0, H0)]):
        mask_img.paste((0, 0, 0, 0), (int(rl), int(rt), int(rr), int(rb)))  # clear = REPAINT here
    mask_path = os.path.join(figures_dir, f"mask-{uuid4().hex[:6]}.png")
    mask_img.save(mask_path, 'PNG')
    try:
        base_bytes = invoke_edit_image_api(
            f"""The transparent regions of the mask are where {names} used to be —
they have been cleared.  FILL those regions with what lies BENEATH: reveal and
draw the body, clothing or scenery that was behind each removed item, on-model
and consistent with the surrounding art.  Leave NO trace, edge, shadow or copy
of {names} anywhere.  Everything outside the cleared regions stays PIXEL-IDENTICAL.""",
            reference_images=[source],
            mask=mask_path,
            size=base_size,
            quality=IMAGE_QUALITY.MEDIUM,
            background="transparent" if kind != 'background' else None,
            input_fidelity="high",
        )
    finally:
        if os.path.exists(mask_path):
            os.remove(mask_path)
    # FIDELITY: the edit API redraws the WHOLE frame, so untouched art
    # drifts.  Keep the ORIGINAL pixels everywhere except inside the lifted
    # regions — only where something came off may the repaint show through.
    from io import BytesIO as _BytesIO
    repaint = _Img.open(_BytesIO(base_bytes)).convert('RGBA').resize((W0, H0))
    if used_rects:
        final = src_img.copy()
        for rect in used_rects:
            final.paste(repaint.crop(rect), (rect[0], rect[1]))
    else:
        final = repaint

    stem = "plate" if kind == 'background' else "base"
    base_path = os.path.join(figures_dir, f"{stem}--{uuid4().hex[:8]}.png")
    final.save(base_path, 'PNG')
    if kind == 'background':
        panel.figure_images["background/plate"] = base_path
    else:
        panel.figure_images[layer] = base_path

    # the split nests its products under a group named for the source layer
    if layer == 'background':
        group_name = 'background'
    else:
        _ch = storage.read_object(cls=CharacterModel, primary_key={
            "series_id": series_id, "character_id": layer.split('/', 1)[0]})
        group_name = (_ch.name if _ch is not None
                      else layer.split('/', 1)[-1]).replace('-', ' ')
    members = list(lifted_keys)
    base_key = 'background/plate' if kind == 'background' else layer
    members.append(base_key)

    # persist the split's DELTAS onto a fresh read of the board: the renders
    # above take minutes and the author kept working the table meanwhile
    fresh = storage.read_object(cls=type(panel), primary_key=panel.primary_key) or panel
    if fresh is not panel:
        for k in lifted_keys:
            if k in (panel.figure_images or {}):
                fresh.figure_images[k] = panel.figure_images[k]
            if k in (panel.figure_blocking or {}):
                fresh.figure_blocking[k] = panel.figure_blocking[k]
        if base_key in (panel.figure_images or {}):
            fresh.figure_images[base_key] = panel.figure_images[base_key]
        # only cast the split itself added — never resurrect figures the
        # author removed while the split was on the drawing board
        for r in added_refs:
            if not any(c.character_id == r.character_id and c.variant_id == r.variant_id
                       for c in (fresh.character_references or [])):
                fresh.character_references = (fresh.character_references or []) + [r]
    groups = dict(fresh.layer_groups or {})
    groups[f"{group_name} (split)"] = members
    fresh.layer_groups = groups

    storage.update_object(data=fresh)
    state.is_dirty = True
    matched = f"  Recognized cast: {'; '.join(identified)}." if identified else ""
    return (f"Split layer '{layer}' into {len(lifted)} acetate(s): {names} "
            f"(grouped as '{group_name} (split)').{matched}  "
            f"The base was repainted with them removed: {base_path}")


@function_tool
async def split_layer(wrapper: RunContextWrapper, series_id: str, issue_id: str,
                scene_id: str, panel_id: str, layer: str,
                elements: Optional[list[str]] = None) -> str:
    """
    SPLIT one of a panel's layers into its constituent elements.   A vision
    pass recognizes the entities on the layer (props, wardrobe, furniture,
    signage...) and their bounds; each is lifted onto its own transparent
    acetate placed where it was recognized, and the layer's base is repainted
    with them removed — revealing what was beneath (splitting a character
    lifts their props/garments off, revealing the character underneath).

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the issue.
        scene_id: The ID of the scene the panel belongs to.
        panel_id: The ID of the panel.
        layer: 'background', a figure key 'character_id/variant_id', or an
            'element/<slug>' key.
        elements: Optional list of entity names to lift; when omitted, the
            vision pass decides (at most 6, most prominent first).

    Returns:
        A status message listing the lifted acetates and the repainted base.
    """

    return await asyncio.to_thread(_split_layer_sync, wrapper, series_id, issue_id, scene_id, panel_id, layer, elements)


def _split_layer_sync(wrapper: RunContextWrapper, series_id: str, issue_id: str,
                scene_id: str, panel_id: str, layer: str,
                elements: Optional[list[str]] = None) -> str:
    """
    SPLIT one of a panel's layers into its constituent elements.   A vision
    pass recognizes the entities on the layer (props, wardrobe, furniture,
    signage...) and their bounds; each is lifted onto its own transparent
    acetate placed where it was recognized, and the layer's base is repainted
    with them removed — revealing what was beneath (splitting a character
    lifts their props/garments off, revealing the character underneath).

    Args:
        series_id: The ID of the comic series.
        issue_id: The ID of the issue.
        scene_id: The ID of the scene the panel belongs to.
        panel_id: The ID of the panel.
        layer: 'background', a figure key 'character_id/variant_id', or an
            'element/<slug>' key.
        elements: Optional list of entity names to lift; when omitted, the
            vision pass decides (at most 6, most prominent first).

    Returns:
        A status message listing the lifted acetates and the repainted base.
    """
    return split_layer_body(wrapper.context, series_id, issue_id, scene_id,
                            panel_id, layer, elements)


def generate_insert_art_body(state, series_id: str, issue_id: str, insert_id: str) -> str:
    """Render a FULL-PAGE INSERT — a poster, an ad, a pin-up, the mailbag —
    full-bleed portrait art in the issue's style, from the insert's
    description.  Callable from the GUI (background job) or via the tool."""
    from helpers.generator import invoke_edit_image_api, invoke_generate_image_api
    from schema import Insert

    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    insert = storage.read_object(cls=Insert, primary_key={
        "series_id": series_id, "issue_id": issue_id, "insert_id": insert_id})
    if insert is None:
        return f"Insert '{insert_id}' not found in issue '{issue_id}'."
    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": issue.style_id}) \
        if issue is not None and issue.style_id else None

    # the insert's own style wins; the issue's style is the default
    own_style = storage.read_object(cls=ComicStyle, primary_key={"style_id": insert.style_id}) \
        if getattr(insert, 'style_id', None) else None
    if own_style is not None:
        style = own_style

    kind_notes = {
        "poster": "an in-world poster page, bold display lettering welcome",
        "ad": "a vintage comic-book advertisement page, playful copy and product art",
        "pin-up": "a full-page pin-up: one glorious drawing, a caption strip at the foot",
        "mailbag": "a letters page: masthead, columns of letter excerpts with replies, hand-lettered",
        "title-page": "a title/contents page: the issue title large, credits, a decorative border",
    }

    # THE ROUGH IS THE PENCILS: when the author blocked acetates on the
    # insert's light table, composite them and hand them to the artist first
    rough_guidance = ""
    rough_ref = _compose_table_rough(storage, insert, None)
    table_layout = _table_layout_brief(insert, storage)
    if rough_ref:
        rough_guidance = ("The FIRST reference image is the author's ROUGH of this page — the exact "
                          "composition assembled on the light table.   Treat it as the pencils: keep "
                          "every figure and element at its position, scale and facing; finish and ink "
                          "it in the style.\n")

    prompt = f"""Draw a FULL-PAGE COMIC BOOK INSERT — {kind_notes.get(insert.kind, 'a full page')}.

"{insert.name}"

{insert.description or 'Design it from the name and kind above.'}

{rough_guidance}{table_layout}
Full-bleed portrait page (standard US comic trim), edge to edge — no outer
frame, no white margin.{chr(10) + format_comic_style(style, include_bubble_styles=False, include_character_style=False, heading_level=1) if style is not None else ''}
"""
    art = None
    if style is not None:
        art = style.image.get('art') if isinstance(style.image, dict) else style.image
    refs = [art] if art and os.path.exists(art) else []
    if rough_ref:
        refs.insert(0, rough_ref)
    refs.extend(storage.list_uploads(obj=insert))
    if refs:
        image_bytes = invoke_edit_image_api(prompt, reference_images=refs,
                                            size="1024x1536", quality=IMAGE_QUALITY.HIGH)
    else:
        image_bytes = invoke_generate_image_api(prompt, size="1024x1536",
                                                quality=IMAGE_QUALITY.HIGH)
    locator = storage.upload_binary_image(obj=insert, data=image_bytes)

    # persist onto a FRESH read — renders take minutes
    fresh = storage.read_object(cls=Insert, primary_key=insert.primary_key) or insert
    fresh.image = locator
    storage.update_object(data=fresh)
    state.is_dirty = True
    return f"Insert '{insert.name}' rendered: {locator}"


@function_tool
async def generate_insert_art(wrapper: RunContextWrapper[APPState], series_id: str,
                        issue_id: str, insert_id: str) -> str:
    """
    Render a full-page insert's art — a poster, ad, pin-up, mailbag or title
    page, full-bleed in the issue's style, drawn from the insert's
    description.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.
        insert_id: The ID of the insert to render.

    Returns:
        A status message with the locator of the rendered art.
    """

    return await asyncio.to_thread(_generate_insert_art_sync, wrapper, series_id, issue_id, insert_id)


def _generate_insert_art_sync(wrapper: RunContextWrapper[APPState], series_id: str,
                        issue_id: str, insert_id: str) -> str:
    """
    Render a full-page insert's art — a poster, ad, pin-up, mailbag or title
    page, full-bleed in the issue's style, drawn from the insert's
    description.

    Args:
        series_id: The ID of the series.
        issue_id: The ID of the issue.
        insert_id: The ID of the insert to render.

    Returns:
        A status message with the locator of the rendered art.
    """
    return generate_insert_art_body(wrapper.context, series_id, issue_id, insert_id)


def generate_character_exemplar_body(state, series_id: str, character_id: str,
                                     variant_id: str, notes: str | None = None) -> str:
    """THE MODEL SHEET SESSION starts with ONE great exemplar: a single
    three-quarter portrait of the character that everyone agrees IS them.
    It lands in the variant's uploads, where it anchors every styled
    reference sheet that follows."""
    from helpers.generator import invoke_edit_image_api, invoke_generate_image_api
    from storage import registry as _reg
    # the key names its own house — read/write where the object LIVES
    storage: GenericStorage = _reg.storage_for_key({"series_id": series_id}, state.storage)
    variant = storage.read_object(cls=CharacterVariant, primary_key={
        "series_id": series_id, "character_id": character_id, "variant_id": variant_id})
    if variant is None:
        return f"Variant '{variant_id}' of '{character_id}' not found."
    character = storage.read_object(cls=CharacterModel, primary_key={
        "series_id": series_id, "character_id": character_id})

    prompt = f"""ONE DEFINITIVE PORTRAIT of a comic character — the exemplar
every future drawing will be held to.

{character.name if character else character_id} ({variant.name or variant_id}):
{variant.description}
Race/species: {variant.race}.  Gender: {variant.gender}.  Age: {variant.age}.
Height/build: {variant.height}.
Appearance: {variant.appearance}
Attire: {variant.attire}

Three-quarter view, head to mid-thigh, neutral stance, even studio light,
plain light-gray background.  Clean readable design — this is a MODEL SHEET
exemplar, not a scene.{(chr(10) + "THE AUTHOR'S DIRECTION: " + notes) if notes else ""}
"""
    refs = [u for u in storage.list_uploads(obj=variant) if u and os.path.exists(u)]
    sheet = storage.find_variant_image(series_id=series_id, character_id=character_id,
                                       variant_id=variant_id)
    if sheet and os.path.exists(sheet):
        refs.append(sheet)
    if refs:
        image_bytes = invoke_edit_image_api(prompt, reference_images=refs[:3],
                                            size="1024x1536", quality=IMAGE_QUALITY.HIGH,
                                            input_fidelity="high")
    else:
        image_bytes = invoke_generate_image_api(prompt, size="1024x1536",
                                                quality=IMAGE_QUALITY.HIGH)
    import io as _io
    locator = storage.upload_reference_image(
        variant, f"exemplar--{uuid4().hex[:6]}.png", _io.BytesIO(image_bytes), "image/png")
    state.is_dirty = True
    return (f"Exemplar sculpted for {character.name if character else character_id} "
            f"({variant.name or variant_id}): {locator}.  Every styled sheet is now "
            f"held to it — re-ink sheets that predate it.")


@function_tool
async def generate_character_exemplar(wrapper: RunContextWrapper[APPState], series_id: str,
                                character_id: str, variant_id: str,
                                notes: Optional[str] = None) -> str:
    """
    Sculpt THE EXEMPLAR: one definitive three-quarter portrait of a character
    variant, saved into the variant's uploads where it anchors every styled
    reference sheet that follows.   Iterate here FIRST — cheaper and faster
    than re-rendering multi-angle sheets — until the author says 'that's
    them', then ink the sheets.

    Args:
        series_id: The ID of the series.
        character_id: The character.
        variant_id: The variant (look) to sculpt.
        notes: The author's direction for this attempt ('rounder face',
            'older eyes', 'less armor').  Optional.

    Returns:
        A status message with the exemplar's locator.
    """

    return await asyncio.to_thread(_generate_character_exemplar_sync, wrapper, series_id, character_id, variant_id, notes)


def _generate_character_exemplar_sync(wrapper: RunContextWrapper[APPState], series_id: str,
                                character_id: str, variant_id: str,
                                notes: Optional[str] = None) -> str:
    """
    Sculpt THE EXEMPLAR: one definitive three-quarter portrait of a character
    variant, saved into the variant's uploads where it anchors every styled
    reference sheet that follows.   Iterate here FIRST — cheaper and faster
    than re-rendering multi-angle sheets — until the author says 'that's
    them', then ink the sheets.

    Args:
        series_id: The ID of the series.
        character_id: The character.
        variant_id: The variant (look) to sculpt.
        notes: The author's direction for this attempt ('rounder face',
            'older eyes', 'less armor').  Optional.

    Returns:
        A status message with the exemplar's locator.
    """
    return generate_character_exemplar_body(wrapper.context, series_id,
                                            character_id, variant_id, notes)


def render_artboard_body(state, scope_id: str, board_id: str) -> str:
    """THE MARK'S PROOF: render a masthead or logo take from the art board —
    the composed rough steers when layers are laid; the brief alone carries
    a bare board.  Transparent background always (a mark is an acetate);
    the take lands on the BOARD — featuring writes it home."""
    from schema import ArtBoard, ComicStyle, Series, Publisher
    # the scope names its own house (a mark's scope is a series OR a
    # publisher id — try both before falling back to the bench's storage)
    from storage import registry as _reg
    storage = _reg.storage_for_key({"series_id": scope_id},
              _reg.storage_for_key({"publisher_id": scope_id}, state.storage))
    board = storage.read_object(cls=ArtBoard, primary_key={
        "scope_id": scope_id, "board_id": board_id})
    if board is None:
        return f"cannot render: no art board {board_id}."
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": board.style_id}) \
        if board.style_id else None

    refs: list[str] = []
    rough_note = ""
    try:
        rough = _compose_table_rough(storage, board, board)
        if rough:
            refs.append(rough)
            rough_note = ("The attached rough is the author's own arrangement — "
                          "follow its composition and redraw it as ONE clean mark.\n\n")
    except Exception as ex:
        logger.debug(f"mark rough skipped: {ex}")

    if board.board_kind == 'masthead':
        owner = storage.read_object(cls=Series, primary_key={"series_id": scope_id})
        what = (f'THE MASTHEAD for the comic series "{owner.name if owner else scope_id}" — '
                f'the title as hand-lettered display lettering, a wordmark.')
    else:
        owner = storage.read_object(cls=Publisher, primary_key={"publisher_id": scope_id})
        what = (f'THE LOGO for the comic publishing house "{owner.name if owner else scope_id}" — '
                f'a bold, high-contrast emblem that reads at any size.')

    style_block = format_comic_style(style, include_bubble_styles=False,
                                     include_character_style=False, heading_level=1) if style else ""
    prompt = f"""{rough_note}Design {what}

{("THE BRIEF: " + board.description) if (board.description or '').strip() else ''}

Lettering/emblem only: NO scenery, NO characters, NO frame, NO other text.
COMPLETELY TRANSPARENT background — this is an acetate to composite over art.

{style_block}"""

    art = style.image.get('art') if (style and isinstance(style.image, dict)) else None
    if art and os.path.exists(art):
        refs.append(art)
    if refs:
        image_bytes = invoke_edit_image_api(prompt, reference_images=refs,
                                            size="1536x1024" if board.aspect.value == 'landscape'
                                            else "1024x1024",
                                            quality=IMAGE_QUALITY.HIGH, background="transparent")
    else:
        image_bytes = invoke_generate_image_api(prompt,
                                                size="1536x1024" if board.aspect.value == 'landscape'
                                                else "1024x1024",
                                                quality=IMAGE_QUALITY.HIGH)
    locator = storage.upload_binary_image(obj=board, data=image_bytes)
    return f"Inked a {board.board_kind} take — it waits on the board: {locator}"
