
from typing import Tuple
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import GUIState
from style.comic import ComicStyle
from style.art import ArtStyle
from style.character import CharacterStyle
from style.bubble import BubbleStyles, BubbleStyle

def style_agent(state: GUIState) -> Agent:


    def get_comic_style() -> ComicStyle:
        """
        Get the currently selected comic style.
        
        Returns:
            The ComicStyle object if found, otherwise None.
        """
        selection = state.get("selection")
        if selection and selection[-1].kind == "style":
            return ComicStyle.read(id=selection[-1].id)
        return None

    def get_style_by_name(name: str) -> ComicStyle | None:
        """
        Get a comic style by its name.
        
        Args:
            name: The name of the comic style.
        
        Returns:
            The ComicStyle object if found, otherwise None.
        """
        return ComicStyle.read(name.lower().replace(" ", "-"))
    
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
    def create_dialog_style_image(dialog_type: str) -> str:
        """
        Create an image for the dialog style of the currently selected comic style.
        
        Args:
            dialog_type: The type of dialog style to create an image for. Must be one of:
            "chat", "whisper", "shout", "thought", "sound_effect", "narration".
        
        Returns:
            A status message indicating the result of the operation.
        """
        style = get_comic_style()
        if style is None:
            return "No comic style selected."
        bubble_styles = style.bubble_styles
        if bubble_styles is None:
            return "No bubble styles defined for this comic style."
        
        bubble_style = getattr(bubble_styles, dialog_type, None)
        if bubble_style is None:
            return f"Invalid dialog type: {dialog_type}. Must be one of: chat, whisper, shout, thought, sound_effect, narration."
        
        img = bubble_styles.render(dialog_type)
        if img is None:
            return f"Could not render image for {dialog_type} dialog style."
        
        state["is_dirty"] = True
        return f"Image for {dialog_type} dialog style created and saved to {img}."

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
    def read_dialog_style( bubble_type: str ) -> BubbleStyles | None:
        """
        Read the dialog style of the currently selected comic style.  The dialog style
        defines the visual language used for dialog  in the comic book, such as font, fill color,
        and more.  It is used by artists to ensure that the text bubbles in a comic book have
        a consistent look and feel throughout the series.
        
        Args:
            bubble_type: The type of bubble style to read.  must be one of: "chat", "whisper", 
            "shout", "thought", "sound_effect", "narration".
        
        Returns:
            The BubbleStyles object if found, otherwise None.
        """
        style = get_comic_style()
        if style:
            if bubble_type not in ["chat", "whisper", "shout", "thought", "sound_effect", "narration"]:
                raise ValueError(f"Invalid bubble type: {bubble_type}. Must be one of: chat, whisper, shout, thought, sound_effect, narration.")
            return getattr(style.bubble_styles, bubble_type, None)
        return None

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
            get_description,
            update_description,
            read_art_style,
            update_art_style,
            read_character_style,
            # set_character_style,
            read_dialog_style,
            # set_dialog_style,
            # render_art_style_example,
            # render_character_style_example,
            # render_dialog_style_example
        ],
    )

