from agentic.constants import LANGUAGE_MODEL
from agents import function_tool, RunContextWrapper
from gui.state import APPState
from schema.series import Series
from gui.selection import SelectionItem, SelectedKind
from schema.character import CharacterModel
from storage.generic import GenericStorage


@function_tool
def create_character_from_reference_image(
    wrapper: RunContextWrapper[APPState], 
    series_id: str,
    character_name: str, 
    reference_image: str
) -> str:
    """
    Create a new character in the currently selected comic series using a reference image.
    
    Args:
        character_name: The name of the character to create.
        reference_image: The filepath of the reference image to use for the character.
    
    Returns:
        A confirmation message indicating the character was created successfully.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage


    from helpers.generator import invoke_generate_api
    series = storage.read_object(cls=Series,primary_key = {"series_id": series_id})
    if not series:
        return f"Series with ID '{series_id}' not found."
    series: Series = series

    prompt = f"""Create a new CharacterModel for {character_name} in the {series.id} comic series using the reference image as a starting point."""
    character:CharacterModel = invoke_generate_api(
        prompt=prompt,
        model=LANGUAGE_MODEL,
        image=reference_image,
        text_format=CharacterModel
    )

    storage.create_object(data=character)    
    return f"Character '{character.name}' created successfully in series '{series.series_title}'."

