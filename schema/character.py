import os
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field
from helpers.generator import invoke_generate_api, invoke_generate_image_api
from helpers.constants import CHARACTERS_FOLDER, COMICS_FOLDER, DATA_FOLDER
from helpers.file import generate_unique_id, get_folder_contents, subfolders
from helpers.image import IMAGE_QUALITY

from schema.style.comic import ComicStyle

class CharacterModel( BaseModel):
    # Note: The character name:variant is used as the key in the characters dictionary and must be unique
    character_id : str = Field(..., description="The unique identifier for the character model.  This is usually the character name in lowercase with spaces replaced by dashes.  defaults to null")
    series_id: str = Field(..., description="The comic book series (title) that the character belongs to.  Default to empty string")
    description: str = Field(..., description="A 1-2 sentence description of the character.  This should be sufficient to distinguish the character from others.")
    name: str = Field(..., description="The name of the character")
    
    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the character model
        """
        return {
            "character_id": self.character_id,
            "series_id": self.series_id,
        }
    
    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the character model
        """
        return {
            "series_id": self.series_id,
        }
    
    @property
    def id(self) -> str:
        """
        return the id of the character model
        """
        # Normalize the id:
        return self.character_id
