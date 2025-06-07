import os
import openai
from loguru import logger
from pydantic import BaseModel

from helpers.image import resize_image, decode_image_response, IMAGE_QUALITY

def invoke_generate_api(
        prompt: str, 
        model: str = "gpt-4o-mini", 
        temperature: float =0.7, 
        text_format: BaseModel | None=None, 
        image: str | None=None, 
        b64_image: str | None=None, 
        images: list[str] | None = None, 
        b64_images: list[str] | None = None):
    """
    Invoke the OpenAI API to generate a response based on the prompt.

    Args:
        prompt (str): The prompt to send to the OpenAI API.
        model (str): The model to use. Defaults to "gpt-4o-mini".
        temperature (float): The temperature to use. Defaults to 0.7.
        text_format (BaseModel | None): The text format to use. Defaults to None.
        image (str | None): The filepath of the image to use. Defaults to None.
    """
    openai.api_key = os.getenv('OPENAI_API_KEY')
    args = { 
        "model": model, 
        "temperature": temperature,
        }
    if text_format:
        args["text_format"] = text_format
    if b64_images is None:
        b64_images = []
    if image:
        b64_images.append(resize_image(image))
    if b64_image:
        b64_images.append(resize_image(b64_image))
    if images:
        for img in images:
            b64_images.append(resize_image(img))

    if len(b64_images) == 0:
        args["input"] = [{"role": "user", "content": prompt}]
    else:
        content = [{"type":"input_text", "text":prompt}]
        for b64_img in b64_images:
            content.append({"type":"input_image", "image_url":f"data:image/jpeg;base64,{b64_img}"})
        args["input"] = [{"role": "user", "content": content}]
    
    response = openai.responses.parse(**args)
    return response.output_parsed

def invoke_generate_image_api(prompt: str, model: str = "gpt-image-1", size: str = "1024x1024", n: int = 1, quality: IMAGE_QUALITY = IMAGE_QUALITY.LOW):
    """
    Invoke the OpenAI API to generate an image based on the prompt.
    """
    openai.api_key = os.getenv('OPENAI_API_KEY')
    response = openai.images.generate(
        model=model,
        prompt=prompt,
        n=n,
        size=size,
        moderation="low",
        quality= quality.name.lower(),
    )
    return decode_image_response(response)

def invoke_edit_image_api(images: list, prompt: str, mask: str | None = None, n: int = 1, size: str = "1024x1024", quality: IMAGE_QUALITY = IMAGE_QUALITY.LOW, reference_images: list[str] | None = None):
    """
    Invoke the OpenAI API to edit an image based on the prompt.
    """
    openai.api_key = os.getenv('OPENAI_API_KEY')
    args = { "prompt": prompt, "n": n, "size": size, "quality": quality.name.lower(), "model": "gpt-image-1" }
    if mask:
        args["mask"] = mask
    if reference_images:
        args["image"] = [open(filepath, "rb") for filepath in reference_images]
    response = openai.images.edit( **args)
    return decode_image_response(response)


