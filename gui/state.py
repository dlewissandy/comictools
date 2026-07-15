import os

from nicegui import ui
from gui.avatars import comic_chat_message
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
    from gui.selection import SelectionItem, SelectedKind
    # GUI CONTROLS
    breadcrumbs: ui.button_group
    details: ui.scroll_area
    history: ui.scroll_area
    user_input: ui.input
    send_button: ui.button
    
    def __init__(self, breadcrumbs, details, history, user_input, send_button, storage: GenericStorage, dark_mode: bool = False, selection: list[SelectionItem] = [], persist: bool = True, suggestions_row=None):
        from agentic import init_agents
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
        # Only the root window persists its selection/history to the state
        # file; deep-linked windows carry their own context (UX_ideas.md).
        self.persist = persist
        self._url_synced = False
        self.suggestions_row = suggestions_row
        # THE ONE THREAD: a single conversation follows the author across
        # every room — typed entries (user/reply/room/work/aside), the DOM
        # rendered FROM it.  One agent memory rides beside it.
        self.thread: list[dict] = []
        self.agent_thread: list = []

        # Storage and logging must be initialized before agents
        self._storage = storage

        # IMAGE EDITOR STATE
        self.image_editor_selection: dict | None = None
        self.image_editor_image: str | None = None
        self.image_editor_mode: str | None = None
        self.image_editor_dom_id: str | None = None
        self.image_editor_choices: list[str] = []
        self.image_editor_choice_selected: str | None = None
        self.image_editor_original_image: str | None = None
        self.image_editor_session_id: str | None = None

        # AGENTS
        self._agents = init_agents(self)
        

        
    @property
    def storage(self) -> GenericStorage:
        """THE SELECTION NAMES THE HOUSE: storage is scoped to the house
        the current trail walks through (data/<slug>), recomputed only
        when the selection changes.  With no house in scope (the lobby,
        the legacy layout) the constructor's root storage answers — inert
        under mount-all, exactly right under a single-root data/."""
        from storage import registry
        # a handed non-root storage (a test fixture, an absolute repo root)
        # is authoritative — only the inert root re-scopes by selection
        if str(getattr(self._storage, 'base_path', '')) != registry.DATA_DIR:
            return self._storage
        key = tuple((s.kind.value, s.id) for s in (self._selection or []))
        if getattr(self, '_storage_key', None) != key:
            from gui.selection import house_for_selection
            slug = house_for_selection(self._selection)
            self._house_slug = slug
            self._house_storage = registry.storage_for(slug) if slug else self._storage
            self._storage_key = key
        return self._house_storage
    

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
        for e in getattr(self, "thread", None) or []:
            if e.get("t") == "user":
                messages.append({"role": "user", "content": e.get("text") or ""})
            elif e.get("t") == "reply":
                messages.append({"role": "assistant", "content": e.get("text") or ""})
        return messages

    def change_selection(self, new: list[SelectionItem], clear_history: bool = True):
        """
        Change the current selection in the GUI state.
        
        Args:
            state: The GUI elements containing the selection.
            new: The new selection to set.
        """
        from gui.selection import SelectedKind
        # A SCENE IS NEVER A DESTINATION: scenes live in the open book, not on
        # a page of their own.  Selecting one opens the issue to its manuscript
        # page instead — so there is no scene page and no scene chip in the
        # breadcrumb.  (A panel keeps its scene ancestor for its keys; the
        # breadcrumb just doesn't draw a button for it.)
        if new and new[-1].kind == SelectedKind.SCENE:
            iidx = next((i for i in range(len(new) - 1, -1, -1)
                         if new[i].kind == SelectedKind.ISSUE), None)
            if iidx is not None:
                iid = new[iidx].id
                if not hasattr(self, '_book_detail') or self._book_detail is None:
                    self._book_detail = {}
                if not hasattr(self, '_book_anchor') or self._book_anchor is None:
                    self._book_anchor = {}
                self._book_detail[iid] = 'scenes'
                self._book_anchor[iid] = f'scene-{new[-1].id}'
                new = new[:iidx + 1]

        logger.trace(f"Changing selection to {new}")
        old = self.selection
        if old == new:
            logger.debug("New selection is the same as the old selection. No changes made.")
            return

        self._selection = new

        # THE ONE THREAD FOLLOWS THE AUTHOR: walking to another room leaves
        # a slim scene caption in the conversation (coalescing — five silent
        # walks leave one), and the agent memory gets a hat note so the
        # coauthor knows whose bench it is standing at now.
        old_key = self.conversation_key(old)
        new_key = self.conversation_key(new)
        if clear_history and old_key != new_key:
            from gui.thread import thread_room_marker
            from gui.coauthor import coauthor_name
            role = coauthor_name(new)
            thread_room_marker(self, new_key,
                               (new[-1].name if new else "the studio"), role)
            hat = {"role": "system",
                   "content": f"[The author walked to {new[-1].name if new else 'the studio'} "
                              f"({new_key}).  You now stand at that bench with its tools; "
                              f"the conversation continues.]"}
            thr = getattr(self, "agent_thread", None)
            if thr is not None:
                if thr and isinstance(thr[-1], dict) and thr[-1].get("role") == "system" \
                        and str(thr[-1].get("content", "")).startswith("[The author walked"):
                    thr[-1] = hat          # silent walks coalesce here too
                else:
                    thr.append(hat)

        self.write()

        # Update the breadcrumbs and details
        self.breadcrumbs.clear()
        with self.breadcrumbs:
            breadcrumb_selector(self)
            for i,item in enumerate(self.selection[1:]):
                # a scene is never its own stop — it rides in the book, so the
                # breadcrumb skips it even inside a panel's trail
                if item.kind == SelectedKind.SCENE:
                    continue
                new_sel = self.selection[:i+2]
                ui.button(item.name).props('rounded').on_click(lambda _, new_sel=new_sel: self.change_selection(new=new_sel))
            ui.space()

        self.refresh_details()
        self._sync_url()
        self._refresh_coauthor()

    @staticmethod
    def migrate_style_threads(conversations: dict, pid: str | None) -> dict:
        """STYLES MOVED INTO THE HOUSE: threads saved under the retired
        room's addresses re-key to the canonical trail so no conversation
        orphans.  Handles all three legacy shapes: '/styles',
        '/styles/<sid>', and the stale-trail '/styles/style/<sid>'."""
        if not pid:
            return conversations
        for k in [k for k in conversations if k == "/styles" or k.startswith("/styles/")]:
            sid = k[len("/styles/"):] if k != "/styles" else ""
            if sid.startswith("style/"):
                sid = sid[len("style/"):]
            new = f"/publishers/{pid}/style/{sid}" if sid else f"/publishers/{pid}"
            conversations.setdefault(new, conversations.pop(k))
        return conversations

    def conversation_key(self, selection: list[SelectionItem]) -> str:
        """
        The conversation an object owns is keyed by its canonical URL; views
        with no address of their own (pickers, image editor) share the thread
        of their nearest addressable ancestor.
        """
        from gui.routes import selection_to_url
        sel = list(selection)
        while sel:
            url = selection_to_url(sel)
            if url is not None:
                return url
            sel = sel[:-1]
        return "/"

    def _refresh_coauthor(self):
        """
        The coauthor speaks first: on a fresh conversation, post one short
        context-aware line, and refresh the suggestion chips above the input.
        Chips send real messages — conversation starters, not wired buttons.
        """
        from gui.coauthor import opening_and_chips, coauthor_name
        try:
            opener, chips = opening_and_chips(self)
        except Exception as e:
            logger.debug(f"coauthor refresh skipped: {e}")
            return

        role = coauthor_name(self.selection)
        try:
            # the conversation box names the room, one voice answers
            here = self.selection[-1].name if self.selection else "the studio"
            self.user_input._props['placeholder'] = f"At {here} — talk to the Editor…"
            self.user_input.update()
        except Exception:
            pass

        # THE YOUR-TURN STRIP: the conversation always ends with the next
        # move — the room's opener as a quiet line (never persisted) and
        # a NEXT: row of chips.  It lives pinned under the history pane.
        if self.suggestions_row is not None:
            from messaging import send
            self.suggestions_row.clear()

            async def _fire(text: str):
                if text.endswith('…'):
                    # a prompt STARTER: prefill the conversation box, don't send
                    self.user_input.value = text[:-1]
                    try:
                        self.user_input.run_method('focus')
                    except Exception:
                        pass
                    return
                self.user_input.value = text
                await send(state=self)

            with self.suggestions_row:
                with ui.column().classes('w-full').style('gap: 2px;'):
                    if opener:
                        ui.label(opener).classes('comic-label-sm italic') \
                            .style('opacity: .75; white-space: normal;')
                    with ui.row().classes('w-full items-center').style('gap: 6px;'):
                        ui.label('NEXT:').classes('comic-label-sm').style('opacity: .6;')
                        for chip in chips[:4]:
                            # a chip is a WORD (send/prefill) or a DOOR
                            # (label, action) — doors act instantly, no
                            # agent turn to do what a click can do
                            if isinstance(chip, tuple):
                                label, action = chip
                                ui.button(label, on_click=lambda _, a=action: a()) \
                                    .props('outline rounded dense no-caps size=sm')
                            else:
                                ui.button(chip, on_click=lambda _, t=chip: _fire(t)) \
                                    .props('outline rounded dense no-caps size=sm')

    def render_your_turn(self):
        """The strip is the thread's standing last line — recompute it."""
        self._refresh_coauthor()

    def _sync_url(self):
        """
        Keep the browser URL in sync with the selection so every view is
        deep-linkable and reload-safe (hierarchical resource routes).  The
        first sync replaces the current history entry; later ones push.
        """
        from gui.routes import selection_to_url
        import json as _json
        url = selection_to_url(self.selection)
        if url is None:
            return
        verb = "pushState" if self._url_synced else "replaceState"
        self._url_synced = True
        try:
            ui.run_javascript(f"history.{verb}(null, '', {_json.dumps(url)});")
        except Exception as e:
            logger.debug(f"URL sync skipped: {e}")

    def refresh_details(self):
        logger.trace("Refreshing details")
        logger.debug(f"SELECTION:{self.selection}")
        # TOOLTIP DISCIPLINE: a rebuild orphans any tooltip open under the
        # cursor — Quasar portals them to <body>, so they'd float forever
        try:
            ui.run_javascript("document.querySelectorAll('.q-tooltip').forEach(t => t.remove());")
        except Exception:
            pass
        # These imports are here to avoid circular imports
        from gui.style import view_style
        from gui.series import view_series
        from gui.setting import view_setting
        from gui.character import view_character, view_character_reference
        from gui.issue import view_issue
        from gui.scene import view_scene
        from gui.panel import view_panel
        from gui.cover import view_cover
        from gui.publisher import view_publisher
        from gui.reference_image import view_reference_image
        from gui.variant import view_character_variant
        from gui.styled_image import view_styled_image
        from gui.image_editor import view_image_editor
        from gui.image_editor_choices import view_image_editor_choices
        from gui.selection import SelectionItem, SelectedKind

        self.clear_details()
        selection = self.selection
        
        if selection == []:
            selection = [SelectionItem(kind=SelectedKind.ALL_SERIES, name="Series", id=None)]

        kind = selection[-1].kind
        identifier = selection[-1].id
        
        match kind.value:
            case "lobby":
                from gui.home import view_lobby
                return view_lobby(self)
            case "all-series":
                # THE RETIRED ROOM: / is the lobby now — stale trails land
                # on the front door, not a bare series wall
                from gui.home import view_lobby
                return view_lobby(self)
            case "all-publishers":
                # THE RETIRED WALL: the studio wall shows every house now
                from gui.home import view_lobby
                return view_lobby(self)
            case "all-styles":
                # THE RETIRED ROOM: styles live in the house — a stale
                # persisted trail lands on the front door instead
                from gui.home import view_lobby
                return view_lobby(self)
            case "library":
                from gui.library import view_library
                return view_library(self)
            case "style":
                return view_style(self)
            case "series":
                return view_series(self)
            case "setting":
                return view_setting(self)
            case "prop":
                from gui.asset_view import view_prop
                return view_prop(self)
            case "outfit":
                from gui.asset_view import view_outfit
                return view_outfit(self)
            case "character":
                return view_character(self)
            case "issue":
                return view_issue(self)
            case "scene":
                return view_scene(self)
            case "artboard":
                from gui.light_table import view_artboard
                return view_artboard(self)
            case "panel":
                return view_panel(self)
            case "cover":
                return view_cover(self)
            case "insert":
                from gui.insert import view_insert
                return view_insert(self)
            case "publisher":
                return view_publisher(self)
            case "pick-publisher":
                # PICK-PUBLISHER retired with the wall: the trail's own house rules
                from gui.home import view_lobby
                return view_lobby(self)
            case "character-reference":
                return view_character_reference(self)
            case "reference-image":
                return view_reference_image(self)
            case "variant":
                return view_character_variant(self)
            case "styled-image":
                return view_styled_image(self)
            case "styled-variant":
                return view_styled_image(self)
            case "image-editor":
                return view_image_editor(self)
            case "image-editor-choices":
                return view_image_editor_choices(self)
            case _:        
                # Handle other cases or return a default message
                self.clear_details()
                with self.details:
                    ui.markdown(f"No description available for this item. {kind}")
                    return    
                
            


    def write(self):
        """THE STUDIO REMEMBERS from EVERY window: conversations are keyed
        by canonical object URL and MERGED into the state file (never
        wholesale-overwritten), so a deep-linked window's chats survive
        right alongside the root's.  Selection and the lights are simply
        last-writer-wins — a single author's 'where was I' is wherever
        they last were.  The write is atomic and lock-guarded."""
        logger.debug("Saving state to file")
        import json
        import threading
        lock = getattr(APPState, "_write_lock", None)
        if lock is None:
            lock = threading.Lock()
            APPState._write_lock = lock

        from gui.thread import persistable, merge_threads
        with lock:
            on_disk = {}
            try:
                with open(STATE_FILEPATH) as f:
                    on_disk = json.load(f)
            except (OSError, ValueError):
                pass
            merged = merge_threads(on_disk.get("thread", []),
                                   persistable(getattr(self, "thread", None) or []))
            state_json = {
                "selection": [item.model_dump() for item in self.selection],
                "thread": merged,
                "agent_thread": [it for it in (getattr(self, "agent_thread", None) or [])
                                 if isinstance(it, dict)][-120:],
                "dark_mode": self.dark_mode,
            }
            from uuid import uuid4
            tmp = f"{STATE_FILEPATH}.{uuid4().hex[:6]}.tmp"
            with open(tmp, "w") as f:
                json.dump(state_json, f, indent=2)
            os.replace(tmp, STATE_FILEPATH)


