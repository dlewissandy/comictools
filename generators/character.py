from typing import Tuple, Optional, List
from gui.state import APPState
from agents import Agent, function_tool
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from models.character import CharacterModel, CharacterVariant


def character_agent(state: APPState) -> Agent:

    def _get_character() -> Optional[CharacterModel]:
        """
        Get the currently selected character.   On failure, this function will
        return a string indicating the error.
        """
        selection = state.selection
        character_id = selection[-1].id if len(selection) > 0 else None
        series_id = selection[-2].id if len(selection) > 1 else None
        if character_id is None or series_id is None:
            return None
        return CharacterModel.read(series=series_id, id=character_id)
        
    @function_tool
    def get_current_character() -> CharacterModel:
        """
        Get the currently selected character.
        
        Returns:
            The currently selected character.
        """
        character = _get_character()
        if isinstance(character, str):
            raise ValueError(character)
        return character


    @function_tool
    def delete_current_character() -> str:
        """
        Delete the currently selected character.   NOTE: YOU MUST ASK FOR
        CONFIRMATION BEFORE DELETING A CHARACTER.   THIS OPERATION CANNOT BE UNDONE.
        
        Returns:
            A message indicating the result of the deletion operation.
        """
        import shutil
        character = _get_character()
        if character is None:
            return None
        
        character: CharacterModel = character
        state.change_selection(new=state.selection[:-1])  # Remove the deleted character from selection
        state.write()
        state.is_dirty = True
        return f"Character {character.name} deleted successfully."
    
    @function_tool
    def update_character_description(description: str) -> str:
        """
        Update the description of the currently selected character.
        
        Args:
            description: The new description for the character.
        
        Returns:
            A message indicating the result of the update operation.
        """
        character = _get_character()
        if character is None:
            return "No character selected."
        
        character.description = description
        character.write()
        state.is_dirty = True
        return f"Character {character.name} updated successfully with new description."

    @function_tool
    def get_variants() -> List[str]:
        """
        Get the list of character variants for the currently selected character.
        
        Returns:
            A list of variant names for the character.
        """
        character = _get_character()
        if character is None:
            return []
        
        return CharacterVariant.read_all(series=character.series, character=character.id)
    
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
        character = _get_character()
        if character is None:
            raise ValueError("No character selected.")
        
        variant = CharacterVariant(
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
        variant.write()
        state.is_dirty = True
        return variant


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
            get_current_character,
            update_character_description,

            delete_current_character,
            get_variants,
            create_variant,
            ],
    )

