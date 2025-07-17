import os
from typing import Tuple, Optional, List
from gui.state import APPState
from helpers.constants import COMICS_FOLDER
from agents import Agent, function_tool, Tool, RunContextWrapper
from agentic.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from schema import CharacterVariant
from agentic.character import render_character_image
from schema.style.comic import ComicStyle
from agentic.instructions import instructions


def render_styled_image(
        wrapper: RunContextWrapper[APPState],
        series_id: str,
        character_id: str,
        variant_id: str,
        style_id: str):
    """
    Render a styled image of the currently selected character variant.
    
    Args:
        series_id: The ID of the comic series.
        character_id: The ID of the character to which the variant belongs.
        variant_id: The ID of the character variant to render.
        style_id: The ID of the style to apply to the character variant.
    
    Returns:
        A string indicating the result of the rendering operation.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    normalized_style_name = style_name.lower().strip()
    series_id=state.selection[-3].id
    character_id=state.selection[-2].id
    variant_id=state.selection[-1].id
    variant = CharacterVariant.read(
        series=series_id,
        character=character_id,
        id=variant_id
    )
    if isinstance(variant, str):
        return variant
    variant: CharacterVariant = variant
    
    all_styles = ComicStyle.read_all()
    names = [style.name.lower() for style in all_styles]

    if normalized_style_name not in names:
        return f"Style '{style_name}' not found.  Maybe it was one of these: {', '.join(names)}.   If any are a likely match, confirm with the user.  Otherwise, ask them to pick one of the available styles."

    style_id = normalized_style_name.replace(" ", "-")
    style = ComicStyle.read(id=style_id)
    if not style:
        return f"Style '{style_name}' could not be loaded."
    style: ComicStyle = style


    character_name = variant.character_id.replace('-', ' ').title()
    save_path = os.path.join(
        COMICS_FOLDER,
        series_id,
        "characters",
        character_id,
        variant.variant_id,
        "images",
        style_id
    )

    def format(variant: CharacterVariant, heading_level: int = 3) -> str:
        result = f"""{'#'*heading_level} Character Model ({variant.name})
* **Name**: {variant.name}
* **Race**: {variant.race}
* **Age**: {variant.age}
* **Height**: {variant.height}
* **Gender**: {variant.gender}
* **Description**: {variant.description}
* **Attire**: {variant.attire}
        """.strip()
        if variant.appearance is not None and variant.appearance != "":
            result += f"\n* **Appearance**: {variant.appearance}"
        if variant.behavior is not None and variant.behavior != "":
            result += f"\n* **Behavior**: {variant.behavior}"
        return result + "\n\n            """


    image_id = render_character_image(
        character_name=character_name,
        character_description = format(variant),
        style_description = style.format(include_bubble_styles=False),
        save_path=save_path
    )

    variant.images[style_id] = image_id
    variant.write()
    state.is_dirty = True
