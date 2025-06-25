from typing import Optional
import os
from uuid import uuid4

from helpers.constants import IMAGE_EXTENSIONS, STYLES_FOLDER

def normalize_id(text: str) -> str:
    """
    Normalize a string to be used as an ID.
    
    This function converts the string to lowercase, replaces spaces with hyphens,
    and removes any non-alphanumeric characters except for hyphens.
    
    Args:
        text (str): The string to normalize.
        
    Returns:
        str: The normalized string.
    """
    return ''.join(c if c.isalnum() or c == '-' else '' for c in text.lower().replace(' ', '-'))    

def subfolders(path: str) -> list[str]:
  """Lists all subfolders within a given folder path.

  Args:
    folder_path: The path to the folder to list subfolders from.

  Returns:
    A list of strings, where each string is the name of a subfolder.
    Returns an empty list if the folder does not exist or has no subfolders.
  """
  subfolders = []
  if os.path.exists(path) and os.path.isdir(path):
    for item in os.listdir(path):
      # skip hidden folders
      if item.startswith("."):
        continue
      item_path = os.path.join(path, item)
      if os.path.isdir(item_path):
        subfolders.append(item)
  return subfolders

def get_folder_contents(path: str) -> list[str]:
    """
    Get all files and folders in a folder.
    """
    contents = []
    if os.path.exists(path) and os.path.isdir(path):
        for item in os.listdir(path):
        # skip hidden folders
            if item.startswith("."):
                continue
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                contents.append(item)
            else:
                # strip the file extension
                item = os.path.splitext(item)[0]
                contents.append(item)
    return contents

def generate_unique_id(path: str, create_folder: bool = True, name:Optional[str] = None) -> str:
    """
    Generate a unique ID.  This will be used as a folder for generated image assets.

    Args:
        path (str): The path to the folder where the unique ID will be created.
        create_folder (bool): Whether to create the folder if it does not exist. Defaults to True.
        name (str): an optional name for the folder.   If not provided, or if the 
            name is not unique, a UUID4 will be used.  The name will be converted to lowercase
            snake-case. 
    """
    # verify that the path exists
    if not os.path.exists(path):
        os.makedirs(path)
    # verify that the path is a directory
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path {path} is not a directory.")
    # get the names of all the folders rooted at the path, excluding hidden folders

    contents = get_folder_contents(path)
    result = str(uuid4()) 
    if name is not None:
        result = name.replace(" ", "-").lower()
    while result in contents:
        result = str(uuid4())
    # create the folder
    if create_folder:
        os.makedirs(os.path.join(path, result))
    return result

def get_image_files(path: str) -> list[str]:
    """
    Get all image files in a folder.
    """
    image_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            # check if the file is an image
            if ext in IMAGE_EXTENSIONS:
                image_files.append(file)
    return image_files

def is_uuid4(text:str) -> bool:
    """
    Check if a string is a valid UUID4.
    """

    import uuid
    try:
        uuid_obj = uuid.UUID(text, version=4)
    except ValueError:
        return False
    return str(uuid_obj) == text and uuid_obj.version == 4

