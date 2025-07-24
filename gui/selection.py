from loguru import logger
from typing import Tuple, Optional
from pydantic import BaseModel, Field
from nicegui import ui
from enum import StrEnum


class SelectedKind(StrEnum):
    """Enum for the selections that can occur in the gui."""
    ALL_SERIES = "all-series"
    ALL_PUBLISHERS = "all-publishers"
    ALL_STYLES = "all-styles"

    SERIES = "series"
    ISSUE = "issue"
    SCENE = "scene"
    PANEL = "panel"
    COVER = "cover"
    CHARACTER = "character"
    VARIANT = "variant"
    STYLED_VARIANT = "styled-variant"
    PUBLISHER = "publisher"
    STYLE = "style"
    STYLE_EXAMPLE = "style-example"
    # PICKERS
    PICK_PUBLISHER = "pick-publisher"
    PICK_STYLE = "pick-style"
    REFERENCE_IMAGE = "reference-image"
    CHARACTER_REFERENCE = "character-reference"

class SelectionItem(BaseModel):
    name: str = Field(..., description="The name that will be displayed on the breadcrumbs")
    id: str | None = Field(..., description="The id of the item.  This will be used to identify the item in the system.")
    kind: SelectedKind = Field(..., description="The kind of item.  This will be used to identify the item in the system.")

def selection_to_context(
    selection: list[SelectionItem]
) -> Tuple[type[BaseModel], dict[str, str]]:
    """
    Converts a selection of items into a primary key string.
    
    Args:
        selection: A list of SelectionItem objects representing the current selection.
    
    Returns:
        A string that represents the primary key for the selection.
    """
    from schema import Publisher, ComicStyle, Series, Issue, SceneModel, Panel, Cover, CharacterModel, CharacterVariant, StyledVariant, ReferenceImage
    i = 0
    accum  = {}
    context = []
    while i < len(selection):
        kind = selection[i].kind
        id = selection[i].id
        i += 1
        match kind.value:
            case SelectedKind.PUBLISHER.value:
                accum["publisher_id"] = id
                context.append((Publisher, {k:v for k, v in accum.items()}))
            case SelectedKind.STYLE.value:
                accum["style_id"] = id
                context.append((ComicStyle, {k:v for k, v in accum.items()}))
            case SelectedKind.SERIES.value:
                accum["series_id"] = id
                context.append((Series, {k:v for k, v in accum.items()}))
            case SelectedKind.ISSUE.value:
                accum["issue_id"] = id
                context.append((Issue, {k:v for k, v in accum.items()}))
            case SelectedKind.SCENE.value:
                accum["scene_id"] = id
                context.append((SceneModel, {k:v for k, v in accum.items()}))
            case SelectedKind.PANEL.value:
                accum["panel_id"] = id
                context.append((Panel, {k:v for k, v in accum.items()}))
            case SelectedKind.COVER.value:
                accum["cover_id"] = id
                context.append((Cover, {k:v for k, v in accum.items()}))
            case SelectedKind.CHARACTER.value:
                accum["character_id"] = id
                context.append((CharacterModel, {k:v for k, v in accum.items()}))
            case SelectedKind.VARIANT.value:
                accum["variant_id"] = id
                context.append((CharacterVariant, {k:v for k, v in accum.items()}))
            case SelectedKind.STYLED_VARIANT.value:
                accum["styled_image_id"] = id
                context.append((StyledVariant, {k:v for k, v in accum.items()}))
            case SelectedKind.REFERENCE_IMAGE.value:
                accum["image_id"] = id
                context.append((ReferenceImage, {k:v for k, v in accum.items()}))
            
            case SelectedKind.ALL_PUBLISHERS.value: 
                continue
            case SelectedKind.ALL_SERIES.value:
                continue
            case SelectedKind.ALL_STYLES.value:
                continue
            case _:

                raise ValueError(f"Unknown selection kind: {kind.value}")
    return context
