from pydantic import BaseModel, Field
from schema.dialog import Narration, Dialogue, NarrationPosition
from schema.enums import FrameLayout
from schema.reference_image import ReferenceImage
from schema.character_reference import CharacterRef

class Panel(BaseModel):
    # IDENTIFIERS
    panel_id: str = Field(..., description="A unique identifier for the panel.   Default to 1")
    issue_id: str = Field(..., description="The parent issue of the panel.   Default to empty")
    scene_id: str = Field(..., description="The parent scene of the panel.   Default to empty string")
    series_id: str = Field(..., description="The parent series of the panel.   Default to empty string")
    panel_number: int = Field(..., description="The number of the panel in the scene.   Default to 1")

    #PROPERTIES
    name: str = Field(..., description="The name of the panel.   Should be a short (3-5 words) description of the panel.   This should be a short description of the panel that can be used to identify it in a list of panels.   Default to empty string")
    beat: str = Field("", description="The narrative beat for the panel.   This should describe what changes or happens in this moment.   Keep it concise (1-3 sentences).")
    description: str = Field(..., description="A detailed visual description of the image in the panel.   This should describe the image in sufficient detail so that different artists could from this information alone reproduce the same image.   This should include the setting, foreground, background, characters, props, scenery and any other elements in the panel.")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to square")
    size: str = Field(default="1x", description="How big the panel prints, as a multiplier: '1x' or '2x' for landscape and portrait, '1x'/'2x'/'3x' for square.  A 2x panel commands its own band instead of pairing.  Default to '1x'.")
    character_references: list[CharacterRef] = Field(..., description="A dictionary mapping the names of the characters that appear in the panel to the visual variant that should be used as reference.   Default to empty dict")

    # DIALOGUE AND NARRATION
    narration: list[Narration] = Field(..., description="The narration of the panel.  default to empty list")
    dialogue: list[Dialogue] = Field(..., description="The dialogue of the panel, default to empty list")
    
    # IMAGES
    image: str | None = Field(None, description="The selected image for this panel.  default to None")
    figure_images: dict[str, str] = Field(default_factory=dict, description="Posed figure acetates for this panel: maps 'character_id/variant_id' to a transparent cut-out image posed for this moment.  Default to empty dict.")
    figure_blocking: dict[str, dict] = Field(default_factory=dict, description="Blocking for each figure acetate: maps 'character_id/variant_id' to {x: percent from left (center of figure), y: percent up from the bottom, h: height as percent of the frame}.  Default to empty dict.")
    layer_groups: dict[str, list[str]] = Field(default_factory=dict, description="Named groups of light-table layers: maps a group name to the member layer keys.  Splitting a layer nests its products under a group.  Default to empty dict.")
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel.  default to empty list")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the panel model
        """
        return {
            "panel_id": self.id,
            "issue_id": self.issue_id,
            "scene_id": self.scene_id,
            "series_id": self.series_id,
        }

    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the panel model
        """
        return {
            "issue_id": self.issue_id,
            "scene_id": self.scene_id,
            "series_id": self.series_id,
        }

    @property
    def id(self) -> str:
        """
        return the id of the panel
        """
        return self.panel_id
