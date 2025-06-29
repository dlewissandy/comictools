import os
import json
import shutil
from uuid import uuid4
from loguru import logger
from typing import Optional, BinaryIO
from pydantic import BaseModel
from storage.generic import GenericStorage
from schema import *
from gui.selection import SelectedKind

SERIES_NOT_FOUND_MESSAGE = lambda series_id: f"Series with ID {series_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all series."
CHARACTER_NOT_FOUND_MESSAGE = lambda character_id: f"Character with ID {character_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all characters."
STYLE_NOT_FOUND_MESSAGE = lambda style_id: f"Style with ID {style_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all styles."
PUBLISHER_NOT_FOUND_MESSAGE = lambda publisher_id: f"Publisher with ID {publisher_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all publishers."
ISSUE_NOT_FOUND_MESSAGE = lambda issue_id: f"Issue with ID {issue_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all issues."

TOPOSORT_ORDER = [
    "publisher_id",
    "series_id",
    "issue_id",
    "location",
    "character_id",
    "variant_id",
    "scene_id",
    "panel_id",
    "style_id",
    "image_id",
    "relation"
]

BASE_PATH = "data"

PATH_TEMPLATES = {}
ROOT_PATH_TEMPLATES = {}
ROOT_PATH_TEMPLATES[SelectedKind.PUBLISHER.value] = os.path.join("{base_path}", "publishers")
PATH_TEMPLATES[SelectedKind.PUBLISHER.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.PUBLISHER.value], "{publisher_id}")
ROOT_PATH_TEMPLATES[SelectedKind.STYLE.value] = os.path.join("{base_path}", "styles")
PATH_TEMPLATES[SelectedKind.STYLE.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.STYLE.value], "{style_id}")
ROOT_PATH_TEMPLATES[SelectedKind.SERIES.value] = os.path.join("{base_path}", "series")
PATH_TEMPLATES[SelectedKind.SERIES.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.SERIES.value], "{series_id}")
ROOT_PATH_TEMPLATES[SelectedKind.CHARACTER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SERIES.value], "characters")
PATH_TEMPLATES[SelectedKind.CHARACTER.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.CHARACTER.value], "{character_id}")
ROOT_PATH_TEMPLATES[SelectedKind.VARIANT.value] = os.path.join(PATH_TEMPLATES[SelectedKind.CHARACTER.value], "variants")
PATH_TEMPLATES[SelectedKind.VARIANT.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.VARIANT.value], "{variant_id}")
ROOT_PATH_TEMPLATES[SelectedKind.ISSUE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SERIES.value], "issues")
PATH_TEMPLATES[SelectedKind.ISSUE.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.ISSUE.value], "{issue_id}")
ROOT_PATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.ISSUE.value], "covers")
PATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.COVER.value], "{location}")
ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.ISSUE.value], "scenes")
PATH_TEMPLATES[SelectedKind.SCENE.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value], "{scene_id}")
ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SCENE.value], "panels")
PATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value], "{panel_id}")

ROOT_PATH_TEMPLATES[ComicStyle.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.STYLE.value]
ROOT_PATH_TEMPLATES[Series.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.SERIES.value]
ROOT_PATH_TEMPLATES[Publisher.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
ROOT_PATH_TEMPLATES[CharacterModel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.CHARACTER.value]
ROOT_PATH_TEMPLATES[CharacterVariant.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.VARIANT.value]
ROOT_PATH_TEMPLATES[Issue.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.ISSUE.value]
ROOT_PATH_TEMPLATES[Cover.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.COVER.value]
ROOT_PATH_TEMPLATES[SceneModel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value]
ROOT_PATH_TEMPLATES[Panel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value]
PATH_TEMPLATES[ComicStyle.__name__] = PATH_TEMPLATES[SelectedKind.STYLE.value]
PATH_TEMPLATES[Series.__name__] = PATH_TEMPLATES[SelectedKind.SERIES.value]
PATH_TEMPLATES[Publisher.__name__] = PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
PATH_TEMPLATES[CharacterModel.__name__] = PATH_TEMPLATES[SelectedKind.CHARACTER.value]
PATH_TEMPLATES[CharacterVariant.__name__] = PATH_TEMPLATES[SelectedKind.VARIANT.value]
PATH_TEMPLATES[Issue.__name__] = PATH_TEMPLATES[SelectedKind.ISSUE.value]
PATH_TEMPLATES[Cover.__name__] = PATH_TEMPLATES[SelectedKind.COVER.value]
PATH_TEMPLATES[SceneModel.__name__] = PATH_TEMPLATES[SelectedKind.SCENE.value]
PATH_TEMPLATES[Panel.__name__] = PATH_TEMPLATES[SelectedKind.PANEL.value]
PATH_TEMPLATES[StyledImage.__name__] = os.path.join(BASE_PATH, "styled_images", "{image_id}")

FILEPATH_TEMPLATES = {}
FILEPATH_TEMPLATES[SelectedKind.PUBLISHER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.PUBLISHER.value], "publisher.json")
FILEPATH_TEMPLATES[SelectedKind.SERIES.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SERIES.value], "series.json")
FILEPATH_TEMPLATES[SelectedKind.STYLE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.STYLE.value], "style.json")
FILEPATH_TEMPLATES[SelectedKind.CHARACTER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.CHARACTER.value], "character.json")
FILEPATH_TEMPLATES[SelectedKind.VARIANT.value] = os.path.join(PATH_TEMPLATES[SelectedKind.VARIANT.value], "variant.json")
FILEPATH_TEMPLATES[SelectedKind.ISSUE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.ISSUE.value], "issue.json")
FILEPATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.COVER.value], "cover.json")
FILEPATH_TEMPLATES[SelectedKind.SCENE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SCENE.value], "scene.json")
FILEPATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(PATH_TEMPLATES[SelectedKind.PANEL.value], "panel.json")
FILEPATH_TEMPLATES[Publisher.__name__] = FILEPATH_TEMPLATES[SelectedKind.PUBLISHER.value]
FILEPATH_TEMPLATES[Series.__name__] = FILEPATH_TEMPLATES[SelectedKind.SERIES.value]
FILEPATH_TEMPLATES[ComicStyle.__name__] = FILEPATH_TEMPLATES[SelectedKind.STYLE.value]
FILEPATH_TEMPLATES[CharacterModel.__name__] = FILEPATH_TEMPLATES[SelectedKind.CHARACTER.value]
FILEPATH_TEMPLATES[CharacterVariant.__name__] = FILEPATH_TEMPLATES[SelectedKind.VARIANT.value]
FILEPATH_TEMPLATES[Issue.__name__] = FILEPATH_TEMPLATES[SelectedKind.ISSUE.value]
FILEPATH_TEMPLATES[Cover.__name__] = FILEPATH_TEMPLATES[SelectedKind.COVER.value]
FILEPATH_TEMPLATES[SceneModel.__name__] = FILEPATH_TEMPLATES[SelectedKind.SCENE.value]
FILEPATH_TEMPLATES[Panel.__name__] = FILEPATH_TEMPLATES[SelectedKind.PANEL.value]

