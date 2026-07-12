from typing import Optional
from pydantic import BaseModel, Field
from schema.enums import CoverLocation, FrameLayout
from schema.character_reference import CharacterRef
from schema.dialog import Dialogue, Narration
from schema.reference_image import ReferenceImage

class Cover(BaseModel):
    cover_id: str = Field(..., description="A unique identifier for the cover.")
    location: CoverLocation = Field(..., description="The location of the cover.  front, inside-front, inside-back or back.  Default to front")
    issue_id: str = Field(..., description="The parent issue of the panel.   Default to empty string")
    series_id: str = Field(..., description="The parent series of the panel.   Default to empty string")
    character_references: list[CharacterRef]  = Field(..., description="The names of the characters in the panel")
    setting_id: Optional[str] = Field(None, description="The setting where the cover scene takes place.  Its master background is used as a reference so the cover matches the interior pages.  Default to None.")
    style_id: str = Field(..., description="The art style of the panel.  Default to 'vintage-4-color'")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to portrait")
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel")
    description: str = Field(..., description="A detailed description of the image on the cover.   This should describe the image in sufficient detail so that different artists could from this information alone reproduce the same image.   This should include the setting, foreground, background, characters, props, scenery and any other elements in the cover.")
    image: str | None = Field(..., description="The selected image for this panel.   Default to None")

    # COVER LETTERS: covers carry copy too — taglines in narrator boxes, a
    # character speaking right off the cover.  Same shapes as Panel, so the
    # light table's letters experience works on both.
    narration: list[Narration] = Field(default_factory=list, description="Cover copy in narrator boxes — taglines, story hooks.  Default to empty list.")
    dialogue: list[Dialogue] = Field(default_factory=list, description="Cover dialogue balloons — a character speaking from the cover.  Default to empty list.")

    # THE LIGHT TABLE (same acetate model as Panel — covers compose on the
    # same table, so the fields match exactly)
    figure_images: dict[str, str] = Field(default_factory=dict, description="Posed figure acetates for this cover: maps 'character_id/variant_id' to a transparent cut-out image posed for this moment.  Default to empty dict.")
    figure_blocking: dict[str, dict] = Field(default_factory=dict, description="Blocking for each figure acetate: maps 'character_id/variant_id' to {x: percent from left (center of figure), y: percent up from the bottom, h: height as percent of the frame}.  Default to empty dict.")
    layer_groups: dict[str, list[str]] = Field(default_factory=dict, description="Named groups of light-table layers: maps a group name to the member layer keys.  Splitting a layer nests its products under a group.  Default to empty dict.")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the title board model
        """
        return {
            "series_id": self.series_id,
            "issue_id": self.issue_id,
            "cover_id": self.cover_id
        }

    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the title board model
        """
        return {
            "series_id": self.series_id,
            "issue_id": self.issue_id,
        }
    
    @property
    def id(self) -> str:
        """
        return the id of the cover
        """
        return self.cover_id
