from typing import Tuple, Optional, List
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool
from gui.state import APPState
from schema import TitleBoardModel, CoverLocation, FrameLayout, CharacterRef, Issue
from gui.selection import SelectionItem, SelectedKind

def issue_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    from generators.tools import dereference_issue as _get_issue
    from generators.tools import normalize_id, normalize_name
        
    @function_tool
    def get_current_issue() -> Issue:
        """
        Get the currently selected comic book issue.
        
        Returns:
            The currently selected issue.
        """
        return _get_issue(state, index=-2)

    @function_tool
    def create_cover(location: CoverLocation, characters: list[str], foreground: str, background: str) -> str:
        """
        Create a cover for the currently selected comic book issue.   Returns the status
        of the cover creation operation.

        Args:
            location (CoverLocation): The location where the cover should be created.
            characters (str): The names of the characters to include on the cover.  You should verify that these
                characters are in the series.   If they are not, but there are similar names, confirm with the user
                which character they meant.
            foreground (str): A detailed description of the visual elements in the foreground of the cover.
            background (str): A detailed description of the visual elements in the background of the cover.

        """
        issue_or_str = _get_issue(state, index=-2)
        
        if isinstance(issue_or_str, str):
            return issue_or_str
        
        issue: Issue = issue_or_str
        issue_id = issue.id
        series_id = issue.series_id

        for cover in issue.covers:
            if cover.location == location.value:
                cover.delete()

        cover = TitleBoardModel(
            id=normalize_id(location.value),
            location = location,
            issue=issue_id,
            series=series_id,
            characters=[CharacterRef(series=series_id, character=char, variant="base") for char in characters],
            style=issue.style,
            aspect=FrameLayout.PORTRAIT,
            foreground=foreground,
            background=background,
            image=None,
            reference_images=[]

        )

        kind = SelectedKind.COVER
        name = normalize_name(kind)
        new_sel = SelectionItem(id=cover.id, kind=kind, name=name,)
        cover.write()
        new_sel = state.selection + [new_sel]
        state.change_selection(new_sel)
        state.is_dirty = True
        
        return f"Cover created successfully for issue {issue.name} at location {location.name}."

    return Agent(
        name="issue",
        instructions="Agent for managing comic book issues.\n\n"+BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        
        tools=[
            tools.get('delete_issue', None),
            tools.get('find_issue_by_name', None),
            get_current_issue,

            create_cover,
        ]
    )