def get_basenames(path: str, exts: list[str] = None) -> list[str]:
    """
    Get all files and folders in a folder, excluding hidden folders.
    """
    logger.trace(f"Getting basenames from path: {path}")
    if not os.path.exists(path):
        msg = f"Path {path} does not exist."
        logger.error(msg)
        raise FileNotFoundError(msg)
    
    if not os.path.isdir(path):
        msg = f"Path {path} is not a directory."
        logger.error(msg)
        raise NotADirectoryError(msg)
    
    contents = []
    for item in os.listdir(path):
        # skip hidden folders
        if item.startswith("."):
            logger.debug(f"Skipping hidden item: {item}")
            continue
        if exts is not None and not any(item.endswith(ext) for ext in exts):
            logger.debug(f"Skipping item {item} with unsupported extension.")
            continue
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            contents.append(item)
        else:
            # strip the file extension
            item = os.path.splitext(item)[0]
            contents.append(item)
    logger.debug(f"Found {len(contents)} items in {path}")
    return contents

def extract_format_keys(fmt) -> set[str]:
    from string import Formatter
    """
    Extracts the field names from a format string.
    Args:
        fmt (str): The format string to parse.
    Returns:
        set: A set of field names found in the format string.
    """
    return {field_name for _, field_name, _, _ in Formatter().parse(fmt) if field_name}



def template_to_filepath(template: Optional[str], pk: dict[str,str]={}, base_path: str = BASE_PATH) -> str:
    """
    Convert a template string to a filepath by formatting it with the primary key.
    Throws Key error if the primary key is missing a required key, and value
    error if the template is None.

    Args: 
        template (str): The template string to format.
        pk (dict[str,str]): The primary key to use for formatting the template.
    """
    if template is None:
        msg = "Cannot perform file operation.   Path template not found."
        logger.error(msg)
        raise ValueError(msg)
    try:
        return template.format(**pk, base_path=base_path)
    except KeyError as e:
        msg = f"Failed to format filepath for template {template} with primary key {pk}. Missing key: {e}"
        logger.error(msg)
        raise KeyError(msg) from e

def cls_to_filepath(cls: type[BaseModel], pk: dict[str,str]={}, base_path: str = BASE_PATH) -> str:
    """
    Get the filepath to a particular object for the given primary key.
    """
    clsname = cls.__name__
    template = FILEPATH_TEMPLATES.get(clsname, None)
    return template_to_filepath(template=template, pk=pk, base_path=base_path)

def cls_to_rootpath(cls: type[BaseModel], pk: dict[str,str]={}) -> str:
    """
    Get the root path to a particular object for the given primary key.
    This is the path to the folder that contains the object.
    """
    clsname = cls.__name__
    template = ROOT_PATH_TEMPLATES.get(clsname, None)
    return template_to_filepath(template=template, pk=pk, base_path=BASE_PATH)

def obj_to_filepath(obj: BaseModel, base_path: str = BASE_PATH) -> str:
    """
    Get the filepath to a particular object.
    """
    clsname = obj.__class__.__name__
    template = FILEPATH_TEMPLATES.get(clsname, None)
    return template_to_filepath(template=template, pk=obj.primary_key, base_path=base_path)

  
def obj_to_rootpath(obj: BaseModel, base_path: str = BASE_PATH) -> str:
    """
    Get the root path to a particular object.
    This is the path to the folder that contains the object.
    """
    clsname = obj.__class__.__name__
    template = ROOT_PATH_TEMPLATES.get(clsname, None)
    return template_to_filepath(template=template, pk=obj.primary_key, base_path=base_path)
    

def generate_unique_id(path: str, create_folder: bool = True) -> str:
    """
    Generate a unique ID.  This will be used as a folder for generated image assets.

    Args:
        path (str): The path to the folder where the unique ID will be created.
        create_folder (bool): Whether to create the folder if it does not exist. Defaults to True.
        name (str): an optional name for the folder.   If not provided, or if the 
            name is not unique, a UUID4 will be used.  The name will be converted to lowercase
            snake-case. 
    """
    logger.trace(f"Generating unique ID in path")
    # verify that the path is a directory
    if not os.path.isdir(path):
        logger.error(f"Path {path} is not a directory.")
        raise NotADirectoryError(f"Path {path} is not a directory.")

    # ensure that the path exists
    if not os.path.exists(path):
        os.makedirs(path)

    # get the names of all the folders rooted at the path, excluding hidden folders
        
    contents = get_basenames(path)
    result = str(uuid4()) 
    while result in contents:
        result = str(uuid4())
    # create the folder
    if create_folder:
        os.makedirs(os.path.join(path, result))
    return result

