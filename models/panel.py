import os
from typing import Optional
from pydantic import BaseModel, Field
from enum import StrEnum
from models.character import CharacterModel
from models.bubble import Naration, NarationLocation, Dialogue, DialogueEmphasis
from style.comic import ComicStyle
from helpers.constants import PANELS_FOLDER, SCENES_FOLDER, COMICS_FOLDER

class FrameLayout(StrEnum):
    SQUARE = "square"
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"

def frame_dimensions(aspect: FrameLayout) -> tuple[int, int]:
    if aspect == FrameLayout.LANDSCAPE:
        return 3,2
    elif aspect == FrameLayout.PORTRAIT:
        return 2,3
    else:
        return 2,2
    
class Relation(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    LEFT = "left"
    RIGHT = "right"
    ABOVE = "above"
    BELOW = "below"
    BACKGROUND = "background"

class BeatBoardModel(BaseModel):
    id: str = Field(..., description="A unique identifier for the panel.   Default to a short (3-5 word) description of the panel")
    issue: str = Field(..., description="The parent issue of the panel.   Default to empty")
    scene: str = Field(..., description="The parent scene of the panel.   Default to empty string")
    story: str = Field(..., description="The story or main action in the panel.   The story can contain multiple actions as long as they are concurrent with each other.   Sequential actions should be separated into different panels.")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to square")
    characters: list[str] = Field(..., description="The names of the characters in the panel.   Make certain that EVERY character that appears explicitly or implied in the panel is listed here")

    def path(self) -> str:
        """
        return the path to the panel model
        """
        return f"{COMICS_FOLDER}/{self.issue}/scenes/{self.scene}/panels/{self.id}"
    
    def filepath(self) -> str:
        """
        return the filepath to the panel model
        """
        return os.path.join(self.path(),"beatboard.json")

    def write(self):
        """
        write the panel model to a file
        """
        # create the directory if it doesn't exist
        os.makedirs(self.path(), exist_ok=True)
        # write the panel model to a file
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read(cls, issue: str, scene: str, id: str):
        """
        read the panel model from a file
        """
        import json
        # read the panel model from a file
        filepath = f"{COMICS_FOLDER}/{issue}/scenes/{scene}/panels/{id}/beatboard.json"
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)

    def format(self, heading_level: int = 1) -> str:
        """
        format the panel model for display
        """
        text = f"""
* **story**: {self.story}
* **characters**:
{"\n".join([f"  - {character}" for character in self.characters])}
* **aspect**: {self.aspect}
"""
        return text


class ReferenceImage(BaseModel):
    filepath: str = Field(..., description="The filepath of the reference image")
    relation: Relation = Field(..., description="The relation of the reference image to the panel")

class CoverLocation(StrEnum):
    FRONT = "front"
    INSIDE_FRONT = "inside-front"
    INSIDE_BACK = "inside-back"
    BACK = "back"
    

class TitleBoardModel(BaseModel):
    id: str = Field(..., description="A unique identifier for the panel.   Default '<location>-cover'")
    location: CoverLocation = Field(..., description="The location of the cover.  front, inside-front, inside-back or back.  Default to front")
    issue: str = Field(..., description="The parent issue of the panel.   Default to empty string")
    characters: list[str]  = Field(..., description="The names of the characters in the panel")
    style: str = Field(..., description="The art style of the panel.  Default to 'vintage-4-color'")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to portrait")
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel")
    foreground: str = Field(..., description="The foreground of the panel")
    background: str | None = Field(None, description="The background of the panel")
    image: str | None = Field(None, description="The selected image for this panel")

    def path(self) -> str:
        """
        return the path to the panel model
        """
        location_id = self.location.value.replace("_", "-")
        return os.path.join(COMICS_FOLDER,self.issue,"covers",location_id)
    
    def filepath(self) -> str:
        """
        return the filepath to the panel model
        """
        return os.path.join(self.path(),"titleboard.json")
    
    def image_filepath(self) -> str | None:
        """
        return the filepath to the image
        """
        if self.image is None or self.image == "":
            return None
        return os.path.join(self.path(), "images", f"{self.image}.jpg")

    def format(self, heading_level: int = 1) -> str:
        """
        format the panel model for display
        """
        text = f"""
* **location**: {self.location}
* **style**: {self.style}
* **aspect**: {self.aspect}
* **characters**:
{"\n".join([f"  - {character}" for character in self.characters])}
* **foreground**: {self.foreground}
* **background**: {self.background}
"""
        return text
    
    def write(self):
        """
        write the panel model to a file
        """
        # create the directory if it doesn't exist
        os.makedirs(self.path(), exist_ok=True)
        # write the panel model to a file
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read(cls, issue: str, location: CoverLocation):
        """
        read the panel model from a file
        """
        if isinstance(location, CoverLocation):
            location_id = location.value.replace("_", "-")
        else:
            # if it is a string then it is a location
            location_id = location.replace("_", "-")

        filepath = os.path.join(COMICS_FOLDER, issue, "covers", location_id, "titleboard.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)
        
    

class RoughBoardModel(BaseModel):
    id: str = Field(..., description="A unique identifier for the panel.   Default to a short (3-5 word) description of the panel")
    issue: Optional[str] = Field(..., description="The parent storyboard of the panel.   Default to empty string")
    scene: Optional[str] = Field(..., description="The parent scene of the panel.   Default to empty string")
    characters: list[str] = Field(..., description="The names of the characters in the panel")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  Default to square")
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel")
    foreground: str = Field(..., description="The foreground of the panel.  In most cases this will describe the primary action of the panel.  Describe any other props, scenery or elements in sufficient detail so that an artist could reproduce the same foreground in another panel if need be.")
    background: str = Field(..., description="The background of the panel.  Describe any other props, scenery or elements in sufficient detail so that an artist could reproduce the same background in another panel if need be.")
    naration: list[Naration] = Field(..., description="The narration of the panel")
    dialogue: list[Dialogue] = Field(..., description="The dialogue of the panel")
    image: str | None = Field(None, description="The selected image for this panel")

    def path(self) -> str:
        """
        return the path to the panel model
        """
        return f"{self.issue}/scenes/{self.scene}/panels/{self.id}"
    
    def filepath(self) -> str:
        """
        return the filepath to the panel model
        """
        return os.path.join(self.path(),"roughboard.json")

    def write(self):
        """
        write the panel model to a file
        """
        # create the directory if it doesn't exist
        os.makedirs(self.path(), exist_ok=True)
        # write the panel model to a file
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read(cls, issue: str, scene: str, id: str):
        """
        read the panel model from a file
        """
        # read the panel model from a file
        filepath = f"{COMICS_FOLDER}/{issue}/scenes/{scene}/panels/{id}/roughboard.json"
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)
        
    def format(self, heading_level: int = 1) -> str:
        """
        format the panel model for display
        """
        text = f"""
* **id**: {self.id}
* **characters**:
{"\n".join([f"  - {character}" for character in self.characters])}
* **aspect**: {self.aspect}
* **foreground**: {self.foreground}
* **background**: {self.background}
* **naration**:
{"\n".join([f"  - {naration.text} (at {naration.location})" for naration in self.naration])}
* **dialogue**:
{"\n".join([f"  - {dialogue.character} ({dialogue.emphasis}): {dialogue.text}" for dialogue in self.dialogue])}
"""
        return text