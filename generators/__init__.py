from .all_publishers import all_publishers_agent
from .all_series import all_series_agent
from .all_styles import all_styles_agent
from .character import character_agent
from .cover import cover_agent
from .issue import issue_agent
from .panel import panel_agent
from .publisher import publisher_agent
from .scene import scene_agent
from .series import series_agent
from .style import style_agent
from .variant import variant_agent
from gui.state import APPState
from agents import Agent, Tool


def init_agents(state: APPState, tools: dict[str, Tool]) -> dict[str, Agent]:
    """
    Initialize the agents for the application.
    
    Args:
        state: The GUI state object.
    
    Returns:
        A dictionary of initialized agents.
    """
    agents = {
        "all-publishers": all_publishers_agent(state=state, tools=tools),
        "all-series": all_series_agent(state=state, tools=tools),
        "all-styles": all_styles_agent(state=state, tools=tools),
        "character": character_agent(state=state, tools=tools),
        "style": style_agent(state=state, tools=tools),
        "series": series_agent(state=state, tools=tools),
        "issue": issue_agent(state=state, tools=tools),
        "scene": scene_agent(state=state, tools=tools),
        "cover": cover_agent(state=state, tools=tools),
        "panel": panel_agent(state=state, tools=tools),
        "publisher": publisher_agent(state=state, tools=tools),
        "variant": variant_agent(state=state, tools=tools),
        "front-cover": cover_agent(state=state, tools=tools),
        "back-cover": cover_agent(state=state, tools=tools),
        "inside-front-cover": cover_agent(state=state, tools=tools),
        "inside-back-cover": cover_agent(state=state, tools=tools),
    }
    return agents