class LocalStorage(GenericStorage):

    def __init__(self, base_path: str):
        super().__init__()
        self.base_path = base_path
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)



    def create_object(self, data: BaseModel) -> str:
        """
        Create a new object in the specified path with the given data.
        """
        logger.trace(f"creating {data.__class__.__name__} with data: {data.model_dump()}")

        rootpath = ROOT_PATH_TEMPLATES.get(data.__class__.__name__, None)
        if not os.path.exists(rootpath):
            os.makedirs(rootpath)        
        if not os.path.isdir(rootpath):
            raise NotADirectoryError(f"Path {rootpath} is not a directory.")
        
        # Generate a unique ID for the object
        data.id = generate_unique_id(path=rootpath, create_folder=True)
        filepath = obj_to_filepath(data)  # This will raise an error if the object is not valid
        parent_path = os.path.dirname(filepath)
        # make sure that file's folder exists
        if not os.path.exists(parent_path):
            os.makedirs(os.path.dirname(filepath))
        if not os.path.isdir(parent_path):
            raise NotADirectoryError(f"Path {parent_path} is not a directory.")

        with open(filepath, 'w') as f:
            f.write(data.model_dump_json(indent=2))
        return data.id

    def read_object(self, cls: BaseModel, primary_key: dict[str,str]={}) -> Optional[BaseModel]:
        """
        Read an object from a file and return it as an instance of the specified class.

        Args:
            cls (BaseModel): The class to which the object should be converted.
            primary_key (dict[str,str]): The primary key of the object to read.   This is used to
              construct the filepath to the object.
        """
        logger.trace(f"Reading {cls.__name__} object with primary key: {primary_key}")
        filepath = cls_to_filepath(cls=cls, pk=primary_key)


        if not os.path.exists(filepath):
            logger.warning(f"File {filepath} does not exist. Returning None.")
            return None
        
        if not os.path.isfile(filepath):
            logger.error(f"Path {filepath} is not a file.")
            raise FileNotFoundError(f"Path {filepath} is not a file.")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        try: 
            return cls.model_validate(data)
        except Exception as e:
            msg = f"Failed to validate: {e}"
            logger.error(msg)
            raise
            
    def read_all_objects(self, cls: BaseModel, primary_key: dict[str,str] = {}) -> list[BaseModel]:
        """
        Read all objects from a directory and return them as a list of instances of the specified class.
        
        Args:
            cls (BaseModel): The class to which the objects should be converted.
            primary_key (dict[str,str]): The primary key of the parent object (if any).   This is used to
              construct the filepath to the object.
        """
        logger.trace(f"Reading all {cls.__name__} objects relative to primary key {primary_key}")
        # Determine the root path and filepath template for the class
        rootpath_template = ROOT_PATH_TEMPLATES.get(cls.__name__, None)
        filepath_template = FILEPATH_TEMPLATES.get(cls.__name__, None)
        if rootpath_template is None:
            msg = f"Root path template for class {cls.__name__} not found."
            logger.error(msg)
            raise ValueError(msg)
        if filepath_template is None:
            msg = f"Filepath template for class {cls.__name__} not found."
            logger.error(msg)
            raise ValueError(msg)
        rootpath_template: str = rootpath_template
        filepath_template: str = filepath_template

        # There should be exactly one key that is in the filepath template that is not
        # in the primary key.   We need to know which key is missing so that we can
        # Can populate that with the correct value later.
        rootpath_keys = extract_format_keys(rootpath_template)
        filepath_keys = extract_format_keys(filepath_template)
        missing_keys = filepath_keys - rootpath_keys

        if len(missing_keys) != 1:
            msg = f"Expected exactly one missing key in the rootpath template {rootpath_template} for class {cls.__name__}.   Found {len(missing_keys)} missing keys: {missing_keys}."
            logger.error(msg)
            raise ValueError(msg)
        missing_key = list(missing_keys)[0]

        rootpath = template_to_filepath(template=rootpath_template, pk=primary_key)

        if not os.path.exists(rootpath):
            logger.warning(f"Path {rootpath} does not exist. Returning empty list.")
            return []
        
        if not os.path.isdir(rootpath):
            msg = f"Path {rootpath} is not a directory."
            logger.error(msg)
            raise NotADirectoryError(msg)
        
        
        objects = []
        # Get all the non-hidden folders in the path
        subfolders = get_basenames(rootpath)
        for folder in subfolders:
            obj = self.read_object(cls, primary_key={**primary_key, missing_key: folder})
            if obj:
                objects.append(obj)
        logger.debug(f"Found {len(objects)} objects of type {cls.__name__} in {rootpath}")
        return objects
        

    def update_object(self, data: BaseModel) -> None:
        """
        Update an existing object in the specified file with the given data.
        
        Args:
            filepath (str): The path to the file containing the object.
            data (BaseModel): The data to update the object with.
        """
        logger.trace(f"Updating {data.__class__.__name__} with data: {data.model_dump()}")
        filepath = obj_to_filepath(data)  # This will raise an error if the object is not valid
        
        if not os.path.exists(filepath):
            logger.error(f"File {filepath} does not exist. Cannot update.")
            raise FileNotFoundError(f"File {filepath} does not exist.")
        
        if not os.path.isfile(filepath):
            logger.error(f"Path {filepath} is not a file.")
            raise NotADirectoryError(f"Path {filepath} is not a file.")
        
        with open(filepath, 'w') as f:
            f.write(json.dumps(data.model_dump(), indent=2))

    def delete_object(self, cls: BaseModel, primary_key: dict[str,str]) -> Optional[BaseModel]:
        """
        Delete an object from a file.   If it existed, then return the object so
        that it could be used for further processing (e.g. logging, undoing, unlinking, etc).

        Args:
            filepath (str): The path to the file containing the object.
            delete_folder (bool): Whether to delete the folder containing the object. Defaults to True.
            cls (BaseModel): The class of the object to be deleted.
        """

        logger.trace(f"Deleting {cls.__name__} with primary key: {primary_key}")
        instance = self.read_object(cls=cls, primary_key=primary_key)
        logger.debug(f"Instance to delete: {instance}")
        if instance is None:
            logger.warning(f"File {cls.__name__} does not exist. Cannot delete.")
            return None
        
        filepath = obj_to_filepath(instance)
        logger.debug(f"Deleting file at {filepath}")
        shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        return instance

    # -------------------------------------------------------------------------
    # Series CRUD Operations
    # -------------------------------------------------------------------------
    def create_series(self, data: Series) -> str:
        return self.create_object(data =data)
    
    def update_series(self, data: Series) -> None:
        return self.update_object(data=data)
    
    def delete_series(self, id: str) -> Optional[Series]:
        return self.delete_object(cls=Series, primary_key={"series_id": id})
        
    
    def find_series_image(self, series_id: str) -> Optional[str]:
        issues: list[Issue] = self.read_all_objects(cls=Issue, primary_key={"series_id": series_id})
        # sort the issues by issue number
        issues.sort(key=lambda x: x.issue_number if x.issue_number is not None else float('inf'))
        for issue in issues:
            issue_covers = self.read_all_objects(Cover, primary_key={"series_id": series_id, "issue_id": issue.issue_id})
            if issue_covers and issue_covers != []:
                cover = issue_covers[0]
                image = cover.image
                if not image:
                    return None
                if image:
                    if os.path.exists(image):
                        return image
        return None

    # -------------------------------------------------------------------------
    # Issue CRUD Operations
    # -------------------------------------------------------------------------
    def create_issue(self, data: Issue) -> str:
        return self.create_object(data=data, base_path = self.base_path)
    
    def update_issue(self,  data: Issue) -> None:
        return self.update_object( data=data)

    
    def delete_issue(self, series_id: str, id: str) -> Optional[Issue]:
        return self.delete_object(cls=Issue,
            primary_key={"series_id": series_id, "issue_id": id}
        )

    
    def find_issue_style(self, series_id: str, id: str) -> Optional[ComicStyle]:
        """
        Read the style of an issue.
        """
        issue = self.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": id})
        if issue is None:
            logger.warning(ISSUE_NOT_FOUND_MESSAGE(id))
            return None
        return self.read_object(cls=ComicStyle, primary_key={"style_id": issue.style_id})

    def find_issue_image(self, series_id: str, issue_id: str) -> Optional[str]:
        covers: list[Cover] = self.read_all_objects(Cover, primary_key={"series_id": series_id, "issue_id": issue_id} )
        # Sort the covers in order Front, Back, Inside Front, Inside Back
        priorities = [CoverLocation.FRONT, CoverLocation.BACK, CoverLocation.INSIDE_FRONT, CoverLocation.INSIDE_BACK]
        covers.sort(key=lambda x: priorities.index(x.location) if x in priorities else len(priorities))
        # Return the first cover that has an image
        for cover in covers:
            if cover.image is not None:
                return cover.image
        return None

    # -------------------------------------------------------------------------
    # Cover CRUD Operations
    # -------------------------------------------------------------------------
    

    def create_cover(self, data):
        raise NotImplemented("Not yet implemented")

    
    def update_cover(self, data: Cover) -> None:
        self.update_object(
            data=data
        )

    
    def delete_cover(self, series_id: str, issue_id: str, location: CoverLocation) -> Optional[Cover]:
        raise NotImplemented("Not yet implemented")

    
    def read_cover_images(self, cover_id):
        raise NotImplemented("Not yet implemented")

    
    def read_cover_style(self, cover_id):
        """
        Read the style of a cover.
        """
        raise NotImplemented("Not yet implemented")

    
    def read_cover_characters(self, cover_id):
        """
        Read all characters featured on a cover.
        """
        raise NotImplemented("Not yet implemented")

    
    def read_cover_reference_images(self, cover_id):
        """
        Read all reference images used for a cover.
        """
        raise NotImplemented("Not yet implemented")
    
    def find_cover_image(self, series_id: str, issue_id: str, location: CoverLocation) -> Optional[str]:
        """
        Find the image of a cover.
        """
        logger.trace("cover.image_filepath() called")
        cover = self.read_object(cls=Cover, primary_key={"series_id": series_id, "issue_id": issue_id, "location": location})
        if cover is None:
            logger.warning(f"Cover {location.value} for issue {issue_id} in series {series_id} not found.")
            return None
        if cover.image is None:
            logger.warning(f"Cover {location.value} for issue {issue_id} in series {series_id} has no image.")
            return None
        filename = cover.image
        filepath = self._cover_image_filepath(series_id=series_id, issue_id=issue_id, location=location, image_name=filename)
        if filepath is None:
            logger.warning(f"Cover image filepath for {location.value} cover of issue {issue_id} in series {series_id} is None.")
            return None
        if os.path.exists(filepath):
            return filepath
        else:
            logger.warning(f"Cover image {filepath} does not exist.")
            return None
        
    def find_cover_images(self, series_id: str, issue_id: str, location: CoverLocation) -> list[str]:
        """
        Find all images of a cover.
        """
        logger.trace("cover.image_filepaths() called")
        cover = self.read_object(cls=Cover, primary_key={"series_id": series_id, "issue_id": issue_id, "location": location})
        if cover is None:
            logger.warning(f"Cover {location.value} for issue {issue_id} in series {series_id} not found.")
            return []
        if cover.image is None:
            logger.warning(f"Cover {location.value} for issue {issue_id} in series {series_id} has no image.")
            return []
        
        images_path = _cover_image_path(issue_id=issue_id, series_id=series_id, location=location)
        if not os.path.exists(images_path):
            logger.warning(f"Cover image path {images_path} does not exist.")
            return []
        
        images = []
        for img in os.listdir(images_path):
            if img.startswith("."):
                logger.debug(f"Skipping hidden image: {img}")
                continue
            
            img_filepath = os.path.join(images_path, img)
            if not os.path.isfile(img_filepath):
                logger.debug(f"Skipping non-file item: {img}")
                continue
            
            images.append(img_filepath)
        return images
    
    def find_cover_reference_images(self, series_id: str, issue_id: str, location: CoverLocation) -> list[str]:
        """
        Find all reference images used for a cover.
        """
        logger.trace("cover.reference_image_filepaths() called")
        cover = self.read_object(Cover, primary_key={"series_id": series_id, "issue_id": issue_id, "location": location})
        if cover is None:
            logger.warning(f"Cover {location.value} for issue {issue_id} in series {series_id} not found.")
            return []
        
        cover: Cover = cover
        return cover.reference_images


    # -------------------------------------------------------------------------
    # Character CRUD Operations
    # -------------------------------------------------------------------------
    
    def create_character(self, data: CharacterModel) -> str:
        return self.create_object(data=data)

        
    def update_character(self, data: CharacterModel) -> None:
        return self.update_object(
            data=data
        )

    
    def delete_character(self, series_id: str, character_id: str) -> Optional[CharacterModel]:
        return self.delete_object(
            cls=CharacterModel,
            primary_key={
                "series_id": series_id,
                "character_id": character_id
            }
        )
            
    def find_character_image(self, series_id: str, character_id: str) -> Optional[str]:
        """
        Find the image of a character.
        """
        logger.trace("character.image_filepath() called")
        # Get the base variant
        variants = self.read_all_objects(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id})
        while len(variants) > 0:
            variant = variants.pop(0)
            filepath = self.find_variant_image(series_id=series_id, character_id=character_id, variant_id=variant.variant_id)
            if filepath is not None:
                return filepath
        # If no image is found, return None
        return None
    

    # -------------------------------------------------------------------------
    # CharacterVariant CRUD Operations
    # -------------------------------------------------------------------------
    
    def create_character_variant(self, data: CharacterVariant):
        return self.create_object(data=data)

        
    def update_character_variant(self, data: CharacterVariant):
        return self.update_object(
            data=data
        )

    
    def delete_character_variant(self, series_id: str, character_id: str, variant_id: str):
        raise NotImplemented("Not yet implemented")
    
    def find_variant_image(self, series_id: str, character_id: str, variant_id: str) -> Optional[str]:
        """
        Find the image of a character variant.
        """
        """
        return the filepath to the representative image for the character model
        """
        # We are going to try to find an image using any of the styles
        variant = self.read_object(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id, "variant_id": variant_id})
        if variant is None:
            logger.warning(f"Variant {variant_id} for character {character_id} in series {series_id} not found.")
            return None
        variant: CharacterVariant = variant
        # We are going to try to find an image using any of the styles
        styles = variant.images.keys()
        sorted_styles = sorted(styles, key=lambda x: x.lower())
        for style in sorted_styles:
            filepath = variant.images.get(style, None)
            if os.path.exists(filepath):
                    return filepath
        logger.warning(f"No image found for character model {variant.character_id}({variant.name}).")
        return None

    # -------------------------------------------------------------------------
    # StyledImage Crud Operations
    # -------------------------------------------------------------------------
    
    def create_styled_image(self, styled_image_data):
        raise NotImplemented("Not yet implemented")

    
    def find_styled_image(self, series_id: str, character_id: str, variant_id: str, style_id: str, name: str) -> Optional[StyledImage]:
        filepath = name

        if not os.path.exists(filepath):
            logger.warning(f"Styled image {name} for character {character_id} in series {series_id} with variant {variant_id} and style {style_id} not found.")
            return None
        
        if not os.path.isfile(filepath):
            logger.error(f"Path {filepath} is not a file.")
            raise NotADirectoryError(f"Path {filepath} is not a file.")
        

        return filepath

    def find_styled_images(self, series_id: str, character_id: str, variant_id: str, style_id: str) -> list[StyledImage]:
        path = _character_variant_styled_image_path(
            series_id=series_id,
            character_id=character_id,
            variant_id=variant_id,
            style_id=style_id
        )
        if not os.path.exists(path):
            return []
        
        basenames = os.listdir(path)
        styled_images = []
        for basename in basenames:
            if basename.startswith(".") or os.path.isdir(os.path.join(path, basename)):
                logger.debug(f"Skipping hidden or directory item: {basename}")
                continue
            ext = os.path.splitext(basename)[1]
            if ext.lower() not in ['.jpg', '.jpeg', '.png']:
                logger.debug(f"Skipping non-image file: {basename}")
                continue
            styled_images.append(StyledImage(
                style_id=style_id,
                series_id=series_id,
                character_id=character_id,
                variant_id=variant_id,
                image_id=os.path.join(path, basename),)
            )
        return styled_images
        
    def update_styled_image(self, styled_image_id, styled_image_data):
        raise NotImplemented("Not yet implemented")
    
    def delete_styled_image(self, styled_image_id):
        raise NotImplemented("Not yet implemented")


    # -------------------------------------------------------------------------
    # Scene CRUD Operations
    # -------------------------------------------------------------------------
    def create_scene(self, scene_data):
        raise NotImplemented("Not yet implemented")
   
    def update_scene(self, data: SceneModel) -> None:
        return self.update_object(data=data)

    
    def delete_scene(self, scene_id):
        raise NotImplemented("Not yet implemented")

    
    def read_scene_style(self, scene_id):
        """
        Read the style of a scene.
        """
        raise NotImplemented("Not yet implemented")

    def find_scene_image(self, scene_id: str, issue_id: str, series_id: str) -> Optional[str]:
        """
        Find the image of a scene.
        """
        panels = self.read_all_objects(cls=Panel, primary_key={"scene_id": scene_id, "issue_id": issue_id, "series_id": series_id})
        if not panels:
            logger.warning(f"No panels found for scene {scene_id} in issue {issue_id} of series {series_id}.")
            return None
        
        # Sort the panels by their order
        for panel in panels:
            if panel.image is None:
                logger.warning(f"Panel {panel.id} in scene {scene_id} has no image.")
                continue
            filepath = self._panel_image_filepath(
                series_id=series_id,
                issue_id=issue_id,
                scene_id=scene_id,
                panel_id=panel.id,
                image_name=panel.image
            )
            if os.path.exists(filepath):
                return filepath
            
        return None
            

    # -------------------------------------------------------------------------
    # Panel CRUD Operations
    # -------------------------------------------------------------------------

    def create_panel(self, panel_data):
        raise NotImplemented("Not yet implemented")

    
    
    def update_panel(self, data: Panel) -> None:
        return self.update_object(data=data)

    
    def delete_panel(self, panel_id):
        raise NotImplemented("Not yet implemented")
    
    def find_panel_images(self, series_id, issue_id, scene_id, panel_id):
        panel_path = _panel_path(
            series_id=series_id,
            issue_id=issue_id,
            scene_id=scene_id,
            panel_id=panel_id
        )
        images_path = os.path.join(panel_path, 'images')

        if not os.path.exists(panel_path):
            logger.warning(f"Panel path {panel_path} does not exist.")
            return []
        images = []
        if not os.path.exists(images_path):
            os.makedirs(images_path)
        for img in os.listdir(images_path):
            if img.startswith("."):
                logger.debug(f"Skipping hidden image: {img}")
                continue
            
            img_filepath = os.path.join(panel_path, img)
            if not os.path.isfile(img_filepath):
                logger.debug(f"Skipping non-file item: {img}")
                continue
            
            images.append(img_filepath)
        return images

    def find_panel_reference_images(self, series_id, issue_id, scene_id, panel_id):
        """
        Find all reference images used for a panel.
        """
        panel = self.read_object(
            cls=Panel,
            primary_key={
                "series_id": series_id,
                "issue_id": issue_id,
                "scene_id": scene_id,
                "panel_id": panel_id
            }
        )
        if panel is None:
            logger.warning(f"Panel {panel_id} in scene {scene_id} of issue {issue_id} in series {series_id} not found.")
            return []

        panel: Panel = panel
        return panel.reference_images

    # -------------------------------------------------------------------------
    # PanelCharacter CRUD Operations
    # -------------------------------------------------------------------------

    
    def read_panel_character(self, panel_id):
        """
        Read the character featured in a panel.
        """
        raise NotImplemented("Not yet implemented")

    
    def read_panel_characters(self, panel_id):
        """
        Read all characters featured in a panel.
        """
        raise NotImplemented("Not yet implemented")

    
    def update_panel_character(self, panel_id, character_data):
        """
        Update the character featured in a panel.
        """
        raise NotImplemented("Not yet implemented")

    
    def delete_panel_character(self, panel_id):
        """
        Delete the character featured in a panel.
        """
        raise NotImplemented("Not yet implemented")

    # -------------------------------------------------------------------------
    # Panel Reference images CRUD Operations
    # -------------------------------------------------------------------------
    
    def create_panel_reference_image(self, panel_id, reference_image_data):
        """
        Create a reference image for a panel.
        """
        raise NotImplemented("Not yet implemented")

    
    def read_panel_reference_image(self, panel_id, reference_image_id):
        """
        Read a reference image for a panel.
        """
        raise NotImplemented("Not yet implemented")
        
    
    def read_panel_reference_images(self, panel_id):
        """
        Read all reference images for a panel.
        """
        raise NotImplemented("Not yet implemented")

    
    def update_panel_reference_image(self, panel_id, reference_image_id, reference_image_data):
        """
        Update a reference image for a panel.
        """
        raise NotImplemented("Not yet implemented")

    
    def delete_panel_reference_image(self, panel_id, reference_image_id):
        """
        Delete a reference image for a panel.
        """
        raise NotImplemented("Not yet implemented")

    # -------------------------------------------------------------------------
    # Style CRUD Operations
    # -------------------------------------------------------------------------
    def create_style(self, data):
        return self.create_object(data=data)
               
    def read_all_styles(self):
        """
        Read all styles.
        """
        return self.read_all_objects(cls=ComicStyle)
    
    def update_style(self, data):
        """
        Update a style.
        """
        self.update_object(data = data)

    
    def delete_style(self, id):
        """
        Delete a style.
        """
        self.delete_object(
            cls=ComicStyle,
            primary_key={"style_id": id},
        )
        
    def find_style_image(self, style_id: str) -> Optional[str]:
        """
        Find the image of a style.
        """
        style = self.read_object(cls=ComicStyle, primary_key={"style_id": style_id})
        if style is None:
            logger.warning(f"Style {style_id} not found.")
            return None
        # Check if the style has an image
        if style.image is None:
            logger.warning(f"Style {style_id} has no image.")
            return None
        
        # Get the image file path
        return style.image['art']
    
    def find_style_images(self, style_id: str, example_type: str='art') -> list[str]:
        """
        Find all images of a style.
        """
        images = []
        images_path = _style_image_path(style_id=style_id, example_type=example_type)
        if not os.path.exists(images_path):
            logger.warning(f"Style image path {images_path} does not exist.")
            return images
        for img in os.listdir(images_path):
            if img.startswith("."):
                logger.debug(f"Skipping hidden image: {img}")
                continue
            
            img_filepath = os.path.join(images_path, img)
            if not os.path.isfile(img_filepath):
                logger.debug(f"Skipping non-file item: {img}")
                continue
            
            images.append(img_filepath)
        return images
        



    # -------------------------------------------------------------------------
    # Style Example Image
    # -------------------------------------------------------------------------

    
    def create_style_example_image(self, style_id, art_image_data):
        """
        Create a new art image for a style.
        """
        raise NotImplemented("Not yet implemented")

    
    def create_style_example_image(self, style_id, art_image_id):
        """
        Read an art image for a style.
        """
        raise NotImplemented("Not yet implemented")

    
    def create_style_example_image(self, style_id):
        """
        Read all art images for a style.
        """
        raise NotImplemented("Not yet implemented")

    
    def create_style_example_image(self, style_id, art_image_id, art_image_data):
        """
        Update an art image for a style.
        """
        raise NotImplemented("Not yet implemented")

    
    def create_style_example_image(self, style_id, art_image_id):
        """
        Delete an art image for a style.
        """
        raise NotImplemented("Not yet implemented")


    # -------------------------------------------------------------------------
    # Publisher CRUD Operations
    # -------------------------------------------------------------------------
    def create_publisher(self, data: Publisher):
        return self.create_object(data=data)


    
    def read_all_publishers(self):
        """
        Read all publishers.
        """
        return self.read_all_objects(
            cls=Publisher
        )

    
    def update_publisher(self, data:Publisher):
        """
        Update a publisher.
        """
        self.update_object(
            data=data
        )
    
    def delete_publisher(self, publisher_id):
        """
        Delete a publisher.
        """
        return self.delete_object(
            cls=Publisher,
            primary_key={"publisher_id": publisher_id}
        )

    def find_publisher_image(self, publisher_id: str) -> Optional[str]:
        """
        Find the image of a publisher.
        """
        publisher = self.read_object(cls=Publisher, primary_key={"publisher_id": publisher_id})
        if publisher is None:
            logger.warning(f"Publisher {publisher_id} not found.")
            return None
        # Check if the publisher has an image
        if publisher.image is None:
            logger.warning(f"Publisher {publisher_id} has no image.")
            return None
        
        # Get the image file path
        return publisher.image
    
    def find_publisher_images(self, publisher_id: str) -> list[str]:
        """
        Find all images of a publisher.
        """
        publisher_path = _publisher_path(id=publisher_id)
        images_path = os.path.join(publisher_path, 'images')
        images = []
        if not os.path.exists(images_path):
            logger.warning(f"Publisher image path {images_path} does not exist.")
            return images
        for img in os.listdir(images_path):
            if img.startswith("."):
                logger.debug(f"Skipping hidden image: {img}")
                continue
            
            img_filepath = os.path.join(images_path, img)
            if not os.path.isfile(img_filepath):
                logger.debug(f"Skipping non-file item: {img}")
                continue
            
            images.append(img_filepath)
        return images
        
    def upload_publisher_image(self, publisher_id, image_name, image_data, mime_type):
        """
        Upload an image for a publisher.
        """
        if not mime_type.startswith("image/"):
            raise ValueError("Uploaded file is not an image")
        
        publisher_path = _publisher_path(id=publisher_id)
        images_path = os.path.join(publisher_path, 'images')
        if not os.path.exists(images_path):
            os.makedirs(images_path, exist_ok=True)
        
        filepath = os.path.join(images_path, image_name)
        with open(filepath, 'wb') as f:
            f.write(image_data.read())
        
        logger.info(f"Uploaded publisher image to {filepath}")
        return filepath 

    # -------------------------------------------------------------------------
    # Publisher Reference Images CRUD Operations
    # -------------------------------------------------------------------------
    
    def create_publisher_reference_image(self, publisher_id, reference_image_data):
        """
        Create a reference image for a publisher.
        """
        raise NotImplemented("Not yet implemented")

    
    def read_publisher_reference_image(self, publisher_id, reference_image_id):
        """
        Read a reference image for a publisher.
        """
        raise NotImplemented("Not yet implemented")

    
    def read_publisher_reference_images(self, publisher_id):
        """
        Read all reference images for a publisher.
        """
        raise NotImplemented("Not yet implemented")

    
    def update_publisher_reference_image(self, publisher_id, reference_image_id, reference_image_data):
        """
        Update a reference image for a publisher.
        """
        raise NotImplemented("Not yet implemented")

    
    def delete_publisher_reference_image(self, publisher_id, reference_image_id):
        """
        Delete a reference image for a publisher.
        """
        raise NotImplemented("Not yet implemented")

    # -------------------------------------------------------------------------
    # Upload Images
    # -------------------------------------------------------------------------

    def upload_cover_reference_image(self, series_id: str, issue_id: str, location: CoverLocation, name: str, data: BinaryIO, mime_type: str) -> str:
        path = os.path.join(_cover_path(issue_id=issue_id, series_id=series_id, location=location), 'uploads')
        if not os.path.exists(path):
            os.makedirs(path)
        filepath = os.path.join(path, name)
        with open(filepath, 'wb') as f:
            f.write(data.read())
        logger.info(f"Uploaded cover reference image to {filepath}")
        return filepath
    
    def upload_cover_image(self, series_id: str, issue_id: str, scene_id: str, panel_id: str, name: str, data: BinaryIO, mime_type: str) -> str:
        if not mime_type.startswith("image/"):
            raise ValueError("Uploaded file is not an image")
        path = os.path.join(_panel_path(series_id=series_id, issue_id=issue_id, scene_id=scene_id, panel_id=panel_id), 'images')
        if not os.path.exists(path):
            os.makedirs(path)
        filepath = os.path.join(path, name)
        with open(filepath, 'wb') as f:
            f.write(data.read())
        logger.info(f"Uploaded panel reference image to {filepath}")
        return filepath

    def upload_style_image(self, style_id: str, example_type: str, name: str, data: BinaryIO, mime_type: str) -> str:
        if not mime_type.startswith("image/"):
            raise ValueError("Uploaded file is not an image")
        path = _style_image_path(style_id=style_id, example_type=example_type)
        if not os.path.exists(path):
            os.makedirs(path)
        filepath = os.path.join(path, name)
        with open(filepath, 'wb') as f:
            f.write(data.read())
        logger.info(f"Uploaded style image to {filepath}")
        return filepath

    def upload_scene_reference_image(self, series_id, issue_id, scene_id, name, data, mime_type):
        if not mime_type.startswith("image/"):
            raise ValueError("Uploaded file is not an image")
        scene_path = _scene_path(
            series_id=series_id,
            issue_id=issue_id,
            scene_id=scene_id
        )
        upload_path = os.path.join(scene_path, 'uploads')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
        filepath = os.path.join(upload_path, name)
        with open(filepath, 'wb') as f:
            f.write(data.read())
        logger.info(f"Uploaded scene reference image to {filepath}")
        return filepath
    
    def upload_panel_reference_image(self, series_id:str, issue_id:str, scene_id:str, panel_id:str, name:str, data:BinaryIO, mime_type:str):
        if not mime_type.startswith("image/"):
            raise ValueError("Uploaded file is not an image")
        panel_path = _panel_path(
            series_id=series_id,
            issue_id=issue_id,
            scene_id=scene_id,
            panel_id=panel_id
        )
        upload_path = os.path.join(panel_path, 'uploads')
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
        filepath = os.path.join(upload_path, name)
        with open(filepath, 'wb') as f:
            f.write(data.read())
        logger.info(f"Uploaded panel reference image to {filepath}")
        return filepath
    
    def upload_styled_variant_image(self, series_id: str, character_id: str, variant_id: str, style_id: str, name: str, data: BinaryIO, mime_type: str) -> str:
        if not mime_type.startswith("image/"):
            raise ValueError("Uploaded file is not an image")
        path = _character_variant_styled_image_path(
            series_id=series_id,
            character_id=character_id,
            variant_id=variant_id,
            style_id=style_id
        )
        if not os.path.exists(path):
            os.makedirs(path)
        filepath = os.path.join(path, name)
        with open(filepath, 'wb') as f:
            f.write(data.read())
        logger.info(f"Uploaded styled variant image to {filepath}")
        return filepath
    



