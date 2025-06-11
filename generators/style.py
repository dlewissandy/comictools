
from typing import Tuple
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import APPState
from style.comic import ComicStyle
from style.art import ArtStyle
from style.bubble import DialogType
from style.character import CharacterStyle
from style.bubble import BubbleStyles, BubbleStyle
import os
from loguru import logger

def style_agent(state: APPState) -> Agent:
    
    def get_comic_style() -> ComicStyle:
        """
        Get the currently selected comic style.
        
        Returns:
            The ComicStyle object if found, otherwise None.
        """
        selection = state.selection
        if selection and selection[-1].kind == "style":
            return ComicStyle.read(id=selection[-1].id)
        return None
    
    @function_tool
    def get_description() -> str:
        """
        Get the description of the currently selected comic style.
        
        Returns:
            The description of the comic style if found, otherwise a message indicating no selection.
        """
        style = get_comic_style()
        if style:
            return style.description
        return "No comic style currently selected."

    @function_tool
    def update_description(new_description: str) -> str:
        """
        Update the description of the currently selected comic style.
        
        Args:
            value (string): The new description for the comic style.
        
        Returns:
            A status message indicating the result of the operation.
        """
        style = get_comic_style()
        if style:
            style.description = new_description
            style.write()
            state["is_dirty"] = True
            return f"Description for {style.name} updated."
        return "No comic style selected."
    
    @function_tool
    def read_art_style() -> ArtStyle | None:
        """
        Read the art style of the currently selected comic style.  The art style
        defines the visual aspects of the comic book, such as line style, inking tools,
        shading style, color palette, and more.  It is used by artists to ensure that
        the visual language of the comic is consistent throughout the series.
        
        Returns:
            The ArtStyle object if found, otherwise None.
        """
        style = get_comic_style()
        if style:
            return style.art_style
        return None


    @function_tool
    def update_art_style(
            line_styles: str | None = None,
            inking_tools: str | None = None,
            shading_style: str | None = None,
            color_palette: str | None = None,
            spot_colors: str | None = None,
            registration: str | None = None,
            lettering_style: str | None = None,
    ) -> str:
        """
        Update the art style of the currently selected comic style.
        
        Args:
            line_styles: The line styles used in the comic book.
            inking_tools: The inking tools used in the comic book.
            shading_style: The shading style used in the comic book.
            color_palette: The color palette used in the comic book.
            spot_colors: The spot colors used in the comic book.
            registration: The registration method used in the comic book.
            lettering_style: The lettering style used in the comic book.
        
        Returns:
            A status message indicating the result of the operation.
        """
        style = get_comic_style()
        if style is None:
            return "No comic style selected."
        art_style = style.art_style
        
        if line_styles is not None:
            art_style.line_styles = line_styles
        if inking_tools is not None:
            art_style.inking_tools = inking_tools
        if shading_style is not None:
            art_style.shading_style = shading_style
        if color_palette is not None:
            art_style.color_palette = color_palette
        if spot_colors is not None:
            art_style.spot_colors = spot_colors
        if registration is not None:
            art_style.registration = registration
        if lettering_style is not None:
            art_style.lettering_style = lettering_style
        if any([line_styles, inking_tools, shading_style, color_palette, spot_colors, registration, lettering_style]):
            style.write()
            state["is_dirty"] = True
            return f"Art style for {style.name} updated."
        return "No comic style selected."

    @function_tool
    def read_character_style() -> CharacterStyle | None:
        """
        Read the character style of the currently selected comic style.  The character style
        defines the visual aspects of characters in the comic book, such as head to body ratio,
        limb proportions, eye style, and more.  It is used by artests to ensure that all the
        characters in a comic book have the same look and feel, and that they are consistent
        throughout the series.
        
        Returns:
            The CharacterStyle object if found, otherwise None.
        """
        style = get_comic_style()
        if style:
            return style.character_style
        return None

    @function_tool
    def read_dialog_style( dialog_type: DialogType ) -> BubbleStyles | None:
        """
        Read one of the dialog styles (chat, whisper, shout, thought, sound-effect
        , narration) of the currently selected comic style.  The dialog style
        defines the visual language used for dialog  in the comic book, such as font, fill color,
        and more.  It is used by artists to ensure that the text bubbles in a comic book have
        a consistent look and feel throughout the series.
        
        Args:
            dialog_type: The type of dialog style to read.
        
        Returns:
            The BubbleStyles object if found, otherwise None.
        """
        style = get_comic_style()
        if style:
            dialog_style = getattr(style.bubble_styles, dialog_type.value.replace("-", "_"), None)
            return dialog_style
        return None

    @function_tool
    def render_art_style_example() -> Tuple[str, str]:
        """
        Render an example of the art style for the currently selected comic style.
        
        Returns:
            A tuple containing the image filepath and a description of the art style.
        """
        style = get_comic_style()
        if style:
            return style.render_art_style()
        return None, "No comic style selected."

    @function_tool
    def delete_art_style_example() -> str:
        """
        Delete the example of the art style for the currently selected comic style.
        THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
        THIS FUNCTION.
        
        Returns:
            A status message indicating the result of the operation.
        """
        style = get_comic_style()
        # if there is no style selected, return an error message
        if not style:
            return "No comic style selected."
        # if the images are not a dictionary, return an error message
        if not isinstance(style.image, dict):
            return "No art style example image to delete."
        # if there is no art style example image selected, return an error message.
        image = style.image.get("art",None)
        if not image:
            return "No art style example image to delete."
        # otherwise, delete the art style example image.
        style.image["art"] = None
        image_filepath = os.path.join(style.image_path(img_type="art"), f"{image}.jpg")
        if not os.path.exists(image_filepath):
            return "The file does not exist.  Nothing to delete."
        os.remove(image_filepath)
        style.write()
        state["is_dirty"] = True
        return f"Art style example for {style.name} deleted."
    
    @function_tool
    def delete_character_style_example() -> str:
        """
        Delete the example of the character style for the currently selected comic style.
        THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
        THIS FUNCTION.
        
        Returns:
            A status message indicating the result of the operation.
        """
        style = get_comic_style()
        # if there is no style selected, return an error message
        if not style:
            return "No comic style selected."
        # if the images are not a dictionary, return an error message
        if not isinstance(style.image, dict):
            return "No character style example image to delete."
        # if there is no art style example image selected, return an error message.
        image = style.image.get("character",None)
        if not image:
            return "No character style example image to delete."
        # otherwise, delete the character style example image.
        style.image["character"] = None
        image_filepath = os.path.join(style.image_path(img_type="character"), f"{image}.jpg")
        if not os.path.exists(image_filepath):
            return "The file does not exist.  Nothing to delete."
        os.remove(image_filepath)
        style.write()
        state["is_dirty"] = True
        return f"Character style example for {style.name} deleted."
    
    @function_tool
    def delete_dialog_style_example(dialog_type: DialogType) -> str:
        """
        Delete the example for one of the dialog styles (chat, whisper, shout, 
        thought, sound-effect, narration) for the currently selected comic style.
        THIS IS IRREVERSIBLE.  YOU MUST ASK THE USER TO CONFIRM PRIOR TO CALLING
        THIS FUNCTION.
        
        Returns:
            A status message indicating the result of the operation.
        """
        style = get_comic_style()
        # if there is no style selected, return an error message
        if not style:
            return "No comic style selected."
        # if the images are not a dictionary, return an error message
        if not isinstance(style.image, dict):
            return "No dialog style example image to delete."
        # if there is no art style example image selected, return an error message.
        image = style.image.get(f"{dialog_type.value}",None)
        if not image:
            return "No chat style example image to delete."
        # otherwise, delete the character style example image.
        style.image[dialog_type.value] = None
        image_filepath = os.path.join(style.image_path(img_type=dialog_type.value), f"{image}.jpg")
        if not os.path.exists(image_filepath):
            return "The file does not exist.  Nothing to delete."
        os.remove(image_filepath)
        style.write()
        state["is_dirty"] = True
        return f"Character style example for {style.name} deleted."
        
    @function_tool
    def render_character_style_example() -> str:
        """
        Render an example of the character style for the currently selected comic style.
        if this runs successfully, it will create a new image and select it as the current
        example image for the character style
        
        Returns:
            A string indicating the result of the operation.
        """
        style = get_comic_style()
    
        if style:
            result = style.render_character_style_example()
            state["is_dirty"] = True
            return result
        return "No style is selected, or the style does not exist."

    @function_tool()
    def delete_style() -> str:
        """
        Delete the current style (with its associated art, character and dialog styles).
        NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        """
        selection = state.selection
        style = get_comic_style()
        if not style:
            logger.error("No style is currently selected.")
            return "Something odd happened.  No style is currently selected."  
        style.delete()
        state["is_dirty"] = True
        state.change_selection(selection[:-1])
        return f"Style {style.name} deleted."

    def render_dialog_example(state, bubble_type: str) -> str:
        """
        Render an example of a dialog bubble as an image.
        
        Returns:
            A message indicating the result of the operation.
        """
        style = get_comic_style()
        if style:
            img_id = style.render_dialog_example(bubble_type=bubble_type)
            state["is_dirty"] = True
            return f"Dialog bubble example rendered and saved to {img_id}.jpg"
        return "No comic style selected."

    @function_tool
    def render_chat_dialog_example() -> str:
        """Render an example image of the chat dialog style for the currently selected comic style.
        
        Returns:
            A message indicating the result of the operation.
        """
        return render_dialog_example(state, bubble_type="chat")
    
    @function_tool
    def render_whisper_dialog_example() -> str:
        """Render an example image of the whisper dialog style for the currently selected comic style.
        
        Returns:
            A message indicating the result of the operation.
        """
        return render_dialog_example(state, bubble_type="whisper")
    
    @function_tool
    def render_shout_dialog_example() -> str:
        """Render an example image of the shout dialog style for the currently selected comic style.
        
        Returns:
            A message indicating the result of the operation.
        """
        return render_dialog_example(state, bubble_type="shout")
    
    @function_tool
    def render_thought_dialog_example() -> str:
        """Render an example image of the thought dialog style for the currently selected comic style.
        
        Returns:
            A message indicating the result of the operation.
        """
        return render_dialog_example(state, bubble_type="thought")
    
    @function_tool
    def render_sound_effect_dialog_example() -> str:
        """Render an example image of the sound effect dialog style for the currently selected comic style.
        
        Returns:
            A message indicating the result of the operation.
        """
        return render_dialog_example(state, bubble_type="sound-effect")
    
    @function_tool
    def render_narration_dialog_example() -> str:
        """Render an example image of the narration dialog style for the currently selected comic style.
        Returns:
            A message indicating the result of the operation.
        """        
        
        return render_dialog_example(state, bubble_type="narration")

    @function_tool
    def update_dialog_style(dialog_type: DialogType, dialog_style: BubbleStyle) -> str:
        """
        Update the dialog style for one of the dialog types (chat, whisper, shout, thought, sound-effect
        , narration).
        
        Args:
            dialog_type: The type of dialog style to update.
            bubble_style: The value of the new dialog style.
        """
        style = get_comic_style()
        if style is None:
            logger.error("No comic style selected.")
            return "No comic style selected."
        dialog_type = dialog_type.value.replace("-", "_")
        old_style = getattr(style.bubble_styles, dialog_type, None)
        if old_style is None:
            logger.debug(f"Unrecognized dialog type: {dialog_type}.")
            return f"Unrecognized dialog type: {dialog_type}."
        
        bubble_styles = style.bubble_styles
        setattr(bubble_styles, dialog_type, dialog_style)
        logger.debug(f"Updated dialog style for {dialog_type}: {dialog_style}")
        style.write()
        state["is_dirty"] = True
        return f"Dialog style for {style.name} updated."

    return Agent(
        name="Style Assistant",
        instructions="""
        You are an interactive artistic assistant who helps create, edit, and publish
        comic books.   You specialize on creating detailed descriptions of art, character,
        and dialog styles to ensure that they are consistently represented
        regardless of the artist or writer.
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools=[
            # UPDATERS
            update_description,
            update_art_style,
            update_dialog_style,
            
            # READ
            get_description,
            read_art_style,
            read_character_style,
            read_dialog_style,
            # RENDER
            render_chat_dialog_example,
            render_whisper_dialog_example,
            render_shout_dialog_example,
            render_thought_dialog_example,
            render_sound_effect_dialog_example,
            render_narration_dialog_example,
            render_art_style_example,
            render_character_style_example,
            # DELETE
            delete_style,
            delete_art_style_example,
            delete_character_style_example,
            delete_dialog_style_example


        ],
    )

