from typing import Optional
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import APPState
from schema import Publisher
from storage.generic import GenericStorage


def all_publishers_agent(state: APPState) -> Agent:
    from schema.series import Series
    from gui.selection import SelectionItem
    storage: GenericStorage = state.storage

    @function_tool
    def get_publisher_names() -> list[str]:
        """
        Get a list of all publisher names.
        
        Returns:
            A list of publisher names.
        """
        from schema.publisher import Publisher
        publishers = storage.read_all_publishers()
        return [publisher.name for publisher in publishers]
    
    @function_tool
    def get_publishers() -> list[Publisher]:
        """
        Get a list of all publisher the publishers in the database.
        
        Returns:
            A list of publisher names.
        """
        from schema.publisher import Publisher
        return storage.read_all_publishers()

    @function_tool
    def get_publisher_by_name(name: str) -> Publisher | None:
        """
        Get a publisher's definition by its name.
        
        Args:
            name: The name of the publisher.
        
        Returns:
            The Publisher object if found, otherwise None.
        """
        return storage.find_publisher(name=name)

    @function_tool
    def create_publisher(name: str, description: Optional[str]) -> Publisher | str | None:
        """
        Create a new publisher with the given name.
        
        Args:
            name: The name of the new publisher.
            description: An optional description of the publisher.

        
        Returns:
            The created Publisher object or an error message if the publisher already exists.
        """
        from schema.publisher import Publisher
        # check to see if the publisher already exists.
        if storage.find_publisher(name=name) is not None:
            logger.error(f"Publisher with name '{name}' already exists.")
            return f"Publisher with name '{name}' already exists."
        
        logger.info(f"The name '{name}' is available.")
        publisher = Publisher(name=name, logo=None, description=description, image=None, id=name.lower().replace(" ", "-"))
        storage.create_publisher(publisher)
        selection = state.selection
        new_itm = SelectionItem(name=publisher.name, id=publisher.id, kind='publisher')
        new_sel = [s for s in selection]+[new_itm]
        state.change_selection(new=new_sel, clear_history=False)
        state.is_dirty = True
        return publisher
    
    @function_tool
    def select_publisher(name: str) -> str:
        """
        Select a publisher by name.   This is a precursor for editing its 
        properties.
        
        Args:
            name: The name of the publisher to select.
        
        Returns:
            A status message indicating the result of the selection.
        """
        from schema.publisher import Publisher
        publisher = storage.find_publisher(name=name)
        if publisher is None:
            return f"Publisher '{name}' not found.  Maybe try looking at the list of publishers first?"
        sel_itm = SelectionItem(
            id=publisher.id,
            name=publisher.name,
            kind="publisher",
        )
        new_selection = state.selection + [sel_itm]
        state.change_selection(new=new_selection, clear_history=False)
        return f"Selected publisher: {publisher.name}"

    @function_tool
    def delete_publisher(name: str) -> str:
        """
        Delete a publisher by name.   YOU MUST CONFIRM THIS ACTION AS IT WILL DELETE ALL ASSOCIATED DATA.
        
        Args:
            name: The name of the publisher to delete.
        
        Returns:
            A status message indicating the result of the deletion.
        """
        pub = storage.find_publisher(name=name)
        if pub is None:
            return f"Publisher '{name}' not found.  Maybe try looking at the list of publishers first?"
        storage.delete_publisher(pub.id)

        # The selection does not need to change, but we do need to refresh the display to 
        # remove the deleted series from the list.
        state.is_dirty = True
        return f"Deleted publisher: {pub.name}"


    return Agent(
        name="Home Screen Assistant",
        instructions="""
        You are an interactive artistic assistant who helps human artists and creators manage
        comic book assests.  There are 3 top level concepts that you are concerned with:
        
        * Publishers:  These are the companies that publish comic books.   They often have specializations
            in terms of audience, artistic style and genera.  Real world examples of publishers include
            Marvel, DC, Image, Dark Horse, and many others.
        * Comic Series:  These are the series of comic books that are published by a publisher.   They
            frequently tell a story about a specific charaacter ( e.g. Spider man, Batman, etc. ) or groups
            of characters ( e.g. The Avengers, Justice League, etc. ).
        * Comic Styles:  These are the artistic styles that are used in a comic book series.   They
            define the visual language of the comic book, such as line style, inking tools, shading style,
            color palette, and more.   They are used by artists to ensure that the visual language of the
            comic is consistent throughout the series.

        You are capable of searching for, updating, deleting or creating any of these assets.   

        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools = [
            select_publisher,
            get_publisher_by_name,
            get_publishers,
            get_publisher_names,
            create_publisher,
            delete_publisher,
        ]
    )

