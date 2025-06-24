import os
from loguru import logger
from pydantic import BaseModel, Field
from schema.panel import Panel
from schema.character import CharacterModel
from helpers.constants import SCENES_FOLDER, STYLES_FOLDER, COMICS_FOLDER, PANELS_FOLDER
from helpers.generator import invoke_generate_api
from helpers.file import generate_unique_id

class SceneModel(BaseModel):
    """
    A scene is a collection of pannels that tell a story.   For example, a scene could be a page in a comic book.
    """
    id: str = Field(..., description="The unique identifier of the scene.  This is the same as the title, but with spaces replaced by underscores.")
    issue: str = Field(..., description="The identifier of the issue comic book or project that this scene belongs to. default to empty string")
    series: str = Field(..., description="The identifier of the series that this scene belongs to. default to empty string")
    name: str = Field(..., description="A short title for the scene.   Default to a short (5 words or less) description of the scene'")
    story: str = Field(..., description="The story or narrative arc of the scene")
    style: str = Field(..., description="The art style of the scene.   Default to 'vintage-four-color'")

    # @property
    # def panels(self) -> list[Panel]:
    #     """
    #     Get the panels in the scene
    #     """

    #     panels_path = os.path.join(self.path(), "panels")
    #     panels = []

    #     if not os.path.exists(panels_path):
    #         return panels
        
    #     folder_contents = os.listdir(panels_path)
    #     for panel_id in folder_contents:
    #         # skip if it is not a folder
    #         if not os.path.isdir(os.path.join(panels_path, panel_id)):
    #             logger.warning(f"Skipping {panel_id} because it is not a folder")
    #             continue
    #         # Try to read the panel as a RoughBoardModel.  If that fails, then read it as a BeatBoardModel
    #         panel = Panel.read(series=self.series, issue=self.issue, scene=self.id, id=panel_id)
    #         if panel is None:
    #             logger.warning(f"Panel {panel_id} not found in scene {self.id}.  Removing from scene")
    #             continue
    #         else:
    #             panels.append(panel)

    #     # Sort the panels by the numeric value of their id
    #     panels.sort(key=lambda x: int(x.id))
    #     return panels

    # def image_filepath(self) -> str | None:
    #     """
    #     Get the image filepath for the scene.  This is the image of the first panel in the scene.
    #     If the scene has no panels, then return an empty string.
    #     """
    #     first_panel = self.read_panel(0)
    #     if first_panel is None:
    #         return None
    #     return first_panel.image

    # def characters(self) -> list[str]:
    #     """
    #     return the list of characters in the scene
    #     """
    #     panels = self.get_panels()
    #     characters = []
    #     for panel in panels.values():
    #         characters.extend(panel.characters)
    #     return list(set(characters))

    # def get_characters(self) -> dict[str, CharacterModel]:
    #     """
    #     Get the characters in the scene
    #     """
    #     character_ids = self.characters()
    #     from schema.issue import Issue
    #     issue_obj = Issue.read(id = self.issue)
    #     series = issue_obj.series_id
    #     characters = {}
    #     for character_id in character_ids:
    #         name, variant = character_id.split("/")
    #         character = CharacterModel.read(series=series, name=name, variant=variant)
    #         characters[character_id] = character
    #     return characters

    def path(self) -> str:
        """
        return the path to the scene model
        """
        return os.path.join(COMICS_FOLDER,self.series,"issues",self.issue, "scenes", self.id)
        
    def filepath(self) -> str:
        """
        return the filepath to the scene model
        """
        return os.path.join(self.path(), "scene.json")
    
    @classmethod
    def generate(cls, story: str, issue: str):
        """
        generate new page model using generative AI (this is a starting point for storyboarding)
        """
        from schema.issue import Issue
        from schema.series import Series
        from schema.style.comic import ComicStyle
    
        from schema.character import CharacterModel
        # verify that the issue exists
        issue_obj = Issue.read(id = issue)
        if issue_obj is None:
            raise FileNotFoundError(f"issue {issue} not found")
        series_obj = Series.read(id = issue_obj.series_id) 
        if series_obj is None:
            raise FileNotFoundError(f"series {issue} not found")
        
        # verify that the style exists
        style_id = issue_obj.style
        cast = "\n".join([f"* {key} - {value.description}" for key,value in series_obj.get_characters().items()])
        
        prompt = f"""
You are an agent designed to create a draft storyboard from a user's brief description. Break the story into a 
detailed list of panels, each consisting of a couple of sentences that convey visual storytelling elements, character
actions, and emotional states. Include a list of characters appearing in each frame. Minimize narration and chat
bubbles, and keep dialogue short, resembling comic book panels.  For now, focus on creating BeatBoards.   We will 
refine them later once this initial draft is complete.

# CAST OF CHARACTERS
This is the list of the characters that appear in the production.   Not all of them will appear in every scene.
{cast}

Do not add any new characters to the story.  Only use the characters that are already in the cast of characters.

# STORY
{story}

"""
        # Invoke the OpenAI API to generate a scene description

        response = invoke_generate_api(prompt=prompt, text_format=BeatBoardsModel)
        response.issue= issue
        response.style = style_id
        response.id = generate_unique_id(os.path.join(issue_obj.path(), "scenes"))
        panels_path = os.path.join(issue_obj.path(), "scenes", response.id, "panels")
        # Verify characters here.
        issue_characters = series_obj.characters
        logger.info(f"issue characters: {issue_characters}")
        for panel in response.panels:
            for character in panel.characters:
                if character not in issue_characters:
                    logger.warning(f"Character {character} not found in issue {issue_obj.id}.  Removing from panel")
                    panel.characters.remove(character)

            id = generate_unique_id(panels_path, create_folder=True)
            panel.issue = issue
            panel.scene = response.id
            panel.id = id
            panel.write()

        result = cls(id=response.id, story=story, issue=issue, style=style_id, panels=[panel.id for panel in response.panels])
        result.write()
        return result
        

    
    # def read_panel(self, index:int) -> Panel | None:
    #     """
    #     Read a panel from the scene
    #     """
    #     logger.debug(f"Reading panel {index} from scene {self.id}")
    #     if index < 0:
    #         raise IndexError(f"Panel index {index} out of range")
    #     # Try to read the panel as a RoughBoardModel.  If that fails, then read it as a BeatBoardModel
    #     # If that fails then raise an error.
    #     panel = Panel.read(series=self.series,issue = self.issue, scene=self.id, id=index)
    #     if panel is None:
    #         logger.error(f"Panel {index} not found.")
    #         return None
        
    #     logger.debug(f"Found beatboard panel {index}")
    #     return panel
        
    # def read_panels(self):
    #     """
    #     Read the panels from the scene
    #     """
    #     panels = [self.read_panel(i) for i in range(len(self.panels))]
    #     if any(panel is None for panel in panels):
    #         none_index = panels.index(None)
    #         panel_id = self.panels[none_index]
    #         raise FileNotFoundError(f"Panel {panel_id} not found")
    #     return panels

    def format(self, heading_level: int=1, no_panels: bool=False):
        """
        Format the scene for display
        """
        
        text = f"""
{'#' * heading_level} SCENE
* **id**: {self.id}
* **story**: {self.story}
* **issue**: {self.issue}
* **style**: {self.style}
"""
        if not no_panels:
            text += f"""
{'#' * (heading_level +1)} PANELS
"""
            for i,panel in enumerate(self.read_panels()):
                text += f"""{'#' * (heading_level + 2)} PANEL {i}\n{panel.format()}\n"""
        return text