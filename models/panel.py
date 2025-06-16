import os
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field, computed_field
from enum import StrEnum
from models.character import CharacterModel, CharacterVariant
from models.bubble import Naration, NarationLocation, Dialogue, DialogueEmphasis
from style.comic import ComicStyle
from helpers.constants import PANELS_FOLDER, SCENES_FOLDER, COMICS_FOLDER

class FrameLayout(StrEnum):
    SQUARE = "square"
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"

class Relation(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    LEFT = "left"
    RIGHT = "right"
    ABOVE = "above"
    BELOW = "below"
    BACKGROUND = "background"

class ReferenceImage(BaseModel):
    id: str = Field(..., description="A unique identifier for the reference image")
    image: str = Field(..., description="The filepath of the reference image")
    relation: Relation = Field(..., description="The relation of the reference image to the panel")

    def image_filepath(self) -> str:
        """
        return the path to the reference image
        """
        return self.image
    


def frame_dimensions(aspect: FrameLayout) -> tuple[int, int]:
    if aspect == FrameLayout.LANDSCAPE:
        return 3,2
    elif aspect == FrameLayout.PORTRAIT:
        return 2,3
    else:
        return 2,2
    
class CharacterRef(BaseModel):
    series: str = Field(..., description="The series of the character variant")
    character: str = Field(..., description="The name of the character")
    variant: str = Field(..., description="The variant of the character")
    
    @property
    def id(self) -> str:
        """
        return the id of the character variant
        """
        return f"{self.series}/{self.character}/{self.variant}"
    
    @property
    def name(self) -> str:
        """
        return the name of the character variant
        """
        return f"{self.character.replace('_', ' ').title()} ({self.variant.replace('_', ' ').title()})"
    
    def image_filepath(self) -> str | None:
        """
        return the filepath of the character variant
        """
        variant = CharacterVariant.read(series=self.series, character=self.character, id=self.variant)
        if variant is None:
            logger.warning(f"Character {self.character} ({self.variant}) not found in series {self.series}")
            return None
        return variant.image_filepath()


class Panel(BaseModel):
    # IDENTIFIERS
    id: int = Field(..., description="A unique identifier for the panel.   Default to 1")
    issue: str = Field(..., description="The parent issue of the panel.   Default to empty")
    scene: str = Field(..., description="The parent scene of the panel.   Default to empty string")
    series: str = Field(..., description="The parent series of the panel.   Default to empty string")
    #PROPERTIES
    description: str = Field(..., description="A detailed description of the image in the panel.   This should describe the image in sufficient detail so that different artists could from this information alone reproduce the same image.   This should include the setting, foreground, background, characters, props, scenery and any other elements in the panel.")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to square")
    characters: list[CharacterRef] = Field(..., description="A dictionary mapping the names of the characters that appear in the panel to the visual variant that should be used as reference.   Default to empty dict")

    # DIALOGUE AND NARATION
    narration: list[Naration] = Field(..., description="The narration of the panel.  default to empty list")
    dialogue: list[Dialogue] = Field(..., description="The dialogue of the panel, default to empty list")
    
    # IMAGES
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel. default to empty list")
    image: str | None = Field(None, description="The selected image for this panel.  default to None")

    def set_aspect(self, aspect: FrameLayout):
        """
        set the aspect ratio of the panel
        """
        logger.debug(f"set aspect {aspect}")
        self.aspect = aspect
        self.write()

    def path(self) -> str:
        """
        return the path to the panel model
        """
        return f"{COMICS_FOLDER}/{self.series}/issues/{self.issue}/scenes/{self.scene}/panels/{self.id}"
    
    def filepath(self) -> str:
        """
        return the filepath to the panel model
        """
        return os.path.join(self.path(),"panel.json")
    
    def image_filepath(self) -> str:
        return None

    def write(self):
        """
        write the panel model to a file
        """
        # create the directory if it doesn't exist
        os.makedirs(self.path(), exist_ok=True)
        # write the panel model to a file
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    def image_path(self) -> str:
        """
        return the path to the images for this panel
        """
        return os.path.join(self.path(), "images")
    
    def all_images(self) -> list[str]:
        """
        return a list of all the images in the panel
        """
        images_path = self.image_path()
        if not os.path.exists(images_path):
            return []
        return [f[:-4] for f in os.listdir(images_path) if f.endswith(".jpg")]
    
    def set_image(self, id: str):
        """
        set the image for the panel
        """
        self.image = id
        self.write()

    @classmethod
    def read(cls, series:str, issue: str, scene: str, id: str):
        """
        read the panel model from a file
        """
        import json
        # read the panel model from a file
        filepath = f"{COMICS_FOLDER}/{series}/issues/{issue}/scenes/{scene}/panels/{id}/panel.json"
        if not os.path.exists(filepath):
            logger.warning(f"file not found: {filepath}")
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)

    def format(self, heading_level: int = 1) -> str:
        """
        format the panel model for display
        """
        text = f"""
* **story**: {self.description}
* **characters**:
{"\n".join([f"  - {character}" for character in self.characters])}
* **aspect**: {self.aspect}
"""
        return text
    
    def format_dialogue(self) -> str:
        """
        format the dialogue for display
        """
        text = ""
        top = "\n\n".join([n.format() for n in self.narration if n.location == NarationLocation.TOP])
        bottom = "\n\n".join([n.format() for n in self.narration if n.location == NarationLocation.BOTTOM])
        dialogue = "\n\n".join([d.format() for d in self.dialogue])
        if top:
            text += top + f"\n\n"
        if dialogue:
            text += dialogue + "\n\n"
        if bottom:
            text += bottom
        return text

