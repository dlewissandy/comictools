from loguru import logger
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
    CHARACTER_REFERENCE = "character-reference"
    VARIANT = "variant"
    STYLED_IMAGE = "styled-image"
    PUBLISHER = "publisher"
    STYLE = "style",
    # PICKERS
    PICK_PUBLISHER = "pick-publisher"
    PICK_STYLE = "pick-style"

class SelectionItem(BaseModel):
    name: str = Field(..., description="The name that will be displayed on the breadcrumbs")
    id: str | None = Field(..., description="The id of the item.  This will be used to identify the item in the system.")
    kind: SelectedKind = Field(..., description="The kind of item.  This will be used to identify the item in the system.")



