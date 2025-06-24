from nicegui import ui
from loguru import logger
from agents import Agent
from agents.items import TResponseInputItem
from storage.generic import GenericStorage

STATE_FILEPATH = 'state.json'
def elipsis(text: str, max_length: int = 50) -> str:
    """
    Truncate the text to a maximum length and add an ellipsis if it exceeds that length.
    
    Args:
        text: The text to truncate.
        max_length: The maximum length of the text.
        
    Returns:
        The truncated text with an ellipsis if it was truncated.
    """
    return text if len(text) <= max_length else text[:max_length] + '...'


class APPState:
    from gui.selection import SelectionItem
    # GUI CONTROLS
    breadcrumbs: ui.button_group
    details: ui.scroll_area
    history: ui.scroll_area
    user_input: ui.input
    send_button: ui.button
    
    def __init__(self, breadcrumbs, details, history, user_input, send_button, storage: GenericStorage, dark_mode: bool = False, selection: list[SelectionItem] = []):
        from generators import init_agents
        # GUI ELEMENTS
        self.breadcrumbs = breadcrumbs
        self.details = details
        self.history = history
        self.user_input = user_input
        self.send_button = send_button
        self._dark_mode = dark_mode

        # APPLICATION STATE
        self._is_dirty = False
        self._selection = selection
        self._dark_controller = ui.dark_mode()

        # Storage and logging must be initialized before agents
        self._storage = storage

        # AGENTS
        self._agents = init_agents(self)
        

        
    @property
    def storage(self) -> GenericStorage:
        """
        Get the current storage instance for the GUI state.
        
        Returns:
            The GenericStorage instance used for data persistence.
        """
        return self._storage
    

    @property
    def selection(self) -> list[SelectionItem]:
        """
        Get the current selection in the GUI state.
        
        Returns:
            A list of SelectionItem objects representing the current selection.
        """
        return self._selection

    @property
    def agents(self) -> dict[str, Agent]:
        """
        Get the current agents in the GUI state.
        
        Returns:
            A dictionary of Agent objects representing the current agents.
        """
        return self._agents
    


    @property
    def dark_mode(self) -> bool:
        """
        Get the current dark mode setting for the GUI state.
        
        Returns:
            A boolean indicating whether dark mode is enabled.
        """
        return self._dark_mode
    
    @dark_mode.setter
    def dark_mode(self, value: bool):
        """
        Set the dark mode for the GUI state.
        
        Args:
            value: A boolean indicating whether to enable dark mode.
        """
        logger.debug(f"Setting dark mode to {value}")
        self._dark_mode = value
        if value:
            self._dark_controller.enable()
        else:
            self._dark_controller.disable()
        self.write()
   
    @property
    def is_dirty(self) -> bool:
        """
        Get the current dirty state of the GUI.
        
        Returns:
            A boolean indicating whether the GUI state has unsaved changes.
        """
        return self._is_dirty

    @is_dirty.setter
    def is_dirty(self, value: bool):
        """
        Set the dirty state of the GUI.
        
        Args:
            value: A boolean indicating whether the GUI state has unsaved changes.
        """
        logger.debug(f"Setting is_dirty to {value}")
        self._is_dirty = value


    def clear_history(self):
        """
        Clear the chat history in the GUI state.

        Args:
            self: The GUI state containing the chat history.
        
        Returns:
            The cleared history to facilitate repopulation if needed.
        """
        logger.trace("Clearing history")
        self.history.clear()
        # TODO: re-enable the send button
        return self.history

    def clear_details(self):
        """
        Clear the details section in the GUI state.
        Args:
            self: The GUI state containing the details section.

        Returns:
            The cleared details to facilitate repopulation if needed.
        """
        logger.trace("Clearing details")
        self.details.clear()
        return self.details

    def get_transcript(self) -> list[TResponseInputItem]:
        """
        Serialize the messages from the GUI state into a list of dictionaries.
        
        Args:
            state: The GUI elements containing the messages.
        
        Returns:
            A list of openai messages.
        """
        def _get_transcript(elem: ui.element, name: str | None, sent = bool | None, indent:int= 0) -> list[dict]: 
            logger.debug(" "*indent +f"Processing message: {elem.tag}")
            name = name or elem.props.get( 'name', None)
            sent = sent if sent is not None else elem.props.get('sent', None)

            text_html = elem.props.get('text_html', None)
            text_html = text_html if text_html is not None else elem.props.get('content', text_html)
            text_html = text_html if text_html is not None else elem.props.get('innerHTML', text_html)
            if text_html is not None and name is not None:
                logger.debug(" "*indent +f"Found message: {name} - {elipsis(text_html)}")
                return [{
                    'name': name,
                    'text_html': text_html,
                    'sent': sent if sent is not None else False,
                }]
            
            if elem.default_slot.children is None:
                logger.debug(" "*indent +"No children in element: {elem.tag}")
                return []
            
            if len(elem.default_slot.children) == 0:
                logger.debug(" "*indent +f"zero children in element: {elem.tag}" )
                return []
            
            result = []
            for child in elem.default_slot.children:
                result.extend(_get_transcript(child, name=name, sent=sent, indent=indent+2))
            return result
        
        logger.trace("Serializing history")
        result =  _get_transcript(self.history, None, None) 
        logger.debug(f"Serialized history: {[{'name': msg.get('name', 'user'), 'text_html': elipsis(msg.get('text_html', ''))} for msg in result]}")
        return result
    
    def get_messages(self, role_map: dict[str,str] = {}) -> list[dict]:
        """
        Get the messages from the chat history in the GUI state.   This list can then be sent
        directly to an agent to generate a response
        
        Args:
            state: The GUI elements containing the messages.
        
        Returns:
            A list of dictionaries representing the messages in the chat history.
        """
        messages = []
        for msg in self.get_transcript( ):
            role = role_map.get(msg.get("name", "user").lower(), None)
            if role is None:
                logger.error(f"Unknown role in message: {msg}")
                continue
            content = msg.get("text_html", "")
            messages.append({"role": role, "content": content})
        return messages

    def restore_history(self, messages: list[dict]):
        """
        Restore the chat history from the GUI state.
        
        Args:
            state: The GUI elements containing the messages.
        """
        logger.trace("Restoring history")
        logger.debug(f"Restoring history with messages: {messages}")
        history: ui.scroll_area = self.history
        parent_container = history
        for message in messages:
            if not isinstance(message, dict):
                logger.warning(f"Skipping non-dict message: {message}")
                continue

            name = message.get('name', 'Unknown')
            text_html = message.get('text_html', '')
            sent = message.get('sent', False)

            if name in ["Tool Call", "Tool Output"] and parent_container == history:
                with history:
                    parent_container = ui.expansion("Thoughts", value=False).classes('w-full').classes("text-sm")
            elif name in ["You", "Bot"] and parent_container != history:
                parent_container = history

            # add the message to the history
            with parent_container:
                ui.chat_message(name=name, sent=sent, text=text_html, text_html=True).classes('w-full')

        # scroll to the bottom of the history
        history.value = 100

    def change_selection(self, new: list[SelectionItem], clear_history=True):
        """
        Change the current selection in the GUI state.
        
        Args:
            state: The GUI elements containing the selection.
            new: The new selection to set.
            clear_history: Whether to clear the history after changing the selection.
        """
        logger.debug(f"Changing selection to {new} with clear_history={clear_history}")
        old = self.selection
        if old == new:
            logger.debug("New selection is the same as the old selection. No changes made.")
            return

        self._selection = new

        # If required (like moving up in the hierarchy), we may need to clear the history.
        if clear_history and len(new) <= len(old):
            # TODO: if returning from a lower level, we may want to add additional dialog.
            # If we just are going up 1 level, and the last element in the old selection
            # has a kind that starts with "pick-", then we can assume that the user
            # has just picked an item, and we don't have to clear the history.
            if len(new) == len(old) - 1 and old[-1].kind.startswith("pick-"):
                logger.debug("Not clearing history because we are returning from a pick- selection.")
            else:
                logger.debug("Clearing history because we are moving up in the hierarchy.")
                self.clear_history()
        self.write()

        # Update the breadcrumbs and details
        self.breadcrumbs.clear()
        with self.breadcrumbs:
            breadcrumb_selector(self)
            for i,item in enumerate(self.selection[1:]):
                new_sel = self.selection[:i+2]
                ui.button(item.name).props('rounded').on_click(lambda _, new_sel=new_sel: self.change_selection(new=new_sel))

        self.refresh_details()

    def refresh_details(self):
        logger.trace("Refreshing details")
        logger.debug(f"SELECTION:{self.selection}")
        # These imports are here to avoid circular imports
        from schema import CoverLocation
        from gui.home import view_all_styles, view_all_series, view_all_publishers
        from gui.style import view_style, view_pick_style
        from gui.series import view_series
        from gui.character import view_character, view_character_reference
        from gui.issue import view_issue
        from gui.scene import view_scene
        from gui.panel import view_panel
        from gui.cover import view_cover
        from gui.publisher import view_publisher, view_pick_publisher
        from gui.style import view_pick_art_style_image
        from gui.reference_image import view_reference_image
        from gui.variant import view_character_variant
        from gui.styled_image import view_styled_image

        self.clear_details()
        selection = self.selection
        
        if selection == []:
            raise ValueError("Selection cannot be empty.  Please select an item first.")

        kind = selection[-1].kind
        
        match kind:
            case "all_series":
                return view_all_series(self)
            case "all_publishers":
                return view_all_publishers(self)
            case "all_styles":
                return view_all_styles(self)
            case "style":
                return view_style(self)
            case "art-style-image":
                return view_pick_art_style_image(self)
            case "series":
                return view_series(self)
            case "character":
                return view_character(self)
            case "issue":
                return view_issue(self)
            case "scene":
                return view_scene(self)
            case "panel":
                return view_panel(self)
            case "front-cover":
                return view_cover(self, location=CoverLocation.FRONT)
            case "back-cover":
                return view_cover(self, location=CoverLocation.BACK)
            case "inside-front-cover":
                return view_cover(self, location=CoverLocation.INSIDE_FRONT)
            case "inside-back-cover":
                return view_cover(self, location=CoverLocation.INSIDE_BACK)
            case "publisher":
                return view_publisher(self)
            case "pick-publisher":
                return view_pick_publisher(self)
            case "pick-style":
                return view_pick_style(self)
            case "character-reference":
                return view_character_reference(self)
            case "reference-image":
                return view_reference_image(self)
            case "variant":
                return view_character_variant(self)
            case "styled-image":
                return view_styled_image(self)
            case _:        
                # Handle other cases or return a default message
                self.clear_details()
                with self.details:
                    ui.markdown(f"No description available for this item. {kind}")
                    return    
                
            


    def write(self):
        logger.debug("Saving state to file")
    
        state_json = {
            "selection": [item.model_dump() for item in self.selection],
            "messages":  self.get_transcript(),
            "dark_mode": self.dark_mode
        }
        with open(STATE_FILEPATH, "w") as f:
            import json
            json.dump(state_json, f, indent=2)

    def init_breadcrumbs(self):
        """
        Initialize the breadcrumbs UI element.
        
        Returns:
            The initialized breadcrumbs UI element.
        """
        logger.debug("Initializing breadcrumbs")
        self.breadcrumbs = ui.button_group().classes('w-full flex-nowrap overflow-x-auto')
        with self.breadcrumbs:
            breadcrumb_selector(self)
        return self.breadcrumbs


