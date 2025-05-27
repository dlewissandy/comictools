from loguru import logger
from agents import Agent, function_tool
from generators.tools import (
    get_comic_style_names,
    get_comic_style_by_name,
    get_comic_series_names,
    get_comic_series_by_name,
    wrap_create_comic_series,
    get_publisher_by_name,
    get_publisher_names,
    wrap_create_publisher,
    wrap_render_logo,
)
from gui.state import GUIState
from style.art import ArtStyle
from style.character import CharacterStyle
from style.bubble import BubbleStyles
from style.comic import ComicStyle


LANGUAGE_MODEL = "gpt-4o-mini"

BOILERPLATE_INSTRUCTIONS = """
You are helpful and friendly, but can provide critical reivews
of content (no sugar coating) when needed.   You are concise and to the point,
and value accuracy above all else.   If ever you are unsure of what is being
requested, you ask clarifying questions.
"""

def home_agent(state: GUIState) -> Agent:
    return Agent(
        name="Home Screen Assistant",
        instructions="""
        You are an interactive artistic assistant who helps create, edit, and publish
        comic books.""" + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools=[get_comic_style_names, 
            get_comic_style_by_name,
            get_comic_series_names,
            get_comic_series_by_name,
            wrap_create_comic_series(state=state),
            get_publisher_by_name,
            get_publisher_names,
            wrap_create_publisher(state=state),
            ],
    )

