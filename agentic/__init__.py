from agentic.constants import LANGUAGE_MODEL
from agentic.instructions import instructions
from gui.state import APPState
from agents import Agent
from agentic.toolkits import TOOLKITS, ALL_TOOLS


def init_agents(state: APPState) -> dict[str, Agent]:
    """ONE EDITOR, EVERY TOOL (the author's ruling): a single agent carries
    the union of every room's kit — the room the author stands in flavors
    its instructions, never its capabilities.  The dict shape survives for
    compatibility: every kind maps to the SAME Editor."""
    editor = Agent(
        name="the Editor",
        tools=ALL_TOOLS,
        instructions=instructions,
        model=LANGUAGE_MODEL)
    agents = {k: editor for k in TOOLKITS}
    agents["the Editor"] = editor
    return agents

