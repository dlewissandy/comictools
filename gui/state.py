from nicegui import ui
from agents import Agent
from agents.items import TResponseInputItem
from loguru import logger

STATE_FILEPATH = 'state.json'

class APPState:
    from gui.selection import SelectionItem
    # GUI CONTROLS
    breadcrumbs: ui.button_group
    details: ui.scroll_area
    history: ui.scroll_area
    user_input: ui.input
    send_button: ui.button

    
    def __init__(self, breadcrumbs, details, history, user_input, send_button, dark_mode: bool = False, selection: list[SelectionItem] = []):
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

        # AGENTS
        self._agents = init_agents(self)
        
        

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
        def get_message(elem: ui.element, name: str | None, sent = bool | None) -> list[dict]: 
            logger.debug(f"Processing message: {elem.tag}")
            name = name or elem.props.get( 'name', None)
            sent = sent if sent is not None else elem.props.get('sent', None)

            text_html = elem.props.get('text_html', None)
            text_html = text_html if text_html is not None else elem.props.get('content', text_html)
            text_html = text_html if text_html is not None else elem.props.get('innerHTML', text_html)
            if text_html is not None and name is not None:
                return [{
                    'name': name,
                    'text_html': text_html,
                    'sent': sent if sent is not None else False,
                }]
            
            if elem.default_slot.children is None:
                return []
            
            if len(elem.default_slot.children) == 0:
                return []
            
            result = []
            for child in elem.default_slot.children:
                result.extend(get_message(child, name=name, sent=sent))
            return result
        
        logger.debug("Serializing history")
        return get_message(self.history, None, None) 

    def restore_history(self, messages: list[dict]):
        """
        Restore the chat history from the GUI state.
        
        Args:
            state: The GUI elements containing the messages.
        """
        logger.trace("Restoring history")
        logger.debug("Restoring history with messages: %s", messages)
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

        # If required (like moving up in the hierarchy), then clear the history
        if clear_history:
            self.clear_history()
        self.write()

        # Update the breadcrumbs and details
        self.breadcrumbs.clear()
        with self.breadcrumbs:
            breadcrumb_selector(self)
            for i,item in enumerate(self.selection[1:]):
                new_sel = self.selection[:i+2]
                ui.button(item.name).props('rounded').on_click(lambda _, new_sel=new_sel: state.change_selection(new=new_sel))

        self.refresh_details()

    def refresh_details(self):
        logger.trace("Refreshing details")
        logger.debug(f"SELECTION:{self.selection}")
        # These imports are here to avoid circular imports
        from gui.home import view_all_styles, view_all_series, view_all_publishers
        from gui.style import view_style, view_pick_style
        from gui.series import view_series
        from gui.character import view_character
        from gui.issue import view_issue
        from gui.scene import view_scene
        from gui.panel import view_panel
        from gui.cover import view_cover
        from gui.publisher import view_publisher, view_pick_publisher

        self.clear_details()
        selection = self.selection
        
        if selection == []:
            raise ValueError("Selection cannot be empty.  Please select an item first.")

        kind = selection[-1].kind
        

        if kind == "all_series":
            return view_all_series(self)
        if kind == "all_publishers":
            return view_all_publishers(self)
        if kind == "all_styles":
            return view_all_styles(self)
        
        if kind == 'style':
            view_style(self)
        elif kind == 'art-style-image':
            from gui.style import view_pick_art_style_image
            view_pick_art_style_image(self)
        
        elif kind == 'series':
            view_series(self)
        elif kind == 'character':
            view_character(self)
        elif kind == "issue":
            view_issue(self)
        elif kind == "scene":
            view_scene(self)
        elif kind == "panel":
            view_panel(self)
        elif kind == "cover":
            view_cover(self)
        elif kind == "publisher":
            view_publisher(self)
        elif kind == "pick-publisher":
            view_pick_publisher(self)
        elif kind == "pick-style":
            view_pick_style(self)
        else:
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
