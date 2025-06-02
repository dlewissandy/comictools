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
from gui.state import GUIState
from agents import Agent


def init_agents(state: GUIState) -> dict[str, Agent]:
    """
    Initialize the agents for the application.
    
    Args:
        state: The GUI state object.
    
    Returns:
        A dictionary of initialized agents.
    """
    agents = {
        "all_publishers": all_publishers_agent(state),
        "all_series": all_series_agent(state),
        "all_styles": all_styles_agent(state),
        "character": character_agent(state),
        "style": style_agent(state),
        "series": series_agent(state),
        "issue": issue_agent(state),
        "scene": scene_agent(state),
        "cover": cover_agent(state),
        "panel": panel_agent(state),
        "publisher": publisher_agent(state),
    }
    return agents

