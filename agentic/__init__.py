from agentic.constants import LANGUAGE_MODEL
from agentic.instructions import instructions
from gui.state import APPState
from agents import Agent
from agentic.toolkits import TOOLKITS


def init_agents(state: APPState) -> dict[str, Agent]:
    """
    Initialize the agents for the application.
    
    Args:
        state: The GUI state object.
    
    Returns:
        A dictionary of initialized agents.
    """
    return {
        k: Agent(
            name= k,
            tools=v,
            instructions=instructions,
            model=LANGUAGE_MODEL)
            for k, v in TOOLKITS.items()
    }

