import os
import json
from pydantic import BaseModel, Field
from style.art import ArtStyle
from style.character import CharacterStyle
from style.bubble import BubbleStyles
from helpers.generator import invoke_generate_api
from helpers.constants import STYLES_FOLDER
from helpers.file import generate_unique_id

class ComicStyle(BaseModel):
    """
    Comic style guidelines for a comic series or title.
    """
    id: str = Field(
        ...,
        description="A unique identifier for the comic style.  e.g. 'vintage 4 color', etc.")
    name: str = Field(...,description="A short (1-5 word) name for the comic style.  e.g. 'vintage 4 color', etc.")
    description: str = Field(
        ..., description="One or two sentences describing the comic style capturing the overall aesthetic and tone, and perhaps defining titles in the genre."
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

    @classmethod
    def generate(cls, description: str):     
        """
        generate new comic style using generative AI
        """
        prompt = f"""Generate a comic style description from the following user description:

        # user description
        {description}

        Focus on sylistic details that would help a comic book artist maintain a consistent and
        recognizable style throughout a title, series or universe, and distinguish it from other styles.
        Be as concise as possible -- the summary should be in enough detail to allow the artist to reproduce
        the style consistently, but no more than that.
        """

        # Invoke the OpenAI API to generate a character description
        response = invoke_generate_api(prompt, text_format=cls)
        name=response.name
        response.id = generate_unique_id(STYLES_FOLDER, create_folder=False, name=name)
        response.write()
        return response
    
    def write(self):
        """
        write the comic style to a file
        """
        # create the directory if it doesn't exist
        os.makedirs(STYLES_FOLDER, exist_ok=True)
        # write the comic style to a file
        with open(f"{STYLES_FOLDER}/{self.id}.json", "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read(cls, id: str):
        """
        read the comic style from a file
        """
        # read the comic style from a file
        filepath = f"{STYLES_FOLDER}/{id}.json"
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Comic style {id} not found")
        with open(f"{STYLES_FOLDER}/{id}.json", "r") as f:
            data = json.load(f)
            return cls(**data)
        
    def format(self, include_bubble_styles: bool = True):
        """
        format the comic style for display
        """
        result = f"""
        # Comic Style ({self.name})\n
        {self.description}
        """.strip()
        if self.art_style is not None:
            result += f"\n{self.art_style.format()}"
        if self.character_style is not None:
            result += f"\n{self.character_style.format()}"
        if self.bubble_styles is not None:
            result += f"\n{self.bubble_styles.format()}"
        return result
    
    @classmethod
    def fromImage(cls, imagepaths: list[str] | str):
        """
        create a comic style from an image or list of images
        """
        prompt = """
        Generate a comic style description from the following example images.  Focus
        on stylistic details that would help a comic book artist maintain a consistent and
        recognizable style throughout a title, series or universe, and distinguish it from other styles.
        Be as concise as possible -- the summary should be in enough detail to allow the artist to reproduce
        the style consistently, but no more than that.
        """
        if isinstance(imagepaths, str):
            imagepaths = [imagepaths]
        
        # Invoke the OpenAI API to generate a character description
        response = invoke_generate_api(prompt, images=imagepaths, text_format=cls)
        response.id = generate_unique_id(STYLES_FOLDER, create_folder=True)
        response.write()
        return response