def _cover_path(series_id: str, issue_id: str, location: CoverLocation) -> str:
    """
    Get the path to the cover folder.
    """
    return PATH_TEMPLATES[(Cover.__name__)].format(
        series_id=series_id,
        issue_id=issue_id,
        location=location.value,
        base_path=BASE_PATH
    )

def _cover_image_path(issue_id: str, series_id: str,  location: CoverLocation) -> str:
    """
    Get the path to the cover image.
    """
    return os.path.join(_cover_path(series_id=series_id, issue_id=issue_id, location=location), "images")

def _character_variant_path(series_id: str, character_id: str, variant_id: str) -> str:
    """
    Get the path to the character variant folder.
    """
    return PATH_TEMPLATES[(CharacterVariant.__name__)].format(
        series_id=series_id,
        character_id=character_id,
        variant_id=variant_id,
        base_path=BASE_PATH
    )

def _character_variant_styled_image_path(series_id: str, character_id: str, variant_id: str, style_id: str) -> str:
    """
    Get the path to the character variant styled image folder.
    """
    return os.path.join(_character_variant_path(series_id=series_id, character_id=character_id, variant_id=variant_id), 'images', style_id)


def _scene_path(series_id: str, issue_id: str, scene_id: str) -> str:
    """
    Get the path to the scene folder.
    """
    return PATH_TEMPLATES[(SceneModel.__name__)].format(
        series_id=series_id,
        issue_id=issue_id,
        scene_id=scene_id,
        base_path=BASE_PATH
    )


def _panel_path(series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str:
    """
    Get the path to the panel folder.
    """
    return PATH_TEMPLATES[(Panel.__name__)].format(
        series_id=series_id,
        issue_id=issue_id,
        scene_id=scene_id,
        panel_id=panel_id,
        base_path=BASE_PATH
    )


def _style_path(style_id: str) -> str:
    """
    Get the path to the style folder.
    """
    return PATH_TEMPLATES[ComicStyle.__name__].format(
        style_id=style_id,
        base_path=BASE_PATH
    )

def _style_image_path(style_id: str, example_type: str) -> str:
    """
    Get the path to the style image folder.
    """
    return os.path.join(_style_path(style_id), 'images', example_type+'-style')

def _publisher_path(id: str) -> str:
    """
    Get the path to the publisher folder.
    """
    return PATH_TEMPLATES[(Publisher.__name__)].format(
        publisher_id=id,
        base_path=BASE_PATH 
    )


