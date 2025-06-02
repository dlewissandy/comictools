from typing import Tuple, Optional, List
from loguru import logger
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool
from gui.state import GUIState
from style.comic import ComicStyle
from gui.selection import change_selection
from style.art import ArtStyle
from style.character import CharacterStyle
from style.bubble import BubbleStyle, BubbleStyles


def all_styles_agent(state: GUIState) -> Agent:
    from models.series import Series
    from gui.selection import SelectionItem

    @function_tool
    def create_style(
        name: str, 
        description: str,
        art_style: ArtStyle,
        character_style: CharacterStyle,
        bubble_styles: BubbleStyles,
        ) -> ComicStyle | str | None:
        """
        Create a new style with the given name.
        
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
        id = name.lower().replace(" ", "-")
        if ComicStyle.read(id=id) is not None:
            logger.error(f"Style with name '{name}' already exists.")
            return f"Style with name '{name}' already exists."
        
        logger.info(f"The name '{name}' is available.")
        style = ComicStyle(
            name=name, 
            id=id, 
            description=description, 
            art_style=art_style, 
            character_style=character_style, 
            bubble_styles=bubble_styles,
            image=None
        )
        style.write()
        selection = state.get("selection")
        new_itm = SelectionItem(name=style.name, id=style.id, kind='style')
        new_sel = [s for s in selection]+[new_itm]
        change_selection(state, new=new_sel, clear_history=False)
        state["is_dirty"] = True
        return style
        
    @function_tool
    def get_comic_style_names() -> list[str]:
        """
        Get a list of all comic style names.
        
        Returns:
            A list of comic style names.
        """
        from style.comic import ComicStyle
        styles = ComicStyle.read_all()
        return [style.name for style in styles]

    @function_tool
    def get_comic_style_by_name(name: str) -> ComicStyle | None:
        """
        Get the detialed information about a comic book style given its name.   Note:
        you may need to check the name of the style first using `get_comic_style_names()`
        
        Args:
            name: The name of the comic style.
        
        Returns:
            The ComicStyle object if found, otherwise None.   If this function returns None,
            you may want to check for similar names using `get_comic_style_names()`.
        """
        from style.comic import ComicStyle
        id = name.replace(" ", "-").lower()
        style = ComicStyle.read(id)
        return None

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
        style = ComicStyle.read(id=name.lower().replace(" ", "-"))
        if style is None:
            return f"Comic style '{name}' not found.  Maybve try looking at the list of comic styles first?"
        sel_itm = SelectionItem(
            id=style.id,
            name=style.name,
            kind="style",
        )
        state["selection"].append(sel_itm)
        state["is_dirty"] = True
        return f"Selected comic style: {style.name}"

    @function_tool
    def delete_style(name: str) -> str:
        """
        Delete a style by name.   You MUST ask for confirmation before using this tool.
        
        Args:
            name: The name of the style to delete.
        
        Returns:
            A status message indicating the result of the deletion.
        """
        style = ComicStyle.read(id=name.lower().replace(" ", "-"))
        if style is None:
            return f"Style '{name}' not found."
        path = style.path()
        if path is None:
            return f"Style '{name}' has no associated file to delete."
        # REMOVE THE FOLDER THAT THE SERIES IS STORED IN.
        import shutil
        try:
            shutil.rmtree(path)
        except Exception as e:
            logger.error(f"Failed to delete style folder '{path}': {e}")
            return f"Failed to delete style folder '{path}': {e}"

        # The selection does not need to change, but we do need to refresh the display to 
        # remove the deleted series from the list.
        state["is_dirty"] = True
        return f"Deleted style: {style.name}"

    return Agent(
        name="Home Screen Assistant",
        instructions="""
        You are an interactive artistic assistant who helps human artists and creators manage
        comic book styles.  
  
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools = [
            select_comic_style,
            get_comic_style_by_name,
            get_comic_style_names,
            create_style,
            delete_style
        ]
    )

