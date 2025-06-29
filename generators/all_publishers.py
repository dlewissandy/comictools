from typing import Optional
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool
from gui.state import APPState
from schema import Publisher
from storage.generic import GenericStorage


def all_publishers_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    from schema.series import Series
    from gui.selection import SelectionItem, SelectedKind
    storage: GenericStorage = state.storage

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
        publisher_id = name.lower().replace(" ", "-")
        if storage.read_object(cls=Publisher, primary_key={"publisher_id": publisher_id}) is not None:
            logger.error(f"Publisher with name '{name}' already exists.")
            return f"Publisher with name '{name}' already exists."
        
        logger.info(f"The name '{name}' is available.")
        publisher = Publisher(name=name, logo=None, description=description, image=None, id=name.lower().replace(" ", "-"))
        storage.create_publisher(publisher)
        selection = state.selection
        new_itm = SelectionItem(name=publisher.name, id=publisher.id, kind=SelectedKind.PUBLISHER)
        new_sel = [s for s in selection]+[new_itm]
        state.change_selection(new=new_sel, clear_history=False)
        state.is_dirty = True
        return publisher
    
    @function_tool
    def select_publisher(publisher_id: str) -> str:
        """
        Select a publisher by identifier.   This is a precursor for editing its 
        properties.
        
        Args:
            publisher_id: The identifier of the publisher to select.

        Returns:
            A status message indicating the result of the selection.
        """
        from schema.publisher import Publisher
        publisher = storage.read_object(cls=Publisher, primary_key={"publisher_id": publisher_id})
        if publisher is None:
            return f"Publisher '{publisher_id}' not found.  Maybe try looking at the list of publishers first?"
        sel_itm = SelectionItem(
            id=publisher.publisher_id,
            name=publisher.name,
            kind=SelectedKind.PUBLISHER,
        )
        new_selection = state.selection + [sel_itm]
        state.change_selection(new=new_selection, clear_history=False)
        return f"Selected publisher: {publisher.name}"

    @function_tool
    def delete_publisher(publisher_id: str) -> str:
        """
        Delete a publisher by identifier.   YOU MUST CONFIRM THIS ACTION AS IT WILL DELETE ALL ASSOCIATED DATA.

        Args:
            publisher_id: The identifier of the publisher to delete.
        
        Returns:
            A status message indicating the result of the deletion.
        """
        pub = storage.read_object(cls=Publisher, primary_key={"publisher_id": publisher_id})
        if pub is None:
            return f"Publisher '{name}' not found.  Maybe try looking at the list of publishers first?"
        storage.delete_publisher(pub.id)

        # The selection does not need to change, but we do need to refresh the display to 
        # remove the deleted series from the list.
        state.is_dirty = True
        return f"Deleted publisher: {pub.name}"
    
    return Agent(
        name="All Publishers Agent",
        instructions="""
        You are an interactive artistic assistant who helps human artists and creators manage
        comic book assests.  You are a specialist on comic book publishers.   You can help users
        understand, and modify your extensive database of comic book publishers.   
        
        You will always use your tools to perform actions when an appropriate tool is available.

        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools = [
            tools.get('get_current_selection', None),

            # Getters
            select_publisher,
            tools.get("get_all_publishers"),
            tools.get("find_publisher"),

            create_publisher,
            delete_publisher,
        ]
    )

