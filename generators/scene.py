from typing import Tuple, Optional, List
from generators.constants import LANGUAGE_MODEL, BOILERPLATE_INSTRUCTIONS
from agents import Agent, function_tool, Tool
from gui.state import APPState
from schema import Narration, Dialogue, FrameLayout, CharacterRef, InsertionLocation, AfterLast, After, BeforeFirst, Before, Panel, Issue, Series, CharacterRef, CharacterModel, CharacterVariant, SceneModel

from storage.generic import GenericStorage

def scene_agent(state: APPState, tools: dict[str, Tool]) -> Agent:
    from generators.tools import dereference_issue as _get_issue
    from generators.tools import normalize_id, normalize_name
    

    @function_tool
    def create_panel(
        name: str,
        description: str,
        aspect: FrameLayout,
        characters: List[CharacterRef],
        narration: List[Narration],
        dialogue: List[Dialogue],
        insertion_location: InsertionLocation = AfterLast,
    ) -> str:
        """
Use this tool to create a single panel in a comic book. Choose this when you 
want to advance the visual narrative by showing a specific moment in time 
through composition, character action, and layout. This tool emphasizes
visual storytelling; prefer it over textual exposition when possible.

This tool is appropriate when:

* A character takes a meaningful action or reacts with clear emotion
* The scene changes in location, time, or energy
* A visual contrast or beat needs to be captured (e.g., tension → release, zoom-in → zoom-out)

Avoid using this tool for:
* Panels that would duplicate prior visuals with no change
* Abstract narration or internal monologue that lacks visual grounding

Args:
name (str): A short label summarizing the panel’s core beat (e.g., “Tormond
  Draws His Bow”).

description (str): A clear visual description of the panel. Describe what
  the reader sees: character positions, motion, facial expressions, and camera
  framing. Think in cinematic or storyboard terms. Do not include narration or
  dialog here.   This description will be used by artists to ink the panel

characters: Names of all character variants visibly present in the panel.

dialogue: Add only if spoken words enhance pacing, emotion, or story clarity.
  It is valid and often preferable to leave this empty.

narration: Use only if the panel benefits from a narrative box (e.g., to
  indicate time passing or internal thoughts). Do not repeat what the image
  already conveys.

aspect_ratio: Select based on visual composition needs:
    * Use portrait for vertical motion, isolation, or focus.
    * Use landscape for wide action or multiple focal points.
    * Use square for balance, neutrality, or symmetry.

insertion_location: Where to insert the new panel in the scene. Defaults to
  AfterLast, which adds the panel to the end of the scene.

Storytelling Guidance
Favor image-driven storytelling. Strong panels do not rely on narration or
dialog. Use this tool to show change — in action, framing, or emotion — and
to maintain narrative rhythm. Dialogue and narration should be minimal and
purposeful.
        """
        storage = state.storage
        selection = state.selection

        scene_id = selection[-1].id
        issue_id = selection[-2].id
        series_id = selection[-3].id
        
        # Read the issue, scene and series from storage
        issue = storage.read_object(cls=Issue, primary_key={'issue_id': issue_id, 'series_id': series_id})
        scene = storage.read_object(cls=SceneModel, primary_key={'scene_id': scene_id, 'issue_id': issue_id, 'series_id': series_id})
        series = storage.read_object(cls=Series, primary_key={'series_id': series_id})

        if series is None:
            raise ValueError(f"Series with ID {series_id} not found.")
        elif issue is None:
            raise ValueError(f"Issue with ID {issue_id} not found in series {series.name}.")
        elif scene is None:
            raise ValueError(f"Scene with ID {scene_id} not found in issue {issue.name}.")
        series: Series = series
        issue: Issue = issue
        scene: SceneModel = scene

        panels: list[Panel] = storage.read_all_objects(cls=Panel, primary_key={'issue_id': issue_id, 'scene_id': scene_id, 'series_id': series_id}, order_by='panel_number')
        
        number_of_panels = len(panels)

        # Determine the panel number based on insertion location
        if isinstance(insertion_location, AfterLast):
            # Insert after the last panel
            panel_number = number_of_panels + 1
        elif isinstance(insertion_location, After):
            # Insert after a specific panel
            if insertion_location.index < 0 or insertion_location.index >= number_of_panels:
                raise ValueError(f"Invalid index {insertion_location.index} for insertion location.")
            panel_number = insertion_location.index + 2
        elif isinstance(insertion_location, BeforeFirst):
            # Insert before the first panel
            panel_number = 1
        elif isinstance(insertion_location, Before):
            # Insert before a specific panel
            if insertion_location.index < 0 or insertion_location.index >= number_of_panels:
                raise ValueError(f"Invalid index {insertion_location.index} for insertion location.")
            panel_number = insertion_location.index + 1
        # Normalize names and IDs

        description = description

        # Create the panel
        storage = state.storage
        new_panel = Panel(
            panel_id=normalize_id(name),
            issue_id=issue_id,
            series_id=series_id,
            scene_id=scene_id,
            name = normalize_name(name),
            description=description,
            aspect=aspect,
            panel_number = panel_number,
            character_references=characters,
            narration=narration,
            dialogue=dialogue,
            image=None,  # Image will be set later if needed
            reference_images=[]  # Reference images can be added later
        )

        storage.create_object(new_panel)

        panels.insert(panel_number - 1, new_panel)
        for i,p in enumerate(panels):
            if p.panel_number != i + 1:
                p.panel_number = i + 1
                storage.update_object(p)
        
        
        
        return f"Panel '{new_panel.name}' created successfully in issue '{issue.name}'."

    return Agent(
        name="issue",
        instructions="Agent for managing comic book scenes.\n\n"+BOILERPLATE_INSTRUCTIONS,
        model=LANGUAGE_MODEL,
        tools=[
            tools.get('get_current_selection', None),

            tools.get('find_scene', None),
            tools.get('find_all_panels', None),
            tools.get('find_style', None),
            tools.get('find_panel', None),

            #tools.get('delete_scene', None),

            create_panel,
        ]
    )

