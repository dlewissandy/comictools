from loguru import logger
from typing import Tuple, Optional, List
from gui.state import APPState
from agents import Agent, function_tool, Tool
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from schema import CharacterModel, CharacterVariant, CharacterVariantMinimal
from helpers.generator import invoke_generate_image_api
from helpers.file import generate_unique_id
from gui.selection import SelectionItem
from storage.generic import GenericStorage
from generators.tools import normalize_id

def render_character_image(character_name: str, character_description: str, style_description: str, save_path: str):
    """
    generate an image of a character in the given style.

    Args:
        character_name (str): The name of the character.
        character_description (str): A description of the character.
        style_description (str): A description of the style.
        save_path (str): The path to save the image.

    Returns:
        str: The id of the generated image.
    """
    prompt = f"""
    Render a multi-angle character model of {character_name} using the following information:\n

    # Character Brief
    {character_description}

    # Artistic Style
    {style_description}

    # Guidelines
    * The image must have a landscape aspect ratio.
    * First row (75% of the image height), THREE poses of the character model:
      - front view
      - side view
      - back view
    * Maintain a neutral stance with neutral background, and ensure the character is fully visible in each pose without clipping
    * Second row (25% of image height) from left to right:
       - Face closeup view - joy
       - Face closeup view - anger
       - Face closeup view - fear
       - face closeup view - sadness
       - face closeup view - surprise
       - THE IMAGE LABEL: "{character_name}"
    * The facial closeup images should be BELOW the character model images, and should not overlap with the character model images.
    * ensure consistent appearance (color, accessories, clothing, weapons, physical features, etc) across all views.  Pay special attention to the facial closeup images,
       ensuring that the characters facial features (eyes, eye color, ears, teeth/tusks, hair, mouth, nose, etc) are consistent across all images.
    """
    
    logger.debug(f"Generating character image with prompt: {prompt}")
    raw_image = invoke_generate_image_api(prompt, n=1, size="1536x1024", quality=IMAGE_QUALITY.HIGH)
    logger.debug(f"Image generation complete.  Generating unique id for image.")
    image_id = generate_unique_id(save_path, create_folder=False)
    logger.debug(f"Unique id generated: {image_id}.  Saving image to {save_path}/{image_id}.jpg")
    save_filepath = f"{save_path}/{image_id}.jpg"
    with open(save_filepath, "wb") as f:
        f.write(raw_image)
    logger.debug(f"Image saved to {save_filepath} with id {image_id}")
    return image_id


