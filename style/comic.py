import os
import json
from PIL import Image
from typing import Optional
from loguru import logger
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
    image: Optional[str] | dict[str, Optional[str]]= Field(..., description="A reference image for the comic style.  default to None")

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
    
    def filepath(self) -> str:
        return f"{self.path()}/style.json"
    
    def path(self) -> str:
        return f"{STYLES_FOLDER}/{self.id}"
    
    @classmethod
    def read_all(cls) -> list["ComicStyle"]:
        """
        read all comic styles from the styles folder
        """
        styles = []
        for item in os.listdir(STYLES_FOLDER):
            logger.debug(f"item: {item}")
            if item.startswith('.'):
                continue
            if os.path.isdir(os.path.join(STYLES_FOLDER, item)):
                # if it is a file then it is a style
                style = cls.read(id=item)
                if style:
                    styles.append(style)
        return styles

    def image_path(self, img_type: str = "art") -> str:
        """
        return the path to the image
        """
        if img_type not in ["art", "character", "chat-bubble", "narration-bubble", "whisper-bubble", "thought-bubble", "shout-bubble", "sound-effect-bubble"]:
            raise ValueError(f"Invalid image type: {img_type}. Must be one of 'art', 'character', 'chat-bubble', 'narration-bubble', 'whisper-bubble', 'thought-bubble', 'shout-bubble', or 'sound-effect-bubble'.")
        return os.path.join(self.path(), "images", f"{img_type.lower()}-style")

    def image_filepath(self, img_type: str = "art") -> str:
        """
        return the filepath to the image
        """
        image_path = self.image_path(img_type)
        if not isinstance(self.image, dict):
            return None
        img_id = self.image.get(img_type, None)
        if img_id is None:
            return None
        return os.path.join(image_path, f"{img_id}.jpg")
        
    def write_image(self, image: Image, type: str = "art") -> str | None:
        """
        write the image to the comic style folder.   Returns the id of the image
        if successful or None on failure.
        """
        is_dirty = False
        if self.image is None:
            self.image = {}
            is_dirty = True
        if type == "art":
            path = os.path.join(self.path(), "images")
        else:
            path = os.path.join(self.path(), "images", type.lower().replace("-", "_"))
        
        id = generate_unique_id(path, create_folder=True)
        filepath = os.path.join(path, f"{id}.jpg")
        image.save(filepath, "JPEG")

        if self.image_filepath(type) is None:
            # There is already an image for this style, so we are done.
            self.image[type] = id
            self.write()
        return id

    def render_art_style(self) -> str:
        """
        Render the art style as an image.
        
        Returns:
            A message indicating the result of the operation.
        """
        import os
        from helpers.generator import invoke_edit_image_api, IMAGE_QUALITY
        from helpers.file import generate_unique_id

        ref_img_filepath = "data/references/art-style.jpg"
        # If the reference image does not exist, return an error message
        if not ref_img_filepath:
            return "Reference image for art style does not exist."
        
        # Ensure the output path exists
        output_path = os.path.join(self.path(), "images", "art-style")
        os.makedirs(output_path, exist_ok=True)

        # Serialize the descripiton of the style
        instructions = self.format(include_bubble_styles=False, include_character_style=False)

        # Render the image using the OpenAI images API and the art style description
        logger.debug(f"Rendering art style image with style: {self.name}")
        prompt = f"""
Redraw the given image in the style described below.   Make no changes to the image
other than to redraw it in the specified style (e.g. do not change the composition,
add text or other elements).  The image should be as faithful a reproduction of
the original image as possible so that it can serve as a visual reference for the style.

# STYLE
{instructions}
"""

        raw_img = invoke_edit_image_api(
            ref_img_filepath,
            prompt,
            n = 1,
            size = "1536x1024",
            quality = IMAGE_QUALITY.HIGH,
            reference_images = [ref_img_filepath],
        )

        # Save the image to a unique file
        logger.debug(f"generating unique ID for art style image")
        unique_id = generate_unique_id(output_path, create_folder=False)

        output_filepath = os.path.join(output_path, f"{unique_id}.jpg")
        logger.debug(f"Saving art style image to {output_filepath}")
        with open(output_filepath, "wb") as f:
            f.write(raw_img.getbuffer())
        logger.debug(f"Saved art style image to {output_filepath}")
        result = "Art style image created successfully."
        self.set_image("art", unique_id)

        return f"Art style image saved to {output_filepath}."

    def set_image(self, image_type: str, id: str):
        """
        set the image for the comic style
        """
        if image_type not in ["art", "character", "chat-bubble", "narration-bubble", "whisper-bubble", "thought-bubble", "shout-bubble", "sound-effect-bubble"]:
            msg = f"Invalid image type: {image_type}. Must be one of 'art', 'character', 'chat-bubble', 'narration-bubble', 'whisper-bubble', 'thought-bubble', 'shout-bubble', or 'sound-effect-bubble'."
            logger.error(msg)
            return
    
        if self.image is None:
            self.image = {}
            self.image[image_type] = id
        elif isinstance(self.image, str):
            # if the image is a string, it is a path to the art style image
            self.image = {"art": self.image}
            self.image[image_type] = id
        elif isinstance(self.image, dict):
            # if the image is a dict, it is a path to the character style image
            self.image[image_type] = id
        
        self.write()

    def write(self):
        """
        write the comic style to a file
        """
        # create the directory if it doesn't exist
        os.makedirs(self.path(), exist_ok=True)
        # write the comic style to a file
        logger.debug(f"writing {self.filepath()}")
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read(cls, id: str):
        """
        read the comic style from a file
        """
        # read the comic style from a file
        filepath = f"{STYLES_FOLDER}/{id}/style.json"
        if not os.path.exists(filepath):
            logger.error(f"Comic style {id} not found in {STYLES_FOLDER}.")
            return None
        with open(f"{STYLES_FOLDER}/{id}/style.json", "r") as f:
            logger.debug(f"reading {f.name}")
            data = json.load(f)
            if not data.get("image", None):
                data["image"] = None
            return cls.model_validate(data)
        
    def format(self, include_bubble_styles: bool = True, include_character_style: bool = True) -> str:
        """
        format the comic style for display
        """
        result = f"""# Comic Style ({self.name})
    {self.description}""".strip()
        if self.art_style is not None:
            result += f"\n{self.art_style.format()}"
        if self.character_style is not None and include_character_style:
            result += f"\n{self.character_style.format()}"
        if self.bubble_styles is not None and include_bubble_styles:
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

    def all_images(self, img_type: str = "art") -> list[str]:
        """
        return all the identifiers for the images for the comic style
        """
        if img_type not in ["art", "character", "chat-bubble", "narration-bubble", "whisper-bubble", "thought-bubble", "shout-bubble", "sound-effect-bubble"]:
            raise ValueError(f"Invalid image type: {img_type}. Must be one of 'art', 'character', 'chat-bubble', 'narration-bubble', 'whisper-bubble', 'thought-bubble', 'shout-bubble', or 'sound-effect-bubble'.")
        
        image_path = self.image_path(img_type)
        if not os.path.exists(image_path):
            return []
        
        result = []
        for item in os.listdir(image_path):
            if item.endswith(".jpg"):
                result.append(item[:-4])
        
        return result