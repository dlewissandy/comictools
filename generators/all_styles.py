from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool,Tool
from gui.state import APPState
from schema.style.comic import ComicStyle
from schema.style.art import ArtStyle
from schema.style.character import CharacterStyle
from schema.style.dialog import BubbleStyles


def all_styles_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    from gui.selection import SelectionItem, SelectedKind
    from storage.generic import GenericStorage
    storage: GenericStorage = state.storage

    @function_tool
    def create_style(
        name: str, 
        description: str,
        art_style: ArtStyle,
        character_style: CharacterStyle,
        bubble_styles: BubbleStyles,
        ) -> ComicStyle | str | None:
        """
        Create a new style with the given name.   Use as much of the relevant information
        from the chat history as possible to fill in the details of the style.  Each field
        should be a short phrase or paragraph, except for the description which can be longer.
        focus on the visual and artistic aspects of the style that might be important for an
        artist to replicate the style.
        
        Args:
            name: The name of the new style.
            description: An optional description of the style.
            art_style: The art style to be used in the comic.
            character_style: The character style to be used in the comic.
            bubble_styles: The bubble styles to be used in the comic.

        Returns:
            The created Style object or an error message if the style already exists.
        """
        # check to see if the publisher already exists.
        style = storage.find_style(name = name)
        if style is not None:
            logger.warning(f"The name '{name}' is already in use by another style.")
            return f"The name '{name}' is already in use by another style.  Please choose a different name."

        logger.info(f"The name '{name}' is available.")
        style = ComicStyle(
            name=name, 
            id=name.lower().replace(" ", "-"),
            description=description, 
            art_style=art_style, 
            character_style=character_style, 
            bubble_styles=bubble_styles,
            image=None
        )
        style_id = storage.create_style(style)
        selection = state.selection
        new_itm = SelectionItem(name=style.name, id=style_id, kind=SelectedKind.STYLE)
        new_sel = [s for s in selection]+[new_itm]
        state.change_selection(new=new_sel, clear_history=False)
        return style
        

    @function_tool
    def select_comic_style(name: str) -> str:
        """
        Select a comic style by name.   This is a precursor for editing its 
        properties.
        
        Args:
            name: The name of the comic style to select.
        
        Returns:
            A status message indicating the result of the selection.
        """
        style = storage.find_style(name=name)
        if style is None:
            return f"Comic style '{name}' not found.  Maybve try looking at the list of comic styles first?"
        sel_itm = SelectionItem(
            id=style.id,
            name=style.name,
            kind=SelectedKind.STYLE,
        )
        state.change_selection(new=[s for s in state.selection] + [sel_itm], clear_history=False)
        return f"Selected comic style: {style.name}"



    return Agent(
        name="Home Screen Assistant",
        instructions="""
        You are an interactive artistic assistant who helps human artists and 
        creators manage comic book styles.  
  
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools = [
            tools.get('get_current_selection', None),
            
            select_comic_style,

            tools.get('get_all_styles', None),
            tools.get('find_style', None),

            create_style,
            tools.get('delete_style', None),
        ]
    )

