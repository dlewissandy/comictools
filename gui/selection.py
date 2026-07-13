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
    LIBRARY = "library"

    SERIES = "series"
    SETTING = "setting"
    PROP = "prop"
    OUTFIT = "outfit"
    ISSUE = "issue"
    SCENE = "scene"
    PANEL = "panel"
    COVER = "cover"
    INSERT = "insert"
    CHARACTER = "character"
    VARIANT = "variant"
    STYLED_VARIANT = "styled-variant"
    PUBLISHER = "publisher"
    STYLE = "style"
    STYLE_EXAMPLE = "style-example"
    IMAGE_EDITOR = "image-editor"
    IMAGE_EDITOR_CHOICES = "image-editor-choices"
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
    from schema import Publisher, ComicStyle, Series, Issue, SceneModel, Panel, Cover, CharacterModel, CharacterVariant, StyledVariant, ReferenceImage, Setting, PropAsset, Outfit
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
                # Series sit under publishers for NAVIGATION, but storage keys
                # are rooted at series_id — the chain resets here.
                accum = {"series_id": id}
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
            case SelectedKind.INSERT.value:
                from schema import Insert
                accum["insert_id"] = id
                context.append((Insert, {k:v for k, v in accum.items()}))
            case SelectedKind.CHARACTER.value:
                accum["character_id"] = id
                context.append((CharacterModel, {k:v for k, v in accum.items()}))
            case SelectedKind.SETTING.value:
                accum["setting_id"] = id
                context.append((Setting, {k:v for k, v in accum.items()}))
            case SelectedKind.PROP.value:
                accum["prop_id"] = id
                context.append((PropAsset, {k:v for k, v in accum.items()}))
            case SelectedKind.OUTFIT.value:
                accum["outfit_id"] = id
                context.append((Outfit, {k:v for k, v in accum.items()}))
            case SelectedKind.VARIANT.value:
                accum["variant_id"] = id
                context.append((CharacterVariant, {k:v for k, v in accum.items()}))
            case SelectedKind.STYLED_VARIANT.value:
                accum["style_id"] = id
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
            case SelectedKind.LIBRARY.value:
                continue
            case SelectedKind.IMAGE_EDITOR.value:
                continue
            case SelectedKind.IMAGE_EDITOR_CHOICES.value:
                continue
            case _:

                raise ValueError(f"Unknown selection kind: {kind.value}")
    return context


def house_for_selection(selection) -> str | None:
    """WHICH HOUSE ARE WE IN: derive the selection's publisher repo slug.

    Deterministic order — the trail's publisher, else its series' home,
    else its style's holder (first hit; bare style ids are ambiguous by
    design since default styles are copies).  None at the lobby or in the
    legacy single-root layout — callers fall back to an inert root or fan
    out across every mounted house.
    """
    from storage import registry
    if not registry.registered():
        return None
    for item in selection or []:
        if item.kind == SelectedKind.PUBLISHER and item.id:
            slug = registry.house_of_publisher(item.id)
            if slug:
                return slug
    for item in selection or []:
        if item.kind == SelectedKind.SERIES and item.id:
            slug = registry.house_of_series(item.id)
            if slug:
                return slug
    for item in selection or []:
        if item.kind in (SelectedKind.STYLE, SelectedKind.STYLED_VARIANT) and item.id:
            slug = registry.house_of_style(str(item.id).split("|", 1)[0]) if item.kind == SelectedKind.STYLED_VARIANT else registry.house_of_style(item.id)
            if slug:
                return slug
    return None
