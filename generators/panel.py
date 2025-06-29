from typing import Tuple, Optional, List
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool
from gui.state import APPState

def panel_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    from generators.tools import dereference_issue as _get_issue
    from generators.tools import normalize_id, normalize_name
        

    return Agent(
        name="issue",
        instructions="Agent for managing comic book issues.\n\n"+BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        
        tools=[
            tools.get('get_current_selection', None),

            tools.get('find_panel', None),
        ]
    )