def breadcrumb_selector(state: APPState):
    from gui.selection import SelectionItem, SelectedKind

    selection = state.selection
    if selection == []:
        raise ValueError("Selection cannot be empty.  Please select an item first.")
    # A SPLIT CONTROL, never a trap: the label walks to the root room, the
    # arrow ONLY opens the menu — every root room is listed, current marked
    primary_selection = ui.dropdown_button(selection[0].name.title(),
                                           split=True, auto_close=True)
    # styles live IN the house (each repo edits its own copies), so the
    # rack is on the publisher's page — no global Styles room
    # TWO ROOMS: make in the Studio, read in the Reading Room —
    # the publishers wall and the asset library folded into the wall
    rooms = (("Studio", SelectedKind.LOBBY),
             ("Reading Room", SelectedKind.LIBRARY))
    with primary_selection:
        for label, kind in rooms:
            here = selection[0].kind == kind
            item = ui.item(("✓ " if here else "") + label)
            if here:
                continue
            if kind == SelectedKind.LIBRARY:
                # the Reading Room is another SPACE — lights down, no chat —
                # so it opens in its own tab and the studio stays put
                item.on_click(lambda _: ui.run_javascript(
                    "window.open('/library', '_blank');"))
            else:
                item.on_click(lambda _, k=kind, l=label: state.change_selection(
                    new=[SelectionItem(kind=k, name=l, id=None)]))

    new_sel = [selection[0]]
    primary_selection.on("click", lambda _, new_sel=new_sel: state.change_selection(new=new_sel))
    return primary_selection





def set_dark_mode(state: APPState, value: bool):
    """
    A wrapper function to allow the property to be set from the GUI.
    
    Args:
        state: The GUI elements containing the dark mode setting.
        value: A boolean indicating whether to enable dark mode.
    """
    state.dark_mode = value
