import os
from loguru import logger
from pydantic import BaseModel, Field
from models.panel import RoughBoardModel, BeatBoardModel
from models.character import CharacterModel
from helpers.constants import SCENES_FOLDER, STYLES_FOLDER, COMICS_FOLDER, PANELS_FOLDER
from helpers.generator import invoke_generate_api
from helpers.file import generate_unique_id

class RoughBoardsModel(BaseModel):
    """
    A scene is a collection of pannels that tell a story.   For example, a scene could be a page in a comic book.
    """
    id: str = Field(..., description="A unique identifier for the scene.   Default to a short (5 words or less) description of the scene'")
    story: str = Field(..., description="The story or narrative arc of the scene")
    issue: str = Field(..., description="The identifier of the issue comic book or project that this scene belongs to. default to empty string")
    style: str = Field(..., description="The art style of the scene.   Default to 'vintage-four-color'")
    panels: list[RoughBoardModel ] = Field(..., description="The panels in the scene that tell the story visually.")

class BeatBoardsModel(BaseModel):
    """
    A scene is a collection of pannels that tell a story.   For example, a scene could be a page in a comic book.
    """
    id: str = Field(..., description="A unique identifier for the scene.   Default to a short (5 words or less) description of the scene'")
    story: str = Field(..., description="The story or narrative arc of the scene")
    issue: str = Field(..., description="The identifier of the issue comic book or project that this scene belongs to. default to empty string")
    style: str = Field(..., description="The art style of the scene.   Default to 'vintage-four-color'")
    panels: list[BeatBoardModel ] = Field(..., description="The panels in the scene that tell the story visually.")

