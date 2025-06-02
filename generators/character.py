from typing import Tuple, Optional, List
from gui.state import GUIState
from agents import Agent, function_tool
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS


def character_agent(state: GUIState) -> Agent:
    return Agent(
        name="Character Assistant",
        instructions="""
        You are an interactive artistic assistant who helps create, edit, and publish
        comic books.   You specialize on creating detailed descriptions of characters
        and their attributes to ensure that they are consistently represented regardless
        of the artist or writer.
        """ + BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools=[
            ],
    )

