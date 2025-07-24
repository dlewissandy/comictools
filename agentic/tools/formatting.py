

from agentic.tools.normalization import normalize_name
from schema import (
    CharacterVariant,
    ComicStyle,
    ArtStyle,
    CharacterStyle,
    BubbleStyles,
    BubbleStyle,
    Issue
)

def format_character_variant(character_name, variant: CharacterVariant, heading_level: int) -> str:
    # Format the character text with the given heading level
    text = f"{'#' * heading_level} {character_name} ({variant.name})\n"
    text += f"* **Description**: {variant.description}\n"
    text += f"* **Gender**: {variant.gender}\n"
    text += f"* **Species**: {variant.race}\n"
    text += f"* **Age**: {variant.age}\n"
    text += f"* **Height**: {variant.height}\n"
    text += f"* **Physical Appearance**: {variant.appearance}\n"
    text += f"* **Attire**: {variant.attire}\n"
    return text


def format_comic_style(style: ComicStyle, include_bubble_styles: bool = True, include_character_style: bool = True, heading_level: int = 1) -> str:
    """
    format the comic style for display
    """
    result = f"""{'#'*heading_level} Comic Style ({style.name})
{style.description}""".strip()
    if style.art_style is not None:
        result += f"\n{format_art_style(style.art_style, heading_level=heading_level + 1)}"
    if style.character_style is not None and include_character_style:
        result += f"\n{format_character_style(style.character_style, heading_level=heading_level + 1)}"
    if style.bubble_styles is not None and include_bubble_styles:
        result += f"\n{format_bubble_styles(style.bubble_styles, heading_level=heading_level + 1)}"
    return result

def format_art_style(style: ArtStyle, heading_level: int = 1) -> str:
    self_json = style.model_dump()
    result = f"{'#'*heading_level} Art Style\n  The art style defines the visual language of the medium, including linework.\n\n"
    for key, value in self_json.items():
        if key == "lettering_style":
            continue
        if value is None or value == "":
            continue
        result += f"* **{key.replace('_', ' ').capitalize()}**: {value}\n\n"
    return result

def format_character_style(style: CharacterStyle, heading_level: int = 1) -> str:
    self_json = style.model_dump()
    result = f"{'#'*heading_level} Character Style\n  The character style defines the visual language of the characters, including proportions, anatomy, and expressions.   It should apply to all characters unless specified otherwise.\n\n"
    for key, value in self_json.items():
        if value is None or value == "":
            continue
        result += f"* **{key.replace('_', ' ').capitalize()}**: {value}\n\n"
    return result

def format_bubble_styles(styles: BubbleStyles, heading_level: int = 1) -> str:
    """
    Format the bubble styles for display.
    """
    self_json = styles.model_dump()
    result = f"{'#'*heading_level} Bubble Styles\n  The bubble styles define the visual language of the text balloons and narration boxes within the comic.\n\n"
    for k,v in self_json.items():
        style_name = normalize_name(k)
        result += f"* **{style_name.replace('_', ' ').capitalize()}**: {v}\n"

    return result
    
def format_issue(issue: Issue, heading_level: int=1) -> str:
    """
    Format the comic book for display
    """
    text = f"{'#'* heading_level} ISSUE {issue.issue_number}\n\n"
    if issue.name is not None:
        text += f" * **title** {issue.name}\n\n"
    if issue.publication_date is not None:
        text += f" * **date** {issue.publication_date}\n\n"
    if issue.writer is not None:
        text += f" * **writer** {issue.writer}\n\n"
    if issue.artist is not None:
        text += f" * **artist** {issue.artist}\n\n"
    if issue.colorist is not None:
        text += f" * **colorist** {issue.colorist}\n\n"
    if issue.creative_minds is not None:
        text += f" * **creative minds** {issue.creative_minds}\n\n"
    if issue.price is not None:
        text += f" * **price** {issue.price}\n\n"
    return text