class SceneModel(BaseModel):
    """
    A scene is a collection of pannels that tell a story.   For example, a scene could be a page in a comic book.
    """
    id: str = Field(..., description="A unique identifier for the scene.   Default to a short (5 words or less) description of the scene'")
    story: str = Field(..., description="The story or narrative arc of the scene")
    issue: str = Field(..., description="The identifier of the issue comic book or project that this scene belongs to. default to empty string")
    style: str = Field(..., description="The art style of the scene.   Default to 'vintage-four-color'")
    panels: list[str] = Field(..., description="The identifiers of the panels in the scene that tell the story visually.")

    def get_panels(self) -> dict[str, RoughBoardModel | BeatBoardModel]:
        """
        Get the panels in the scene
        """
        panels = {}
        for panel_id in self.panels:
            panel = RoughBoardModel.read(issue=self.issue, scene=self.id, id=panel_id)
            if panel is None:
                panel = BeatBoardModel.read(issue=self.issue, scene=self.id, id=panel_id)
            if panel is None:
                # remove the panel from the list of panels
                logger.warning(f"Panel {panel_id} not found in scene {self.id}.  Removing from scene")
                self.panels.remove(panel_id)
                self.write()
            else:
                panels[panel_id] = panel
        return panels

    def characters(self) -> list[str]:
        """
        return the list of characters in the scene
        """
        panels = self.get_panels()
        characters = []
        for panel in panels.values():
            characters.extend(panel.characters)
        return list(set(characters))

    def get_characters(self) -> dict[str, CharacterModel]:
        """
        Get the characters in the scene
        """
        character_ids = self.characters()
        from models.issue import Issue
        issue_obj = Issue.read(id = self.issue)
        series = issue_obj.series_id
        characters = {}
        for character_id in character_ids:
            name, variant = character_id.split("/")
            character = CharacterModel.read(series=series, name=name, variant=variant)
            characters[character_id] = character
        return characters

    def path(self) -> str:
        """
        return the path to the scene model
        """
        return os.path.join(COMICS_FOLDER,self.issue, "scenes", self.id)
        
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
        from models.issue import Issue
        from models.series import Series
        from style.comic import ComicStyle
    
        from models.character import CharacterModel
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
        

    def write(self):
        """
        Save the scene to a file, by either writing the issue project/comic book or the scene itself.
        """
        # Verify that the folder exists
        path = self.path()
        if not os.path.exists(path):
            os.makedirs(path)
        
        filepath = self.filepath()
        with open(filepath, "w") as f:
            f.write(self.model_dump_json(indent=2))
        

    @classmethod
    def read(cls, id: str, issue: str):
        """
        Read the scene from a file, by either reading the issue project/comic book or the scene itself.
        """
        # Verify that the issue exists
        from models.issue import Issue
        issue_obj = Issue.read(id = issue)
        if issue_obj is None:
            raise FileNotFoundError(f"issue {issue} not found")
        path = os.path.join(issue_obj.path(), "scenes", id)
        # Verify that the folder exists
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path {path} does not exist")
        
        filepath = os.path.join(path,"scene.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Scene {filepath} not found")
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)
        
    def revise_beatboard(self, feedback: str):
        """
        Revise the beatboard using generative AI
        """
        from models.issue import Issue
        issue_obj = Issue.read(id = self.issue)
        cast = "\n".join([f"* {key} - {value.description}" for key,value in issue_obj.characters.items()])
        panel_objects = [BeatBoardModel.read(issue=self.issue, scene=self.id, id=id) for id in self.panels]

        prior = BeatBoardsModel(id=self.id, story=self.story, issue=self.issue, style=self.style, panels=panel_objects)

        prompt = f"""
You are an agent designed to revise (and improve) a draft storyboard from a user's feedback.  Make no changes
to the storyboard except those that are necessary to address the feedback.   For now we will focus on BeatBoards --
we will refine them later once this initial draft is complete.

# CAST OF CHARACTERS
This is the list of the characters that appear in the production.   Not all of them will appear in every scene.
{cast}

Do not add any new characters to the story.  Only use the characters that are already in the cast of characters.

# PREVIOUS DRAFT
{prior.model_dump_json(indent=2)}

# AUTHOR'S FEEDBACK
{feedback}
"""
        # Invoke the OpenAI API to generate a scene description
        response = invoke_generate_api(prompt=prompt, text_format=SceneModel)
        # This might have introduced new panels, so we need to verify that all the panels have
        # unique ids that are valid guids
        prior_ids = issue_obj.panels
        posterior_ids = []
        for panel in response.panels:
            if panel.id in posterior_ids:
                # Duplicate, so generate a new id for it.
                panel.id = generate_unique_id(PANELS_FOLDER, create_folder=True)
            elif panel.id not in prior_ids:
                # New panel.   I don't know where the id came from, so generate a new id for it.
                panel.id = generate_unique_id(PANELS_FOLDER, create_folder=True)
            posterior_ids.append(panel.id)
            panel.write()

        # update the Storyboard with the new panels and/or style
        self.story = response.story
        self.style = response.style
        self.panels = [panel.id for panel in response.panels]
        self.write()

    def translate_beatboards(self):
        """
        Translate the beatboards into roughboards using generative AI
        """
        from models.issue import Issue
        issue_obj = Issue.read(id = self.issue)
        
        scene_characters  = {}

        priors = [BeatBoardModel.read(id) for id in self.panels]
        for prior in priors:
            for character in prior.characters:
                if character not in scene_characters:
                    scene_characters[character] = issue_obj.characters[character]
        cast = "\n".join([f"## {value.id}\n{value.format()}" for value in scene_characters.values()])

        beatboards = BeatBoardsModel(id=self.id, story=self.story, issue=self.issue, style=self.style, panels=priors)

        prompt = f"""
You are an expert in converting BeatBoards into RoughBoards.  You are given a list of panels that describe the story.
Your job is to convert each BeatBoard into a more detailed RoughBoard so that the artist can draw the scene.   Each
The actions, emotions and dialogue should be clear and concise to serve as stage directions for the actors.  Note
that character descriptions and thier wardrobe choices should only be included as part of the storyboard if they differ
from the character breifs.

# CAST OF CHARACTERS
This is the list of characters that appear in the scene.  Not all characters will appear in every panel.
{cast}

# BEATBOARD
{beatboards.model_dump_json(indent=2)}

# SPECIFIC INSTRUCTIONS
* Each panel should use the RoughBoardModel format (not the BeatBoardModel format).
* The foreground and background of the panel should include a detailed description of the set, props, etc so that they can be drawn consistently across different panels.
* Use dialog sparingly and only when necessary to convey the story.
* The actions, emotions and dialogue should be clear and concise to serve as stage directions for the actors.
"""
        # Invoke the OpenAI API to generate a scene description
        posterior = invoke_generate_api(prompt=prompt, text_format=RoughBoardsModel)
        # Save the roughboard panels
        prior_ids = issue_obj.panels
        posterior_ids = []
        for i, (beat, rough) in enumerate(zip(self.panels, posterior.panels)):
            if rough.id in posterior_ids:
                # Duplicate, so generate a new id for it.
                rough.id = generate_unique_id(PANELS_FOLDER, create_folder=True)
            elif rough.id not in prior_ids:
                # New panel.   I don't know where the id came from, so generate a new id for it.
                rough.id = generate_unique_id(PANELS_FOLDER, create_folder=True)
            rough.write()
            posterior_ids.append(rough.id)

        self.story = posterior.story
        self.style = posterior.style
        self.panels = posterior_ids
        self.write()

    def read_panel(self, index:int):
        """
        Read a panel from the scene
        """
        if index < 0 or index >= len(self.panels):
            raise IndexError(f"Panel index {index} out of range")
        # Try to read the panel as a RoughBoardModel.  If that fails, then read it as a BeatBoardModel
        # If that fails then raise an error.
        panel_id = self.panels[index]
        panel = RoughBoardModel.read(issue = self.issue, scene=self.id, id=panel_id)
        if panel is not None:
            return panel
        panel = BeatBoardModel.read(issue=self.issue, scene=self.id, id=panel_id)
        if panel is not None:
            return panel
        return None

    def read_panels(self):
        """
        Read the panels from the scene
        """
        panels = [self.read_panel(i) for i in range(len(self.panels))]
        if any(panel is None for panel in panels):
            none_index = panels.index(None)
            panel_id = self.panels[none_index]
            raise FileNotFoundError(f"Panel {panel_id} not found")
        return panels

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