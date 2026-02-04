import os
import json
from PIL import Image
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field
from schema.style.art import ArtStyle
from schema.style.character import CharacterStyle
from schema.style.dialog import BubbleStyles

class ComicStyle(BaseModel):
    """
    Comic style guidelines for a comic series or title.
    """
    style_id: str = Field(
        ...,
        description="A unique identifier for the comic style.  e.g. 'vintage 4 color', etc.")
    name: str = Field(...,description="A short (1-5 word) name for the comic style.  e.g. 'vintage 4 color', etc.   It should not include the words 'comic' or 'style'.")
    description: str = Field(
        ..., description="A Description the comic style capturing the overall aesthetic and tone, and perhaps historical perspective, artists and defining works in the genre.  This should be at least 3 sentences and no longer than several paragraphs."
    )
    art_style: ArtStyle = Field(
        ...,
        description="Artistic style and ink rendering parameters for the comic."
    )
    character_style: CharacterStyle = Field(
        ...,
        description="Character appearance and form style guidelines for the comic."
    )
    bubble_styles: BubbleStyles = Field(
        ...,
        description="Styling for any kind of text balloon or narration box within the comic."
    )
    image: Optional[str] | dict[str, Optional[str]]= Field(..., description="A reference image for the comic style.  default to None")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the comic style
        """
        return {
            "style_id": self.style_id,
        }

    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the comic style
        """
        return {}
    
    @property
    def id(self) -> str:
        """
        return the id of the comic style
        """
        # Normalize the id:
        return self.style_id

