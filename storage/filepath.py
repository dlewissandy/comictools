import os
from typing import Optional
from uuid import uuid4
from loguru import logger
from pydantic import BaseModel
from gui.selection import SelectedKind
from schema import *

TOPOSORT_ORDER = [
    "publisher_id",
    "series_id",
    "issue_id",
    "cover_id",
    "character_id",
    "variant_id",
    "scene_id",
    "panel_id",
    "style_id",
    "example_id",
    "image_id",
    "relation",
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
PATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.COVER.value], "{cover_id}")
ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.ISSUE.value], "scenes")
PATH_TEMPLATES[SelectedKind.SCENE.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value], "{scene_id}")
ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SCENE.value], "panels")
PATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value], "{panel_id}")
ROOT_PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.STYLE.value], "images")
PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value], "{example_id}")

ROOT_PATH_TEMPLATES[ComicStyle.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.STYLE.value]
ROOT_PATH_TEMPLATES[Series.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.SERIES.value]
ROOT_PATH_TEMPLATES[Publisher.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
ROOT_PATH_TEMPLATES[CharacterModel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.CHARACTER.value]
ROOT_PATH_TEMPLATES[CharacterVariant.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.VARIANT.value]
ROOT_PATH_TEMPLATES[Issue.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.ISSUE.value]
ROOT_PATH_TEMPLATES[Cover.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.COVER.value]
ROOT_PATH_TEMPLATES[SceneModel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value]
ROOT_PATH_TEMPLATES[Panel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value]
ROOT_PATH_TEMPLATES[StyleExample.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value]
PATH_TEMPLATES[ComicStyle.__name__] = PATH_TEMPLATES[SelectedKind.STYLE.value]
PATH_TEMPLATES[Series.__name__] = PATH_TEMPLATES[SelectedKind.SERIES.value]
PATH_TEMPLATES[Publisher.__name__] = PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
PATH_TEMPLATES[CharacterModel.__name__] = PATH_TEMPLATES[SelectedKind.CHARACTER.value]
PATH_TEMPLATES[CharacterVariant.__name__] = PATH_TEMPLATES[SelectedKind.VARIANT.value]
PATH_TEMPLATES[Issue.__name__] = PATH_TEMPLATES[SelectedKind.ISSUE.value]
PATH_TEMPLATES[Cover.__name__] = PATH_TEMPLATES[SelectedKind.COVER.value]
PATH_TEMPLATES[SceneModel.__name__] = PATH_TEMPLATES[SelectedKind.SCENE.value]
PATH_TEMPLATES[Panel.__name__] = PATH_TEMPLATES[SelectedKind.PANEL.value]
PATH_TEMPLATES[StyledVariant.__name__] = os.path.join(BASE_PATH, "styled_images", "{image_id}")
PATH_TEMPLATES[StyleExample.__name__] = PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value]
PATH_TEMPLATES[StyledVariant.__name__] = os.path.join(PATH_TEMPLATES[SelectedKind.VARIANT.value], "images", "{style_id}")
PATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value] = PATH_TEMPLATES[StyledVariant.__name__]

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
FILEPATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value] = os.path.join(PATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value], "styled_variant.json")
FILEPATH_TEMPLATES[Publisher.__name__] = FILEPATH_TEMPLATES[SelectedKind.PUBLISHER.value]
FILEPATH_TEMPLATES[Series.__name__] = FILEPATH_TEMPLATES[SelectedKind.SERIES.value]
FILEPATH_TEMPLATES[ComicStyle.__name__] = FILEPATH_TEMPLATES[SelectedKind.STYLE.value]
FILEPATH_TEMPLATES[CharacterModel.__name__] = FILEPATH_TEMPLATES[SelectedKind.CHARACTER.value]
FILEPATH_TEMPLATES[CharacterVariant.__name__] = FILEPATH_TEMPLATES[SelectedKind.VARIANT.value]
FILEPATH_TEMPLATES[Issue.__name__] = FILEPATH_TEMPLATES[SelectedKind.ISSUE.value]
FILEPATH_TEMPLATES[Cover.__name__] = FILEPATH_TEMPLATES[SelectedKind.COVER.value]
FILEPATH_TEMPLATES[SceneModel.__name__] = FILEPATH_TEMPLATES[SelectedKind.SCENE.value]
FILEPATH_TEMPLATES[Panel.__name__] = FILEPATH_TEMPLATES[SelectedKind.PANEL.value]
FILEPATH_TEMPLATES[StyledVariant.__name__] = os.path.join(PATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value], "styled_variant.json")

