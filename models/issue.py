import os
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field
from models.character import CharacterModel
from models.scene import SceneModel
from models.panel import TitleBoardModel, CoverLocation
from models.scene import SceneModel
from helpers.constants import COMICS_FOLDER
from helpers.generator import invoke_generate_api

        

class Issue(BaseModel):
    id: str = Field(..., description="A unique identifier for the comic book.   Default to 'series_title/issue_number'")
    style: str = Field(..., description="The style of the comic book.  Default to 'vintage-four-color'")
    series_title: str = Field(..., description="The title of the comic book")
    issue_title: Optional[str] = Field(..., description="The title of the issue.  Optional.  Default to None")
    issue_number: int = Field(..., description="The issue number.  Optional.  default to 1")
    issue_date: Optional[str] = Field(..., description="The date of the issue.  Optional.  Default to None")
    logo: Optional[str] = Field(..., description="A refrerence image for the logo of the comic book.  Default to None")
    price: Optional[float] = Field(..., description="The price of the issue.  Default to None")
    writer: Optional[str] = Field(..., description="The writer of the issue.  Optional.   Default to None")
    artist: Optional[str] = Field(..., description="The artist of the issue.  Optional.   Default to None")
    colorist: Optional[str] = Field(..., description="The colorist of the issue.  Optional.   Default to None")
    creative_minds: Optional[str] = Field(..., description="The creative minds behind the issue. Optional. Default to None")

    cover: Optional[dict[str, str]] = Field(..., description="The cover pages of the issue.   Default to None")
    characters: list[str] = Field(..., description="The characters in the issue.  Default to empty string")
    style: Optional[str]  = Field(..., description="The style of the comic book.   Default to 'vintage-four-color'")
    scenes: list[str] = Field(..., description="The scenes of the issue. Default to empty list")

    @property
    def name(self) -> str:
        """
        return the name of the comic book.
        """
        if self.issue_title is not None:
            return f"{self.issue_title}"
        return f"{self.series_title} {self.issue_number}"

    def _series(self) -> str:
        """
        return the series of the comic book
        """
        from models.series import Series
        return Series.read(series_title=self.series_title)
    
    def get_scenes(self) -> list[SceneModel]:
        """
        return the scenes of the comic book
        """
        scenes = []
        for scene_id in self.scenes:
            scene = SceneModel.read(id=scene_id, issue=self.id)
            if scene is not None:
                scenes.append(scene)
        return scenes

    @property
    def series_id(self) -> str:
        """
        return the series id of the comic book
        """
        return self.series_title.lower().replace(" ", "-")

    def path(self) -> str:
        """
        return the path to the panel model
        """
        return f"{COMICS_FOLDER}/{self.id}"
    
    def filepath(self) -> str:
        """
        return the filepath to the panel model
        """
        return os.path.join(self.path(), "comic.json")
   
    def add_character(self, name: str, variant: str | None = None):
        """
        Add a character to the comic book.   Note, if the character already exists, it will be replaced.
        """
        # Verify that the character exists
        character = CharacterModel.read(series=self.series_id, name=name, variant=variant)
        if character is None:
            # Does not exist!
            if variant is None or variant == "":
                variant = "base"
            raise ValueError(f"Character {name}, variant {variant} not found")
        # Verify that the character is not already in the issue
        if character.id in self.characters:
            return
        self.characters.append(character.id)
        self.write()

    def image_filepath(self) -> Optional[str]:
        """
        return the image of the comic book
        """
        if self.cover is None or self.cover == {}:
            return None
        for key, value in self.cover.items():
            value = TitleBoardModel.read(issue=self.id, location=CoverLocation(key))
            if value.image is not None:
                return os.path.join(self.path(), "covers", key, "images", f"{value.image}.jpg")
        return None

    def delete_character(self, name: str, variant: str | None = None):
        """
        Delete a character from the comic book.  Remove it from any frames that it appears in.
        """
        if variant is None or variant == "":
            variant = "base"
        semantic_id = f"{name}/{variant}".to_lower().replace(" ", "-")
        if semantic_id in self.characters:
            del self.characters[semantic_id]
            self.write()


    def generate_scene(self, story: str, before: int | None = None, after: int | None = None):
        """
        Generate a scene based on the story.  The scene is generated using the style of the comic book.
        """
        logger.info(f"Generate scene with story: {story}")
        scene = SceneModel.generate(story=story, issue = self.id)
        self.add_scene(scene_id=scene.id, before=before, after=after)
        return scene

    def revise_beatboards(self, feedback: str, index: int):
        """
        Revise a scene based on the feedback.  The scene is revised using the style of the comic book.
        """
        if index < 0 or index >= len(self.scenes):
            raise IndexError(f"Scene index {index} out of range")
        logger.info(f"Revise scene {index} with feedback: {feedback}")
        scene = self.scenes[index]
        scene.revise_beatboard(feedback=feedback)
        self.write()

    def translate_beatboards(self, index: int):
        """
        Translate a scene comprised of beatboards into a scene with RoughBoards
        """
        if index < 0 or index >= len(self.scenes):
            raise IndexError(f"Scene index {index} out of range")
        logger.info(f"Translate scene {index} into RoughBoards")
        scene = self.scenes[index]
        scene.translate_beatboards()
        self.write()
        
    def generate_character(self, name: str, description: str,variant:Optional[str] = None) -> CharacterModel:
        """
        Generate a character based on the name and description.  The character is generated using the style of the comic book.
        """
        logger.info(f"name: {name}, description: {description}, variant: {variant}")
        # verify that the character does not already exist!
        character = CharacterModel.read(series=self.series_title, name=name, variant=variant)
        if character is None:
            character = CharacterModel.generate(name=name, description=description, variant=variant, series=self.series_id())
            if character is None:
                raise ValueError(f"Character {name} could not be generated")
        logger.info(f"Add character {name} to comic book")
        self.add_character(name=character.name, variant=character.variant)
        return character
    
    def revise_character(self, name:str, feedback: str, variant: Optional[str] = None) -> CharacterModel:
        """
        Revise a character based on the feedback.  The character is revised using the style of the comic book.
        """
        logger.info(f"name: {name}, variant: {variant}, feedback: {feedback}")
        character = CharacterModel.read(series=self.series_id(), name=name, variant=variant)
        if character is None:
            raise ValueError(f"Character {name}:{variant} not found")
        revised = character.revise(feedback=feedback)
        self.write()
        return revised

    def add_scene(self, scene_id: str, before: int | None = None, after: int | None = None):
        """
        Add a scene to the comic book.  Note, if the scene already exists, it will be replaced.
        """
        if before is not None and after is not None:
            raise ValueError("Cannot specify both before and after")
        
        if before is not None and (before < 0 or before >= len(self.scenes)):
            raise IndexError(f"Scene index {before} out of range")
        if after is not None and (after < 0 or after >= len(self.scenes)):
            raise IndexError(f"Scene index {after} out of range")

        if before is not None:
            self.scenes.insert(before, scene_id)
        elif after is not None:
            self.scenes.insert(after + 1, scene_id)
        else:
            self.scenes.append(scene_id)
        self.write()        

    def delete_scene(self, index: int):
        """
        Delete a page from the comic book.  Remove it from any frames that it appears in.
        """
        if index < 0 or index >= len(self.scenes):
            raise IndexError(f"Scene index {index} out of range")
        logger.info(f"Delete scene {index}")
        del self.scenes[index]
        self.write()


    def add_cover(self, cover: TitleBoardModel):
        """
        Add a cover to the comic book.  Note, if the cover already exists, it will be replaced.
        """
        pass

    def delete_cover(self):
        """
        Delete the cover from the comic book.
        """
        pass

    def write(self):
        """
        Save the comic book to a file.
        """
        path = self.path()
        if not os.path.exists(path):
            os.makedirs(path)
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))  

    @classmethod
    def read(cls, series_title: Optional[str]=None, issue_number: Optional[int]=None, id: Optional[str] = None) -> Optional["Issue"]:
        """
        Load the comic book from a file.

        Args:
            series_title (str): The title of the comic book.  Optional.  Default to None
            issue_number (int): The issue number.  Optional.  default to 1
            id (str): The id of the comic book.  Optional.  Default to None
        NOTE: You must provide either the id or the series_title and issue_number

        Returns:
            Either a ComicBookModel object or None if the comic book does not exist.
        """
        if id is None and series_title is None:
            raise ValueError("Either id or series_title and issue_number must be provided")
        if id is None:
            if issue_number is None:
                issue = 1
            id = f"{series_title.lower().replace(' ', '-')}/{issue_number}".replace(" ", "-")
        filepath = os.path.join(COMICS_FOLDER, id, "comic.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)

    def format(self, header_level: int=1, no_covers: bool=False, no_scenes: bool=False, no_style:bool=False) -> str:
        """
        Format the comic book for display
        """
        text = f"{'#'* header_level} ISSUE {self.issue_number}\n\n"
        if self.issue_title is not None:
            text += f" * **title** {self.issue_title}\n\n"
        if self.issue_date is not None:
            text += f" * **date** {self.issue_date}\n\n"
        if self.writer is not None:
            text += f" * **writer** {self.writer}\n\n"
        if self.artist is not None:
            text += f" * **artist** {self.artist}\n\n"
        if self.colorist is not None:
            text += f" * **colorist** {self.colorist}\n\n"
        if self.creative_minds is not None:
            text += f" * **creative minds** {self.creative_minds}\n\n"
        if self.logo is not None:
            text += f" * **logo** {self.logo}\n\n"
        if self.price is not None:
            text += f" * **price** {self.price}\n\n"
        if self.style is not None and not no_style:
            text += f" * **style** {self.style}\n\n"

        if self.characters is not None and len(self.characters) > 0:
            text += f" * **characters** {', '.join(self.characters)}\n\n"

        if self.cover is not None and not no_covers:
            for cover_type, cover_id in self.cover.items():
                cover = TitleBoardModel.read(issue=self.id, id=cover_id)
                if not cover:
                    continue
                cover.format(header_level=header_level+1)
        
        if self.scenes is not None and len(self.scenes) > 0 and not no_scenes:
            text += f"{'#'* (header_level+1)}  SCENES\n\n"

            for i,scene in enumerate(self.get_scenes()):
                text += f"* **scene {i+1}** {scene.story}\n\n"
        return text