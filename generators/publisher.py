from typing import Tuple, Optional, List
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool
from gui.state import APPState
import os
from gui.selection import SelectionItem, SelectedKind


def publisher_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    """
    Create an agent for the publisher assistant.
    """
    from schema.publisher import Publisher

    def _get_publisher() -> Optional[Publisher]:
        """
        Get the currently selected publisher.
        """
        selection = state.selection
        if selection and selection[-1].kind == SelectedKind.PUBLISHER:
            return Publisher.read(id=selection[-1].id)
        return None

    def _get_publisher_attribute(attribute: str) -> str:
        """
        Get the specified attribute of the currently selected publisher.
        """
        publisher = _get_publisher()
        if publisher:
            return getattr(publisher, attribute, "Currently selected publisher does not have a {attribute} attribute.")
        return "Something odd happened.  No publisher is currently selected."

    def _set_publisher_attribute(attribute: str, value: str) -> str:
        """
        Set the specified attribute of the currently selected publisher.
        """
        publisher = _get_publisher()
        if not publisher:
            return "Something odd happened.  No publisher is currently selected."
        setattr(publisher, attribute, value)
        publisher.write()
        state.is_dirty = True
        return f"{attribute} for {publisher.name} updated."
        
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

    
    @function_tool()
    def delete_publisher() -> str:
        """
        Delete the currently selected publisher.
        NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        """
        selection = state.selection
        publisher = _get_publisher()
        if not publisher:
            return "Something odd happened.  No publisher is currently selected."  
        publisher.delete()
        state["is_dirty"] = True
        state.change_selection(selection[:-1])
        state.write()
        return f"Publisher {publisher.name} deleted."
    
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
        from schema.publisher import Publisher
        selection = state.selection
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

    @function_tool
    def delete_logo_image() -> str:
        """
        Delete the logo image for the current publisher.  NOTE: YOU MUST ASK FOR CONFIRMATION BEFORE YOU DO THIS.  IT IS DESTRUCTIVE AND IRREVERSIBLE.
        """
        publisher = _get_publisher()
        if not publisher:
            return "Something odd happened.  No publisher is currently selected."
        # if the images are not a dictionary, return an error message
        if publisher.image is None:
            return "No logo image to delete."
        # otherwise, delete the image.
        image_filepath = publisher.image_filepath()
        publisher.image = None
        if not os.path.exists(image_filepath):
            return "The file does not exist.  Nothing to delete."
        os.remove(image_filepath)
        publisher.write()
        state["is_dirty"] = True
        return f"logo image for {publisher.name} deleted."


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
            tools.get('get_current_selection', None),

            tools.get('find_publisher', None),
            
            get_publisher_description,
            get_logo_description,
            delete_logo_image,
            delete_publisher,
            update_publisher_description,
            update_logo_description,
            render_logo,
            ],
    )

