import os
from typing import Tuple, Optional, List
from gui.state import APPState
from helpers.constants import COMICS_FOLDER
from agents import Agent, function_tool, Tool
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from schema import CharacterVariant
from generators.character import render_character_image
from schema.style.comic import ComicStyle


def variant_agent(state: APPState, tools: dict[str, Tool]) -> Agent | str:
    storage = state.storage


    @function_tool
    def render_styled_image(style_name: str):
        """
        Render a styled image of the currently selected character variant.
        
        Args:
            style_name: The name of the style to apply to the character variant.
            NOTE: YOU SHOULD VERIFY THAT THE STYLE EXISTS BEFORE CALLING THIS FUNCTION.
        
        Returns:
            A string indicating the result of the rendering operation.
        """
        normalized_style_name = style_name.lower().strip()
        series_id=state.selection[-3].id
        character_id=state.selection[-2].id
        variant_id=state.selection[-1].id
        variant = CharacterVariant.read(
            series=series_id,
            character=character_id,
            id=variant_id
        )
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        
        all_styles = ComicStyle.read_all()
        names = [style.name.lower() for style in all_styles]

        if normalized_style_name not in names:
            return f"Style '{style_name}' not found.  Maybe it was one of these: {', '.join(names)}.   If any are a likely match, confirm with the user.  Otherwise, ask them to pick one of the available styles."

        style_id = normalized_style_name.replace(" ", "-")
        style = ComicStyle.read(id=style_id)
        if not style:
            return f"Style '{style_name}' could not be loaded."
        style: ComicStyle = style


        character_name = variant.character_id.replace('-', ' ').title()
        save_path = os.path.join(
            COMICS_FOLDER,
            series_id,
            "characters",
            character_id,
            variant.variant_id,
            "images",
            style_id
        )

        def format(variant: CharacterVariant, heading_level: int = 3) -> str:
            result = f"""{'#'*heading_level} Character Model ({variant.name})
    * **Name**: {variant.name}
    * **Race**: {variant.race}
    * **Age**: {variant.age}
    * **Height**: {variant.height}
    * **Gender**: {variant.gender}
    * **Description**: {variant.description}
    * **Attire**: {variant.attire}
            """.strip()
            if variant.appearance is not None and variant.appearance != "":
                result += f"\n* **Appearance**: {variant.appearance}"
            if variant.behavior is not None and variant.behavior != "":
                result += f"\n* **Behavior**: {variant.behavior}"
            return result + "\n\n            """


        image_id = render_character_image(
            character_name=character_name,
            character_description = format(variant),
            style_description = style.format(include_bubble_styles=False),
            save_path=save_path
        )

        variant.images[style_id] = image_id
        variant.write()
        state.is_dirty = True

    def _get_character_variant() -> Optional[CharacterVariant]:
        """
        Get the currently selected character variant.   On failure, this function will
        return a string indicating the error.
        """
        selection = state.selection
        character_id = selection[-2].id if len(selection) > 1 else None
        series_id = selection[-3].id if len(selection) > 2 else None

        if not selection or selection[-1].kind != "variant":
            return "No character variant selected. Please select a variant to delete."
        if not character_id:
            return "No character selected. Please select a character to delete a variant."
        if not series_id:
            return "No series selected. Please select a series to delete a variant."
        
        variant = CharacterVariant.read(
            id=selection[-1].id,
            character=character_id,
            series=series_id,
        )
        if not variant:
            return "Could not read the selected character variant."
        
        return variant


    @function_tool
    def delete_variant() -> str:
        """
        Delete the currently selected character variant.   NOTE: YOU MUST ASK FOR 
        CONFIRMATION BEFORE DELETING A VARIANT.
        
        Returns:
            A confirmation message indicating the variant was deleted successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return str
        variant.delete()
        state.change_selection(new=state.selection[:-1])  # Remove the deleted variant from selection
        state.write()
        return f"Variant {variant.name} deleted successfully."

    @function_tool
    def update_general_description(description: str) -> str:
        """
        Update the general description of the currently selected character variant.
        
        Args:
            description: The new general description for the character variant.
        
        Returns:
            A confirmation message indicating the description was updated successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        variant.description = description
        variant.write()
        state.is_dirty = True
        return f"General description for {variant.name} updated successfully."
    
    @function_tool
    def update_physical_appearance(appearance: str) -> str:
        """
        Update the physical appearance of the currently selected character variant.
        
        Args:
            appearance: The new physical appearance description for the character variant.
        
        Returns:
            A confirmation message indicating the appearance was updated successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        variant.appearance = appearance
        variant.write()
        state.is_dirty = True
        return f"Physical appearance for {variant.name} updated successfully."

    @function_tool
    def update_attire(attire: str) -> str:
        """
        Update the attire of the currently selected character variant.
        
        Args:
            attire: The new attire description for the character variant.
        
        Returns:
            A confirmation message indicating the attire was updated successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        variant.attire = attire
        variant.write()
        state.is_dirty = True
        return f"Attire for {variant.name} updated successfully."

    @function_tool
    def update_behavior(behavior: str) -> str:
        """
        Update the behavior of the currently selected character variant.
        
        Args:
            behavior: The new behavior description for the character variant.
        
        Returns:
            A confirmation message indicating the behavior was updated successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        variant.behavior = behavior
        variant.write()
        state.is_dirty = True
        return f"Behavior for {variant.name} updated successfully."


    @function_tool
    def update_race(race: str) -> str:
        """
        Update the race of the currently selected character variant.
        Args
            race: The new race description for the character variant.
        Returns:
            A confirmation message indicating the race was updated successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        variant.race = race
        variant.write()
        state.is_dirty = True

        return f"Race for {variant.name} updated successfully."

    @function_tool
    def update_gender(gender: str) -> str:
        """
        Update the gender of the currently selected character variant.
        Args
            gender: The new gender description for the character
        variant.
        Returns:
            A confirmation message indicating the gender was updated successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        variant.gender = gender
        variant.write()
        state.is_dirty = True

        return f"Gender for {variant.name} updated successfully."

    @function_tool
    def update_age(age: str) -> str:
        """
        Update the age of the currently selected character variant.
        
        Args:
            age: The new age description for the character variant.
        
        Returns:
            A confirmation message indicating the age was updated successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        variant.age = age
        variant.write()
        state.is_dirty = True

        return f"Age for {variant.name} updated successfully."
    
    @function_tool
    def update_height(height: str) -> str:
        """
        Update the height of the currently selected character variant.
        
        Args:
            height: The new height description for the character variant.
        
        Returns:
            A confirmation message indicating the height was updated successfully.
        """
        variant = _get_character_variant()
        if isinstance(variant, str):
            return variant
        variant: CharacterVariant = variant
        variant.height = height
        variant.write()
        state.is_dirty = True
        return f"Height for {variant.name} updated successfully."



    return Agent(
        name="Variant Assistant",
        instructions="""
        You are an interactive artistic assistant that helps create and edit 
        variations (variants) of characters models for comic books.   You specialize in creating detailed
        text descriptions of characters and their attributes to ensure that they
        are consistently represented regardless of the artist or writer.
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools=[
            # Context
            tools.get('get_current_selection', None),

            # Getters
            tools.get('find_variant', None),

            
            render_styled_image,
            delete_variant,
            
            # Updaters
            update_general_description,
            update_physical_appearance,
            update_attire,
            update_behavior,
            update_race,
            update_gender,
            update_age,
            update_height,
            ],
    )