IMAGE_PATH_TEMPLATES = {}
IMAGE_PATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(PATH_TEMPLATES[SelectedKind.PANEL.value], "images")
IMAGE_PATH_TEMPLATES[Panel.__name__] = IMAGE_PATH_TEMPLATES[SelectedKind.PANEL.value]
IMAGE_PATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.COVER.value], "images")
IMAGE_PATH_TEMPLATES[Cover.__name__] = IMAGE_PATH_TEMPLATES[SelectedKind.COVER.value]
IMAGE_PATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value] = os.path.join(PATH_TEMPLATES[SelectedKind.VARIANT.value], "images", "{style_id}")
IMAGE_PATH_TEMPLATES[StyledVariant.__name__] = IMAGE_PATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value]
IMAGE_PATH_TEMPLATES[SelectedKind.PUBLISHER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.PUBLISHER.value], "images")
IMAGE_PATH_TEMPLATES[Publisher.__name__] = IMAGE_PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
IMAGE_PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE] = os.path.join(PATH_TEMPLATES[SelectedKind.STYLE], "images", "{example_id}")
IMAGE_PATH_TEMPLATES[StyleExample.__name__] = PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value]

UPLOAD_PATH_TEMPLATES = {}
UPLOAD_PATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(PATH_TEMPLATES[SelectedKind.PANEL.value], "uploads")
UPLOAD_PATH_TEMPLATES[Panel.__name__] = UPLOAD_PATH_TEMPLATES[SelectedKind.PANEL.value]
UPLOAD_PATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.COVER.value], "uploads")
UPLOAD_PATH_TEMPLATES[Cover.__name__] = UPLOAD_PATH_TEMPLATES[SelectedKind.COVER.value]
UPLOAD_PATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value] = IMAGE_PATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value]
UPLOAD_PATH_TEMPLATES[StyledVariant.__name__] = IMAGE_PATH_TEMPLATES[SelectedKind.STYLED_VARIANT.value]
UPLOAD_PATH_TEMPLATES[SelectedKind.PUBLISHER.value] = IMAGE_PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
UPLOAD_PATH_TEMPLATES[Publisher.__name__] = IMAGE_PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
UPLOAD_PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value] = IMAGE_PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value]
UPLOAD_PATH_TEMPLATES[StyleExample.__name__] = IMAGE_PATH_TEMPLATES[SelectedKind.STYLE_EXAMPLE.value]
UPLOAD_PATH_TEMPLATES[SceneModel.__name__] = os.path.join(PATH_TEMPLATES[SelectedKind.SCENE.value], "uploads")


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
    
    # Sync the directory
    dir_fd = os.open(path, os.O_DIRECTORY)
    os.fsync(dir_fd)  # ensure directory entry is committed
    os.close(dir_fd)
    
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
    
def obj_to_path(obj: BaseModel, base_path: str = BASE_PATH) -> str:
    """
    Get the path to a particular object.
    This is the path to the folder that contains the object.
    """
    clsname = obj.__class__.__name__
    template = PATH_TEMPLATES.get(clsname, None)
    return template_to_filepath(template=template, pk=obj.primary_key, base_path=base_path)

def obj_to_imagepath(obj: BaseModel, base_path: str = BASE_PATH) -> str:
    """
    Get the image path for a particular object.
    This is the path to the folder that contains the object.
    """
    clsname = obj.__class__.__name__
    template = IMAGE_PATH_TEMPLATES.get(clsname, None)
    return template_to_filepath(template=template, pk=obj.primary_key, base_path=base_path)

def obj_to_reference_path(obj: BaseModel, base_path: str = BASE_PATH) -> str:
    """
    Get the reference path for a particular object.
    This is the path to the folder that contains the object.
    """
    clsname = obj.__class__.__name__
    template = UPLOAD_PATH_TEMPLATES.get(clsname, None)
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

def get_object_id_field_name(item: BaseModel) -> str:
    """
    Get the identifier field for a given item.
    """
    # Get the compound keys for the item
    pk = item.primary_key
    fk = item.parent_key

    pk_fields = set(pk.keys())
    fk_fields = set(fk.keys())

    # The identifier field is the one that is in the primary key, but not the foreign key.
    identifier_fields = pk_fields - fk_fields
    if identifier_fields:
        return identifier_fields.pop()
    raise ValueError("No identifier field found.")

IMAGE_FILE_EXTENSIONS = [
    "png",
    "jpg",
    "jpeg",
    "gif",
    "bmp",
    "tiff",
    "webp",
    "svg",
    "heic",
    "avif",
]