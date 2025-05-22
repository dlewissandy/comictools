import os
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field
from models.character import CharacterModel
from models.issue import Issue
from helpers.constants import COMICS_FOLDER

class Series(BaseModel):
    series_title: str = Field(..., description="The series title of the comic book")
    description: str | None = Field(..., description="A short paragraph describing the comic book series")
    publisher: Optional[str] = Field(..., description="The publisher of the comic book.  Optional.  Default to None")
    logo: Optional[str] = Field(..., description="A refrerence image for the logo of the comic book.  Default to None")

    @property
    def id(self) -> str:
        """
        return the series id of the comic book
        """
        return self.series_title.lower().replace(" ", "-")
    
    @property
    def issues(self) -> list[int]:
        """
        return the list of issues in the series
        """
        contents = os.listdir(self.path())
        issues = []
        for item in contents:
            if item.isdigit():
                issues.append(int(item))
        return issues

    @property
    def characters(self) -> list[str]:
        """
        return the list of characters in the series
        """
        characters_path = os.path.join(self.path(), "characters")
        if not os.path.exists(characters_path):
            return []
        contents = os.listdir(characters_path)
        characters = []
        for item in contents:
            # if the item is a directory and not hidden, then it is a character
            if os.path.isdir(os.path.join(characters_path, item)) and not item.startswith("."):
                # We want the varants, so we will add the item to the list
                subcontents = os.listdir(os.path.join(characters_path, item))
                for subitem in subcontents:
                    if os.path.isdir(os.path.join(characters_path, item, subitem)) and not subitem.startswith("."):
                        # We want the varants, so we will add the item to the list
                        characters.append(f"{item}/{subitem}")
        return characters
    
    def get_character(self, name: str | None = None, variant: str | None = None, id: str | None = None) -> Optional[CharacterModel]:
        """
        Get a character from the series.  If the name is not provided, then the id must be provided.
        """
        character = CharacterModel.read(series=self.id, name=name, variant=variant, id=id)
        return character
    
    def get_characters(self) -> dict[str, CharacterModel]:
        """
        Get all the characters in the series.
        """
        characters = {}
        for character in self.characters:
            name, variant = character.split("/")
            character_model = CharacterModel.read(series=self.id, name=name, variant=variant)
            if character_model is not None:
                characters[character] = character_model
        return characters
    
    def get_issue(self, issue_number: int) -> Optional[Issue]:
        """
        Get an issue from the series.
        """
        issue = Issue.read(series_title=self.series_title, issue_number=issue_number)
        return issue
    
    def get_issues(self) -> dict[int, Issue]:
        """
        Get all the issues in the series.
        """
        issues = {}
        for issue_number in self.issues:
            issue = Issue.read(series_title=self.series_title, issue_number=issue_number)
            if issue is not None:
                issues[issue_number] = issue
        return issues

    def image_filepath(self) -> Optional[str]:
        """
        Get the filepath to a representative image for the series.   This will be the first cover image of any issue in the series.
        If there are no issues with cover images, or there are no issues in the series, then return None.
        """    

        issues = self.get_issues()
        if not issues:
            return None
        for issue in issues.values():
            if issue.cover and issue.cover != {}:
                image = issue.cover.get("front", None)
                if not image:
                    return None
                if image:
                    filepath = os.path.join(issue.path(), "covers", "front", "images", f"{image}.jpg")
                    if os.path.exists(filepath):
                        return filepath
        return None

    def path(self) -> str:
        """
        return the path to the panel model
        """
        return f"{COMICS_FOLDER}/{self.id}"
    
    def filepath(self) -> str:
        """
        return the filepath to the panel model
        """
        return os.path.join(self.path(), "series.json")

    def add_issue(self, **kwargs):
        """
        Create a new comic book.
        """
        # get all the subfolders in the series' folder that are numbers.  These will be
        # the issue numbers.  If there are no subfolders, then the issue number is 1.
        # If there are subfolders, then the issue number is the max of the subfolders + 1
        issue_number = 1
        issue_numbers = self.issues
        issue_number= max(issue_numbers) + 1 if issue_numbers else 1
        
        issue_number=kwargs.get("issue_number", issue_number)
        if issue_number in issue_numbers:
            raise ValueError(f"Issue {issue_number} already exists")
        
        issue = Issue(
            id = kwargs.get("id", f"{self.id}/{issue_number}"),
            series_title = self.series_title,
            issue_number = kwargs.get("issue_number", issue_number),
            issue_title = kwargs.get("issue_title", None),
            issue_date = kwargs.get("issue_date", None),
            logo = kwargs.get("logo", None),
            price = kwargs.get("price", None),
            writer = kwargs.get("writer", None),
            artist = kwargs.get("artist", None),
            colorist = kwargs.get("colorist", None),
            creative_minds = kwargs.get("creative_minds", None),
            cover = kwargs.get("cover", None),
            characters = kwargs.get("characters", []),
            style = kwargs.get("style", "vintage-four-color"),
            scenes = kwargs.get("scenes", []),
        )
        issue.write()
        return issue
        
        
    def generate_character(self, name: str, description: str,variant:Optional[str] = None) -> CharacterModel:
        """
        Generate a character based on the name and description.  The character is generated using the style of the comic book.
        """
        logger.info(f"name: {name}, description: {description}, variant: {variant}")
        # verify that the character does not already exist!
        character = CharacterModel.read(series=self.series_title, name=name, variant=variant)
        if character is None:
            character = CharacterModel.generate(name=name, description=description, variant=variant, series=self.id)
            if character is None:
                raise ValueError(f"Character {name} could not be generated")
        logger.info(f"Add character {name} to series {self.series_title}")
        return character
    
    def revise_character(self, name:str, feedback: str, variant: Optional[str] = None) -> CharacterModel:
        """
        Revise a character based on the feedback.  The character is revised using the style of the comic book.
        """
        logger.info(f"name: {name}, variant: {variant}, feedback: {feedback}")
        character = CharacterModel.read(series=self.id, name=name, variant=variant)
        if character is None:
            raise ValueError(f"Character {name}:{variant} not found")
        revised = character.revise(feedback=feedback)
        return revised

    
    def write(self):
        """
        Save the series to a file.
        """
        path = self.path()
        if not os.path.exists(path):
            os.makedirs(path)
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))  

    @classmethod
    def read(cls, series_title: Optional[str]=None, id: Optional[str] = None) -> Optional["Series"]:
        """
        Load the comic series from a file.

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
        if series_title is not None:
            id = series_title.lower().replace(" ", "-")
        filepath = os.path.join(COMICS_FOLDER, id, "series.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)
        
    def format(self):
        self_json = self.model_dump()
        result = "## Series\n\n"
        for key, value in self_json.items():
            if value is None or value == "":
                continue
            result += f"* **{key.replace('_', ' ').capitalize()}**: {value}\n\n"
        return result
