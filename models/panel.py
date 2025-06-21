import os
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field, computed_field
from enum import StrEnum
from models.character import CharacterModel, CharacterVariant
from models.bubble import Naration, NarationLocation, Dialogue, DialogueEmphasis
from style.comic import ComicStyle
from helpers.constants import PANELS_FOLDER, SCENES_FOLDER, COMICS_FOLDER
from helpers.image import load_b64_image, load_b64_images
from helpers.file import generate_unique_id

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
    
def frame_layout_to_dims(aspect: FrameLayout) -> str:
    """
    Convert a FrameLayout to a string representation of its dimensions.
    """
    if aspect == FrameLayout.LANDSCAPE:
        return "1536x1024"  # 3:2 aspect ratio
    elif aspect == FrameLayout.PORTRAIT:
        return "1024x1536"  # 2:3 aspect ratio
    else:
        return "1024x1024"  # Default to square for other cases

    


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
        
    def delete(self):
        """
        delete the panel model
        """
        import shutil
        shutil.rmtree(self.path(), ignore_errors=True)

    def render(self) -> str:
        """
        Render the cover for the currently selected comic book issue.
        
        Returns:
            A string indicating the status of the rendering operation.
        """
        from style.comic import ComicStyle      # Needed for style description
        from models.publisher import Publisher  # Needed for publisher logo
        from models.series import Series        # Needed for Series name
        from models.issue import Issue          # Needed for issue name, price, creative team, etc.
        from models.character import CharacterVariant # Needed for character models and images

        # Read the style, issue, series and characters
        try:
            style = ComicStyle.read(id=self.style)  # Ensure the style is loaded
            issue = Issue.read(id=self.issue, series_id=self.series)
            series = Series.read(id=self.series)
            characters = [CharacterVariant.read(series=self.series, character=char.character, id=char.variant) for char in self.characters]
        except Exception as e:
            logger.error(f"Error loading related models: {e}")
            return f"Error rendering cover: {e}"
        
        reference_image_filepaths = [ref.image_filepath() for ref in self.reference_images if ref.image_filepath() is not None]

        # If any of them didn't load, then we need to return a warning
        warnings = []
        if style is None:
            warnings.append(f"The style ({self.style}) does not exist.")
        if issue is None:
            warnings.append(f"The issue ({self.issue}) does not exist.")
        if series is None:
            warnings.append(f"The series ({self.series}) does not exist.")
            publisher = None
        else:
            publisher = Publisher.read(id=series.publisher)
            if publisher is None:
                warnings.append(f"The publisher ({series.publisher}) does not exist.")
            if not publisher.image_filepath() is None:
                reference_image_filepaths.append(publisher.image_filepath()) 
        for char, ref in zip(characters, self.characters):
            if char is None:
                warnings.append(f"The character variant ({ref.character}/{ref.variant}) in series {self.series} does not exist.")
            else:
                if char.image_filepath(self.style) is not None:
                    reference_image_filepaths.append(char.image_filepath(self.style))
        
        if publisher is None:
            warnings.append(f"The publisher ({series.publisher}) does not exist.")

        # Get the reference images
        for ref in reference_image_filepaths:
            if not os.path.exists(ref):
                warnings.append(f"Reference image {ref} does not exist.")

        if len(warnings) > 0:
            msg = f"errors encountered while rendering cover:\n {"\n".join(warnings)}"
            logger.error(msg)
            return msg
        
        location_name = self.location.value.replace("_", " ").title()

        character_information = ""
        if len(characters) > 0:
            for character in characters:
                character_information += character.format(heading_level=2) + "\n"
        # If we got here, then we have all the information that we need to render the cover.
        prompt = f"""
        Create a comic book {location_name} cover.   The image should be have a {self.aspect.value} orientation/aspect ratio.


# Series
* ** Title **: "{series.name}".   This should appear prominently across the top of the cover.
* ** Subtitle **: "{issue.name}".  This should appear in smaller font below the title.
{'* ** Price **: ' + str(issue.price) +".   Place below subtitle on left." if issue.price else ""}
{'* ** Issue Number **: ' + str(issue.issue_number) + ".   Place below subtitle on right." if issue.issue_number else ""}
{'* ** Issue Date **: ' + issue.publication_date + ".   Place below issue number right in small font." if issue.publication_date else ""}
{'* ** Artist **: ' + issue.artist + ".   Place in small font at bottom of image" if issue.artist else ""}
{'* ** Writer **: ' + issue.writer + ".   Place in small font at bottom of image" if issue.writer else ""}
{'* ** Colorist **: ' + issue.colorist + ".   Place in small font at bottom of image" if issue.colorist else ""}
{'* ** Creative Minds **: ' + issue.creative_minds + ".   Place in small font at bottom of image" if issue.creative_minds else ""}


{issue.format(heading_level=1)}

# Publisher
* ** Logo **: (PLACE IN SMALL SQUARE IN LOWER RIGHT CORNER) {publisher.logo} 

# Characters
{character_information}

# Style
{style.format(heading_level=1)}

# Cover Design
* ** Foreground **: {self.foreground}
{'* ** Background **: ' + self.background if self.background else ""}
"""

        from helpers.generator import invoke_edit_image_api, invoke_generate_image_api, decode_image_response
        try:
            if len(reference_image_filepaths) > 0:
                # We have to use the edit image API
                raw_image = invoke_edit_image_api(
                    prompt=prompt,
                    size=frame_layout_to_dims(self.aspect),
                    reference_images=reference_image_filepaths,
                )
            else:
                # We can use the generate image API
                raw_image = invoke_generate_image_api(
                    prompt=prompt,
                    size=frame_layout_to_dims(self.aspect)
                )
        except Exception as e:
            msg = f"Error generating cover image: {e}"
            logger.error(msg)
            return msg
        
        # Write the image bytes to the image path
        image_path = os.path.join(self.path(), "images")
        image_id = generate_unique_id(image_path, create_folder = False)
        image_filepath = os.path.join(self.image_path(), f"{image_id}.jpg")

        with open(image_filepath, "wb") as f:
            f.write(raw_image)
        self.set_image(image_id)
        self.write()
        return f"Cover rendered successfully for issue {issue.name} at location {location_name}."

        

        