def character_agent(state: GUIState) -> Agent:
    return Agent(
        name="Character Assistant",
        instructions="""
        You are an interactive artistic assistant who helps create, edit, and publish
        comic books.   You specialize on creating detailed descriptions of characters
        and their attributes to ensure that they are consistently represented regardless
        of the artist or writer.
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools=[get_comic_style_names, 
            get_comic_style_by_name,
            ],
    )

def cover_agent(state: GUIState) -> Agent:
    pass

def issue_agent(state: GUIState) -> Agent:
    pass

def panel_agent(state: GUIState) -> Agent:
    pass

def publisher_agent(state: GUIState) -> Agent:
    """
    Create an agent for the publisher assistant.
    """
    from models.publisher import Publisher

    def _get_publisher_attribute(attribute: str) -> str:
        """
        Get the specified attribute of the currently selected publisher.
        """
        selection = state.get("selection")
        if selection and selection[-1].kind == "publisher":
            publisher = Publisher.read(id=selection[-1].id)
            return getattr(publisher, attribute, "Currently selected publisher does not have a {attribute} attribute.")
        return "Something odd happened.  No publisher is currently selected."

    def _del_publisher_attribute(attribute: str) -> str:
        """
        Delete the specified attribute of the currently selected publisher.
        """
        selection = state.get("selection")
        if selection and selection[-1].kind == "publisher":
            publisher = Publisher.read(id=selection[-1].id)
            # set the attribute to None
            try:
                setattr(publisher, attribute, None)
                publisher.write()
            except Exception as e:
                # couldn't be set to None.   Set it to an empty string.
                setattr(publisher, attribute, "")
                publisher.write()
            state["is_dirty"] = True
            return f"{attribute} for {publisher.name} deleted."
        return "Something odd happened.  No publisher is currently selected."
    
    def _set_publisher_attribute(attribute: str, value: str) -> str:
        """
        Set the specified attribute of the currently selected publisher.
        """
        selection = state.get("selection")
        if selection and selection[-1].kind == "publisher":
            publisher = Publisher.read(id=selection[-1].id)
            setattr(publisher, attribute, value)
            publisher.write()
            state["is_dirty"] = True
            return f"{attribute} for {publisher.name} updated."
        return "Something odd happened.  No publisher is currently selected."

    @function_tool
    def get_publisher_id() -> str:
        """
        Get the ID of the currently selected publisher.
        """
        return _get_publisher_attribute("id")

    @function_tool
    def get_publisher_name() -> str:
        return _get_publisher_attribute("name")

    @function_tool
    def get_publisher_description() -> str:
        """
        Get the description of the currently selected publisher.
        """
        return _get_publisher_attribute("description")
    
    @function_tool
    def get_logo_description() -> str:
        """
        Get the logo description of the currently selected publisher.
        """
        return _get_publisher_attribute("logo")

    @function_tool
    def delete_publisher_description() -> str:
        """
        Delete the description of the currently selected publisher.
        NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        """
        return _del_publisher_attribute("description")

    @function_tool
    def delete_logo_description() -> str:
        """
        Delete the description of the currently selected publisher's logo.
        NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        """
        return _del_publisher_attribute("logo")
    
    @function_tool()
    def delete_publisher() -> str:
        """
        Delete the currently selected publisher.
        NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        """
        selection = state.get("selection")
        if selection and selection[-1].kind == "publisher":
            publisher = Publisher.read(id=selection[-1].id)
            publisher.delete()
            state["is_dirty"] = True
            state["selection"] = selection[:-1]
            return f"Publisher {publisher.name} deleted."
        return "Something odd happened.  No publisher is currently selected."
    
    @function_tool
    def update_publisher_description(value: str) -> str:
        """
        Update the description of the currently selected publisher.

        Args:
            value: The new description of the publisher.
        """
        return _set_publisher_attribute("description", value)

    @function_tool
    def update_logo_description(value: str) -> str:
        """
        Update the logo description of the currently selected publisher.

        Args:
            value: The new logo description of the publisher.
        """
        return _set_publisher_attribute("logo", value)

    @function_tool
    def render_logo() -> str:
        """
        Render the logo for the currently selected publisher
        
        Returns:
            A status message indicating the result of the rendering.
        """
        from models.publisher import Publisher
        selection = state.get("selection")
        kind = selection[-1].kind
        if kind != "publisher":
            msg = f"The selection is not a publisher: {kind}"
            logger.error(msg)
            return msg
        
        publisher_id = selection[-1].id
        publisher = Publisher.read(id=publisher_id)
        if publisher is None:
            msg = f"Publisher with ID '{publisher_id}' not found."
            logger.error(msg)
            return msg
        
        img = publisher.render()
        if img is None:
            msg = f"Logo for publisher '{publisher.name}' could not be rendered."
            logger.error(msg)
            return msg
        
        state["is_dirty"] = True        
        return f"The logo for publisher '{publisher.name}' has been rendered and is saved to {img}.jpg"


    return Agent(
        name="Publisher Assistant",
        instructions="""
        You are an interactive artistic assistant who helps edit the description of
        a currently selected publisher.   You specialize on creating detailed 
        descriptions of publishers and their attributes to ensure that they are 
        consistently represented regardless of the artist or writer.
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools=[
            get_publisher_id,
            get_publisher_name,
            get_publisher_description,
            get_logo_description,
            delete_logo_description,
            delete_publisher_description,
            update_publisher_description,
            update_logo_description,
            render_logo,
            ],
    )

def scene_agent(state: GUIState) -> Agent:
    pass

def series_agent(state: GUIState) -> Agent:
    pass

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
    def update_description(value: str) -> str:
        """
        Update the description of the currently selected comic style.
        
        Args:
            value: The new description for the comic style.
        
        Returns:
            A status message indicating the result of the operation.
        """
        style = get_comic_style()
        if style:
            style.description = value
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



def init_agents(state: GUIState) -> dict[str, Agent]:
    """
    Initialize the agents for the application.
    
    Args:
        state: The GUI state object.
    
    Returns:
        A dictionary of initialized agents.
    """
    agents = {
        "home": home_agent(state),
        "character": character_agent(state),
        "style": style_agent(state),
        "series": series_agent(state),
        "issue": issue_agent(state),
        "scene": scene_agent(state),
        "cover": cover_agent(state),
        "panel": panel_agent(state),
        "publisher": publisher_agent(state),
    }
    return agents
