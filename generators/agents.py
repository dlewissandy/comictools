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
    pass


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