def character_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    storage: GenericStorage = state.storage




    
    @function_tool
    def update_character_description(description: str) -> str:
        """
        Update the description of the currently selected character.
        
        Args:
            description: The new description for the character.
        
        Returns:
            A message indicating the result of the update operation.
        """
        series_id = state.selection[-2].id  # Assuming the second last item is the series
        character_id = state.selection[-1].id  # Assuming the last item is the character

        character = storage.find_character(series_id=series_id, character_id=character_id)
        if character is None:
            return "Can't update the current character.  Is one selected?"
        
        character.description = description
        storage.update_character(data = character)
        state.is_dirty = True
        return f"Character {character.name} updated successfully with new description."

    
    @function_tool
    def create_variant(name: str, race: str, gender: str, age: str, height: str, general_description: str, physical_appearance: str, attire: str, behavior: str) -> CharacterVariant:
        """
        Create a new character variant with the provided attributes.
        
        Args:
            name: The name of the variant.   This should be unique within the character's variants and should be short (1-3 words).
            general_description: A short 3-5 sentence description of the variant.   What does this variant represent?  How does it differ from other variants?  
            race: 1-5 words describing the race of the character variant.
            gender: 1-2 words describing the gender of the character variant.
            age: 1-5 words describing the relative age of the character variant (e.g. 'child', 'teen', 'adult', 'middle age', 'old', "ancient", etc).
            height: 1-5 words describing the height of the character variant. (e.g. 'short', 'average', 'tall', 'very tall', etc).  Alternatively, compare to size of another character or species.
            physical_appearance: 1-2 paragraphs describing the physical appearance details this variant of the character.
            attire: 1-2 paragraphs describing the attire of the character variant
            behavior: 1-2 paragraphs describing the behavior of the character variant.
            
        NOTE: the descriptions should focus on attiributes that would help artists and writers accurately depict the character variant,
        and will serve as a reference template for depicting the character variant in comic book panels.   Include enough detail so that
        the character variant can be consistenlty represented, even by artists who have never seen the character before.
        
        Returns:
            The newly created CharacterVariant object.
        """
        character_id = state.selection[-1].id  # Assuming the last item is the character
        series_id = state.selection[-2].id  # Assuming the second last item is the

        series = storage.read_series(id=series_id)
        if series is None:
            raise ValueError("The series {series_id} does not exist.  Try checking the list of series first to see if maybe you misspelled it?")
        character = storage.find_character(series_id=series_id, character_id=character_id)
        if character is None:
            raise ValueError(f"The character {character_id} does not exist in series {series_id}.  Try checking the list of characters first to see if maybe you misspelled it?")
        
        character: CharacterModel = character
        variant = CharacterVariant(
            id=normalize_id(name),
            series=character.series,
            character=character.id,
            name=name,
            race=race,
            gender=gender,
            age=age,
            height=height,
            description=general_description,
            appearance=physical_appearance,
            attire=attire,
            behavior=behavior,
            images = {}
        )
        storage.create_character_variant(variant)
        sel_item = SelectionItem( id = variant.id, name=variant.name, kind="variant")
        state.selection.append(sel_item)  # Add the new variant to the selection
        state.write()
        state.is_dirty = True
        return variant


    # @function_tool
    # def create_variant_from_image(variant_name: str, image_path: str) -> CharacterVariant | str:
    #     """
    #     Create a new character variant from a reference image.
        
    #     Args:
    #         variant_name: The name of the variant.   This should be unique within the character's variants and should be short (1-3 words).
    #         image_path: The path to the image file to use as a reference for the variant.
        
    #     Returns:
    #         The newly created CharacterVariant object or an error message if the image could not be processed.
    #     """
    #     from helpers.generator import invoke_generate_api
    #     character = _get_character()
    #     if character is None:
    #         return "No character selected."
                
    #     prompt = f"""Create a variant of the character {character.name} in the {character.series} comic sereis using the provided image as a reference."""
    #     minimal:CharacterVariantMinimal = invoke_generate_api(
    #         prompt=prompt,
    #         image=image_path,
    #         model=LANGUAGE_MODEL,
    #         text_format=CharacterVariantMinimal
    #     )
    #     variant = CharacterVariant(
    #         series=character.series,
    #         character=character.id,
    #         name=variant_name,
    #         race=minimal.race,
    #         gender=minimal.gender,
    #         age=minimal.age,
    #         height=minimal.height,
    #         description=minimal.description,
    #         appearance=minimal.appearance,
    #         attire=minimal.attire,
    #         behavior=minimal.behavior,
    #         images = {}
    #         )

    #     variant.write()
    #     sel_item = SelectionItem( id = variant.id, name=variant.name, kind="variant")
    #     state.selection.append(sel_item)  # Add the new variant to the selection
    #     state.write()
    #     state.is_dirty = True
    #     return variant
    
    # @function_tool
    # def describe_image(image_path: str) -> str:
    #     """
    #     Describe the provided image in sufficient detail that it could be used
    #     to create a character variant.
        
    #     Args:
    #         image_path: The path to the image file to describe.
        
    #     Returns:
    #         A description of the image.
    #     """
    #     from helpers.generator import invoke_generate_api
    #     prompt = f"""Describe character in the given image in detail.  Your description
    #        should focus on visual elements that would be necessary for an artist to recreate
    #        the character.   For example, what is their physical appearance, age, stature, 
    #        attire.   Do they have any defining features, accessories or mannerisms.  Your 
    #        description should be exhaustive."""
    #     description = invoke_generate_api(
    #         prompt=prompt,
    #         image=image_path,
    #         model=LANGUAGE_MODEL
    #     )
    #     return description

    return Agent(
        name="Character Assistant",
        instructions="""
        You are an interactive artistic assistant who helps create, edit, and publish
        comic books.   You specialize on creating detailed descriptions of characters
        and their attributes to ensure that they are consistently represented regardless
        of the artist or writer.
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools=[
            # Navigation tools
            tools.get("get_current_selection", None),

            # Query Tools
            tools.get("find_character", None),
            tools.get("find_series", None),
            tools.get("find_all_characters", None),
            tools.get("find_all_variants", None),
        
            # describe_image,
            update_character_description,

            tools.get("delete_character", None),
            create_variant,
            # create_variant_from_image
            ],
    )

