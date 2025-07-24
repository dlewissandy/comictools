import os
import json
from PIL import Image
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field
from schema.style.art import ArtStyle
from schema.style.character import CharacterStyle
from schema.style.dialog import BubbleStyles
from helpers.generator import invoke_generate_api
from helpers.constants import STYLES_FOLDER
from helpers.file import generate_unique_id

# TODO: Move these to models/style.py

BUBBLE_TEXT = {
    "chat": "Nice day, isn't it?",
    "narration": "Once upon a time...",
    "whisper": "Shhh.  It's a secret.",
    "thought": "I wonder what will happen...",
    "shout": "Watch out!",
    "sound-effect": "Boom!"
}

def render_dialog_example(style_description: str, bubble_style_description: str, bubble_type: str, bubble_text: str, save_path: str) -> str | None:
    """
    Render an example of a dialog bubble as an image.
    
    Returns:
        A message indicating the result of the operation.
    """
    # TODO: Move this to generators!   This is not a crud operatation.
    from helpers.generator import invoke_generate_image_api, IMAGE_QUALITY
    import os

    # Ensure the output path exists
    logger.debug(f"Ensuring dialog image path exists")
    os.makedirs(save_path, exist_ok=True)

    logger.debug(f"Preparing the image generation prompt")
    # Serialize the descripiton of the style
    prompt = f"""
       Render an example of the of a {bubble_type} dialog in the style described below.

       # ART STYLE
       {style_description}

       # DIALOG STYLE
       {bubble_style_description}

       # DIALOG TEXT
         {bubble_text}

       # OTHER INSTRUCTIONS
       * The image should have a 1:1 aspect ratio 
       * It should be a close-up of the dialog element, with no other elements in the image.
       * If there is a conflict between the art style and the dialog style, the dialog style should take precedence.
       """
    
    raw_img = invoke_generate_image_api(
        prompt=prompt,
        n=1,
        size="1024x1024",
        quality=IMAGE_QUALITY.HIGH,
    )

    # Save the image to a unique file
    logger.debug(f"generating unique ID for dialog bubble image")
    unique_id = generate_unique_id(save_path, create_folder=False)
    output_filepath = os.path.join(save_path, f"{unique_id}.jpg")
    logger.debug(f"Saving dialog bubble image to {output_filepath}")
    with open(output_filepath, "wb") as f:
        f.write(raw_img.getbuffer())
    logger.debug(f"Saved dialog bubble image to {output_filepath}")
    return unique_id

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

    # Todo: Move this to generators!   This is not a crud operatation.
    def render_art_style(self) -> str:
        """
        Render the art style as an image.
        
        Returns:
            A message indicating the result of the operation.
        """
        # TODO: Move this to generators!   This is not a crud operatation.
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

    # Todo: Move this to generators!   This is not a crud operatation.
    def render_character_style_example(self) -> str:
        """
        Render an example of the character style as an image.
        
        Returns:
            A message indicating the result of the operation.
        """
        from schema.character import render_character_image
        from agentic.constants import RUGOR_DESCRIPTION
        import os

        # Ensure the output path exists
        logger.debug(f"Ensuring character image path exists")
        save_path = self.image_path("character")
        os.makedirs(save_path, exist_ok=True)

        logger.debug(f"Preparing the image generation prompt")
        # Serialize the descripiton of the style
        style_description = self.format(include_bubble_styles=False, include_character_style=True)

        logger.debug(f"Rendering character image with style: {self.name}")
        img_id = render_character_image(character_name = "Rugor", character_description = RUGOR_DESCRIPTION, style_description = style_description, save_path = save_path)
        if img_id is None:
            self.set_image("character", img_id)
            return "success.  The new character style image has been saved."
        return "Character style image could not be rendered."
        

    

    # TODO: Move this to generators!   This is not a crud operatation.
    def render_dialog_example(self, bubble_type: str) -> str:
        """
        Render an example of a dialog bubble as an image.
        
        Returns:
            A message indicating the result of the operation.
        """
        style_description = self.format(include_bubble_styles=False, include_character_style=False)
        bubble_style = getattr(self.bubble_styles, bubble_type.replace("-", "_"), None)
        if bubble_style is None:
            msg = f"Invalid bubble type: {bubble_type}. Must be one of 'chat', 'narration', 'whisper', 'thought', 'shout', or 'sound-effect'."
            logger.error(msg)
            return msg
        
        bubble_style_description = bubble_style.format()

        bubble_text = BUBBLE_TEXT[bubble_type]

        save_path = self.image_path(f"{bubble_type}")

        img_id = render_dialog_example(style_description, bubble_style_description, bubble_type, bubble_text, save_path)
        if img_id is not None:
            self.set_image(bubble_type, img_id)
            return f"success.  The new {bubble_type} dialog bubble image has been saved."
        return f"{bubble_type} dialog bubble image could not be rendered."
        