import io
from loguru import logger
from pydantic import BaseModel
from enum import StrEnum
from PIL import Image
from base64 import b64encode, b64decode
from helpers.constants import MAX_LONGEST_SIDE, MAX_SHORTEST_SIDE
from io import BytesIO

class IMAGE_QUALITY(StrEnum):
    """
    Enum for image quality.
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class LoadImageResult(BaseModel):
    success: bool
    warnings: list[str]
    b64_images: list[str]

def load_b64_image(filepath: str) -> LoadImageResult:
    """
    Load an image from the given path and return the result as a base64 string.
    Args:
        filepath (str): The path to the image file.
    Returns:
        str: The base64 encoded string of the image.
    """

    try:
        with open(filepath, 'rb') as f:
            b64_image = b64encode(f.read()).decode('utf-8')
        return LoadImageResult(
            success=True,
            warnings=[],
            b64_images=[b64_image]
        )
    except Exception as e:
        msg = f"Error loading image from {filepath}: {e}"
        logger.error(msg)
        return LoadImageResult(success=False, warnings=[msg], b64_images=[])

def load_b64_images(filepaths: list[str]) -> LoadImageResult:
    """
    Load multiple images from the given paths and return the results as a list of base64 strings.
    Args:
        filepaths (list[str]): The list of paths to the image files.
    Returns:
        LoadImageResult: An object containing the success status, warnings, and base64 encoded images.
    """
    results = LoadImageResult(success=True, warnings=[], b64_images=[])

    for filepath in filepaths:
        result = load_b64_image(filepath)
        if not result.success:
            results.success = False
            results.warnings.extend(result.warnings)
        results.b64_images.extend(result.b64_images)

    return results

def resize_image(filepath: str) -> str:
    """
    Resize an image so that the longest size is less than 2000px and the shortest size is less than 768px.
    return the resized image as a base64 string.
    """
    # Open the image file

    with Image.open(filepath) as img:
        # Check if the image is already smaller than the max s        
        # Get the original size
        width, height = img.size

        # Calculate the new size
        if width > height:
            wratio = width / MAX_LONGEST_SIDE
            hratio = height / MAX_SHORTEST_SIDE
        else:
            wratio = width / MAX_SHORTEST_SIDE
            hratio = height / MAX_LONGEST_SIDE
        ratio = min(wratio, hratio)
        if ratio < 1:
            new_width = int(width / ratio)
            new_height = int(height / ratio)
            # Resize the image
            img = img.resize((new_width, new_height))

        # base64 encode the image, but do not save it to disk!
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        b64_image = b64encode(img_buffer.read()).decode('utf-8')

    return b64_image

def decode_image_response(response) -> bytes:
    """
    Decode the image response from the OpenAI API.
    """
    b64_img = response.data[0].b64_json
    # decode the base64 image
    return b64decode(b64_img)