class CoverLocation(StrEnum):
    FRONT = "front"
    INSIDE_FRONT = "inside-front"
    INSIDE_BACK = "inside-back"
    BACK = "back"
    
class TitleBoardModel(BaseModel):
    id: str = Field(..., description="A unique identifier for the panel.   Default '<location>-cover'")
    location: CoverLocation = Field(..., description="The location of the cover.  front, inside-front, inside-back or back.  Default to front")
    issue: str = Field(..., description="The parent issue of the panel.   Default to empty string")
    series: str = Field(..., description="The parent series of the panel.   Default to empty string")
    characters: list[CharacterRef]  = Field(..., description="The names of the characters in the panel")
    style: str = Field(..., description="The art style of the panel.  Default to 'vintage-4-color'")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to portrait")
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel")
    foreground: str = Field(..., description="The foreground of the panel")
    background: str | None = Field(None, description="The background of the panel")
    image: str | None = Field(None, description="The selected image for this panel")

    def set_aspect(self, aspect: FrameLayout):
        """
        set the aspect ratio of the panel
        """
        self.aspect = aspect
        self.write()


    def path(self) -> str:
        """
        return the path to the panel model
        """
        location_id = self.location.value.replace("_", "-")
        return os.path.join(COMICS_FOLDER,self.series,"issues",self.issue,"covers",location_id)
    
    def filepath(self) -> str:
        """
        return the filepath to the panel model
        """
        return os.path.join(self.path(),"titleboard.json")
    
    def image_path(self) -> str:
        """
        return the path to the images for this panel
        """
        return os.path.join(self.path(), "images")

    def image_filepath(self) -> str | None:
        """
        return the filepath to the image
        """
        if self.image is None or self.image == "":
            return None
        return os.path.join(self.image_path(), f"{self.image}.jpg")
    
    def all_images(self) -> list[str]:
        """
        return a list of all the images in the panel
        """
        images_path = self.image_path()
        if not os.path.exists(images_path):
            return []
        return [f[:-4] for f in os.listdir(images_path) if f.endswith(".jpg")]
    
    def set_image(self, id: str):
        """
        set the image for the panel
        """
        self.image = id
        self.write()

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
    def read(cls, series: str, issue: str, location: CoverLocation):
        """
        read the panel model from a file
        """
        if isinstance(location, CoverLocation):
            location_id = location.value.replace("_", "-")
        else:
            # if it is a string then it is a location
            location_id = location.replace("_", "-")

        filepath = os.path.join(COMICS_FOLDER, series, "issues", issue, "covers", location_id, "titleboard.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)
        
    
