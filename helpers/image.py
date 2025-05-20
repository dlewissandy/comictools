import io
from enum import StrEnum
from PIL import Image
from base64 import b64encode, b64decode
from helpers.constants import MAX_LONGEST_SIDE, MAX_SHORTEST_SIDE

class IMAGE_QUALITY(StrEnum):
    """
    Enum for image quality.
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

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

def decode_image_response(response):
    """
    Decode the image response from the OpenAI API.
    """
    b64_img = response.data[0].b64_json
    # decode the base64 image
    img_data = b64decode(b64_img)
    buf = io.BytesIO(img_data)
    buf.seek(0)
    return buf    