def breadcrumb_selector(state: APPState):
    from gui.selection import SelectionItem

    selection = state.selection
    if selection == []:
        raise ValueError("Selection cannot be empty.  Please select an item first.")
    primary_selection = ui.dropdown_button(selection[0].name.title(), auto_close=True)
    with primary_selection:
        all_series = ui.item("Series")
        all_publishers = ui.item("Publishers")
        all_styles = ui.item("Styles")

    
    new_sel = [selection[0]]
    series_sel = [SelectionItem(kind="all_series", name="Series", id=None)]
    publishers_sel = [SelectionItem(kind="all_publishers", name="Publishers", id=None)]
    styles_sel = [SelectionItem(kind="all_styles", name="Styles", id=None)]

    primary_selection.on("click", lambda _, new_sel=new_sel: state.change_selection( new=new_sel, clear_history=True))
    all_series.on_click(lambda _, new_sel=series_sel: state.change_selection( new=new_sel, clear_history=True))
    all_publishers.on_click( lambda _, new_sel=publishers_sel: state.change_selection( new=new_sel, clear_history=True))
    all_styles.on_click( lambda _, new_sel=styles_sel: state.change_selection( new=new_sel, clear_history=True))
    return primary_selection





def set_dark_mode(state: APPState, value: bool):
    """
    A wrapper function to allow the property to be set from the GUI.
    
    Args:
        state: The GUI elements containing the dark mode setting.
        value: A boolean indicating whether to enable dark mode.
    """
    state.dark_mode = value
