from typing import Optional
from pydantic import BaseModel, Field
from schema.enums import CoverLocation, FrameLayout
from schema.character_reference import CharacterRef
from schema.reference_image import ReferenceImage

class Cover(BaseModel):
    cover_id: str = Field(..., description="A unique identifier for the panel.   Default '<location>-cover'")
    location: CoverLocation = Field(..., description="The location of the cover.  front, inside-front, inside-back or back.  Default to front")
    issue_id: str = Field(..., description="The parent issue of the panel.   Default to empty string")
    series_id: str = Field(..., description="The parent series of the panel.   Default to empty string")
    character_references: list[CharacterRef]  = Field(..., description="The names of the characters in the panel")
    style_id: str = Field(..., description="The art style of the panel.  Default to 'vintage-4-color'")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to portrait")
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel")
    description: str = Field(..., description="A detailed description of the image on the cover.   This should describe the image in sufficient detail so that different artists could from this information alone reproduce the same image.   This should include the setting, foreground, background, characters, props, scenery and any other elements in the cover.")
    image: str | None = Field(..., description="The selected image for this panel.   Default to None")

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