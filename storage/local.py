import os
import json
import shutil
from loguru import logger
from typing import Optional, BinaryIO
from pydantic import BaseModel
from uuid import uuid4
from storage.generic import GenericStorage
from logging import Logger
from schema import *

class LocalStorage(GenericStorage):

    def __init__(self, base_path: str, logger: Logger):
        super().__init__()
        self._logger = logger
        self.base_path = base_path
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

    def _get_basenames(self, path: str, exts: list[str] = None) -> list[str]:
        """
        Get all files and folders in a folder, excluding hidden folders.
        """
        self._logger.trace(f"Getting basenames from path: {path}")
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
                self._logger.debug(f"Skipping hidden item: {item}")
                continue
            if exts is not None and not any(item.endswith(ext) for ext in exts):
                self._logger.debug(f"Skipping item {item} with unsupported extension.")
                continue
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                contents.append(item)
            else:
                # strip the file extension
                item = os.path.splitext(item)[0]
                contents.append(item)
        self._logger.debug(f"Found {len(contents)} items in {path}")
        return contents

    def _generate_unique_id(self, path: str, create_folder: bool = True) -> str:
        """
        Generate a unique ID.  This will be used as a folder for generated image assets.

        Args:
            path (str): The path to the folder where the unique ID will be created.
            create_folder (bool): Whether to create the folder if it does not exist. Defaults to True.
            name (str): an optional name for the folder.   If not provided, or if the 
                name is not unique, a UUID4 will be used.  The name will be converted to lowercase
                snake-case. 
        """
        self._logger.trace(f"Generating unique ID in path")
        # verify that the path is a directory
        if not os.path.isdir(path):
            self._logger.error(f"Path {path} is not a directory.")
            raise NotADirectoryError(f"Path {path} is not a directory.")

        # verify that the path exists
        if not os.path.exists(path):
            os.makedirs(path)

        # get the names of all the folders rooted at the path, excluding hidden folders
            
        contents = self._get_basenames(path)
        result = str(uuid4()) 
        while result in contents:
            result = str(uuid4())
        # create the folder
        if create_folder:
            os.makedirs(os.path.join(path, result))
        return result

    def _create_object(self, path: str, data: BaseModel, create_folder: bool = True, filename: str=None) -> str:
        """
        Create a new object in the specified path with the given data.
        """
        self._logger.trace(f"creating {data.__class__.__name__} with data: {data.model_dump()}")
        if not os.path.exists(path):
            os.makedirs(path)
        
        if not os.path.isdir(path):
            raise NotADirectoryError(f"Path {path} is not a directory.")
        
        # Generate a unique ID for the object
        object_id = self._generate_unique_id(path=path, create_folder=create_folder)
        data.id = object_id
        
        # Write the data to a file
        if filename:
            filepath = os.path.join(path, object_id, filename)
        else:
            filepath = os.path.join(path, f"{object_id}.json")
            
        with open(filepath, 'w') as f:
            f.write(data.model_dump_json(indent=2))
        return object_id

    def _read_object(self, filepath: str, cls: BaseModel) -> Optional[BaseModel]:
        """
        Read an object from a file and return it as an instance of the specified class.
        """
        if not os.path.exists(filepath):
            self._logger.warning(f"File {filepath} does not exist. Returning None.")
            return None
        
        if not os.path.isfile(filepath):
            self._logger.error(f"Path {filepath} is not a file.")
            raise FileNotFoundError(f"Path {filepath} is not a file.")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        try: 
            return cls.model_validate(data)
        except Exception as e:
            msg = f"Failed to validate: {e}"
            self._logger.error(msg)
            raise
            
    def _read_all_objects(self, path: str, cls: BaseModel, filename: Optional[str] = None) -> list[BaseModel]:
        """
        Read all objects from a directory and return them as a list of instances of the specified class.
        
        Args:
            path (str): The path to the directory containing the objects.
            cls (BaseModel): The class to which the objects should be converted.
            filename: The name of the file that contains a single object.  If provided,
              then it is assumed that the path contains multiple folders, each containing
              a single file with the given filename.
        """
        self._logger.trace(f"Reading all {cls.__class__.__name__} objects from {path}")
        if not os.path.exists(path):
            self._logger.warning(f"Path {path} does not exist. Returning empty list.")
            return []
        
        if not os.path.isdir(path):
            msg = f"Path {path} is not a directory."
            self._logger.error(msg)
            raise NotADirectoryError(msg)
        
        
        objects = []
        # If a filename is provided, read each folder in the path
        if filename:
            # Get all the non-hidden folders in the path
            subfolders = self._get_basenames(path)
            for folder in subfolders:
                folder_path = os.path.join(path, folder)
                if not os.path.isdir(folder_path):
                    self._logger.warning(f"Path {folder_path} is not a directory. Skipping.")
                    continue
                filepath = os.path.join(folder_path, filename)
                obj = self._read_object(filepath, cls)
                if obj:
                    objects.append(obj)
        else:
            # Read all the json files in the directory
            for item in os.listdir(path):
                if item.startswith("."):
                    self._logger.debug(f"Skipping hidden item: {item}")
                    continue
                if not item.endswith('.json'):
                    self._logger.debug(f"Skipping non-json item: {item}")
                    continue
                if not os.path.isfile(os.path.join(path, item)):
                    self._logger.debug(f"Skipping non-file item: {item}")
                    continue
                filepath = os.path.join(path, item)
                obj = self._read_object(filepath, cls)
                if obj:                    
                    objects.append(obj)
        self._logger.debug(f"Read {len(objects)} objects from {path}")
        return objects
        

    def _update_object(self, filepath: str, data: BaseModel) -> None:
        """
        Update an existing object in the specified file with the given data.
        
        Args:
            filepath (str): The path to the file containing the object.
            data (BaseModel): The data to update the object with.
        """
        self._logger.trace(f"Updating {data.__class__.__name__} in {filepath} with data: {data.model_dump()}")
        if not os.path.exists(filepath):
            self._logger.error(f"File {filepath} does not exist. Cannot update.")
            raise FileNotFoundError(f"File {filepath} does not exist.")
        
        if not os.path.isfile(filepath):
            self._logger.error(f"Path {filepath} is not a file.")
            raise NotADirectoryError(f"Path {filepath} is not a file.")
        
        with open(filepath, 'w') as f:
            f.write(json.dumps(data.model_dump(), indent=2))

    def _delete_object(self, filepath: str, cls: BaseModel, delete_folder=True) -> Optional[BaseModel]:
        """
        Delete an object from a file.   If it existed, then return the object so
        that it could be used for further processing (e.g. logging, undoing, unlinking, etc).

        Args:
            filepath (str): The path to the file containing the object.
            delete_folder (bool): Whether to delete the folder containing the object. Defaults to True.
            cls (BaseModel): The class of the object to be deleted.
        """

        self._logger.trace(f"Deleting {cls.__class__.__name__} from {filepath}")
        instance = self._read_object(filepath, cls)
        if instance is None:
            self._logger.warning(f"File {filepath} does not exist. Cannot delete.")
            return None
        

        if delete_folder:
            # Remove the entire folder containing the file
            shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)
        else:
            # Just remove the file
            os.remove(filepath)

        return instance



    # -------------------------------------------------------------------------
    # Series CRUD Operations
    # -------------------------------------------------------------------------
    _SERIES_FILENAME = 'series.json'
    _ALL_SERIES_FOLDER = 'series'

    def _all_series_path(self) -> str:
        return os.path.join(self.base_path, "series")
    
    def _series_path(self, series_id: str) -> str:
        """
        Get the path to the series folder.
        """
        return os.path.join(self._all_series_path(), series_id)
    
    def _series_filepath(self, series_id: str) -> str:
        return os.path.join(self._series_path(series_id), self._SERIES_FILENAME)

    def create_series(self, data: Series) -> str:
        return self._create_object(path=self._all_series_path(), data =data, create_folder=True, filename='series.json')

    def read_series(self, id: str) -> Optional[Series]:
        return self._read_object(filepath = self._series_filepath(id),cls = Series)

    def read_all_series(self) -> list[Series]:
        return self._read_all_objects(path=self._all_series_path(),cls=Series,filename=self._SERIES_FILENAME) 
    
    def update_series(self, data: Series) -> None:
        self._update_object(
            filepath=self._series_filepath(data.id),
            data=data
        )
    
    def delete_series(self, id: str) -> Optional[Series]:
        return self._delete_object(
            filepath=self._series_filepath(id),
            cls=Series,
        )
    
    def find_series(self, name: str) -> Optional[Series]:
        """
        Find a series by name.   The name is case-insensitive and can be a partial match.
        """
        all_series = self.read_all_series()
        for series in all_series:
            if series.name.lower() == name.lower():
                return series
        return None
    
    def find_series_image(self, series_id: str) -> Optional[str]:
        issues: list[Issue] = self.find_issues(series_id=series_id)
        # sort the issues by issue number
        issues.sort(key=lambda x: x.issue_number if x.issue_number is not None else float('inf'))
        for issue in issues:
            issue_covers = self.find_covers(series_id=series_id, issue_id=issue.id)
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
    def _all_issues_path(self, series_id: str) -> str:
        """
        Get the path to the all issues folder.
        """
        return os.path.join(self._series_path(series_id=series_id), 'issues')

    def _issue_path(self, series_id: str, issue_id: str) -> str:
        """
        Get the path to the issue folder.
        """
        return os.path.join(self._all_series_path(), series_id, 'issues', issue_id)
    
    def _issue_filepath(self, series_id: str, issue_id: str) -> str:
        """
        Get the path to the issue file.
        """
        return os.path.join(self._issue_path(series_id, issue_id), 'issue.json')


    def create_issue(self, data: Issue) -> str:
        return self._create_object(
            path=self._all_issues_path(),
            data=data,
            create_folder=True,
            filename='issue.json'
        )
    
    def find_issue(self, series_id: str, id: str) -> Optional[Issue]:
        return self._read_object(
            filepath=self._issue_filepath(series_id, id),
            cls=Issue
        )

    def find_issues(self, series_id: str) -> list[Issue]:
        return self._read_all_objects(
            path=self._all_issues_path(series_id),
            cls=Issue,
            filename='issue.json'
        )
    
    def update_issue(self,  data: Issue) -> None:
        return self._update_object(
            filepath=self._issue_filepath(series_id = data.series, issue_id = data.id),
            data=data
        )

    
    def delete_issue(self, series_id: str, id: str) -> Optional[Issue]:
        return self._delete_object(
            filepath=self._issue_filepath(series_id=series_id, id=id),
            cls=Issue,
            delete_folder=True
        )

    
    def find_issue_style(self, series_id: str, id: str) -> Optional[ComicStyle]:
        """
        Read the style of an issue.
        """
        issue = self.find_issue(series_id = series_id, id = id)
        if issue is None:
            self._logger.warning(f"Issue {id} in series {series_id} not found.")
            return None
        return self.read_style(id=issue.style_id)
        
    def find_issue_image(self, series_id: str, issue_id: str) -> Optional[str]:
        covers: list[TitleBoardModel] = self.find_covers(series_id=series_id, issue_id=issue_id)
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
    
    def _all_covers_path(self, series_id: str, issue_id: str) -> str:
        """
        Get the path to the all covers folder.
        """
        return os.path.join(self._issue_path(series_id=series_id, issue_id=issue_id), 'covers')
    
    def _cover_path(self, series_id: str, issue_id: str, location: CoverLocation) -> str:
        """
        Get the path to the cover folder.
        """
        return os.path.join(self._all_covers_path(series_id=series_id, issue_id=issue_id), location.value)
    
    def _cover_filepath(self, series_id: str, issue_id: str, location: CoverLocation) -> str:
        """
        Get the path to the cover file.
        """
        return os.path.join(self._cover_path(series_id=series_id, issue_id=issue_id, location=location),"cover.json")
    
    def _cover_image_path(self, issue_id: str, series_id: str,  location: CoverLocation) -> str:
        """
        Get the path to the cover image.
        """
        return os.path.join(self._cover_path(series_id=series_id, issue_id=issue_id, location=location), "images")
    
    def _cover_image_filepath(self, series_id: str, issue_id: str, location: CoverLocation, image_name: str) -> str:
        """
        Get the path to the cover image.
        """
        return os.path.join(self._cover_image_path(issue_id=issue_id, series_id=series_id, location=location), image_name)

    def create_cover(self, data):
        raise NotImplemented("Not yet implemented")

    
    def find_cover(self, series_id: str, issue_id: str, location: CoverLocation) -> Optional[TitleBoardModel]:
        return self._read_object(
            filepath=self._cover_filepath(series_id=series_id, issue_id=issue_id, location=location),
            cls=TitleBoardModel
        )

    
    def find_covers(self, series_id: str, issue_id: str) -> list[TitleBoardModel]:
        return self._read_all_objects(
            path=self._all_covers_path(series_id=series_id, issue_id=issue_id),
            cls=TitleBoardModel,
            filename='cover.json'
        )

    
    def update_cover(self, data: TitleBoardModel) -> None:
        self._update_object(
            filepath=self._cover_filepath(series_id=data.series, issue_id=data.issue, location=data.location),
            data=data
        )

    
    def delete_cover(self, series_id: str, issue_id: str, location: CoverLocation) -> Optional[TitleBoardModel]:
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
        cover = self.find_cover(series_id=series_id, issue_id=issue_id, location=location)
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
        cover = self.find_cover(series_id=series_id, issue_id=issue_id, location=location)
        if cover is None:
            logger.warning(f"Cover {location.value} for issue {issue_id} in series {series_id} not found.")
            return []
        if cover.image is None:
            logger.warning(f"Cover {location.value} for issue {issue_id} in series {series_id} has no image.")
            return []
        
        images_path = self._cover_image_path(issue_id=issue_id, series_id=series_id, location=location)
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
        cover = self.find_cover(series_id=series_id, issue_id=issue_id, location=location)
        if cover is None:
            logger.critical(f"Cover {location.value} for issue {issue_id} in series {series_id} not found.")
            return []
        
        cover: TitleBoardModel = cover
        return cover.reference_images


    # -------------------------------------------------------------------------
    # Character CRUD Operations
    # -------------------------------------------------------------------------
    
    def _all_characters_path(self, series_id: str) -> str:
        """
        Get the path to the all characters folder.
        """
        return os.path.join(self._series_path(series_id=series_id), 'characters')
    
    def _character_path(self, series_id: str, character_id: str) -> str:
        """
        Get the path to the character folder.
        """
        return os.path.join(self._all_characters_path(series_id=series_id), character_id)
    
    def _character_filepath(self, series_id: str, character_id: str) -> str:
        """
        Get the path to the character file.
        """
        return os.path.join(self._character_path(series_id=series_id, character_id=character_id), 'character.json')

    def create_character(self, character_data):
        raise NotImplemented("Not yet implemented")

    
    def find_character(self, series_id: str, character_id: str)-> Optional[CharacterModel]:
        return self._read_object(
            filepath=self._character_filepath(series_id=series_id, character_id=character_id),
            cls=CharacterModel
        )

    def find_characters(self, series_id: str) -> Optional[CharacterModel]:
        return self._read_all_objects(
            path=self._all_characters_path(series_id=series_id),
            cls=CharacterModel,
            filename='character.json'
        )

    
    def update_character(self, character_id, character_data):
        raise NotImplemented("Not yet implemented")

    
    def delete_character(self, character_id):
        raise NotImplemented("Not yet implemented")

    
    def find_character_variant(self, series_id: str, character_id: str, variant_id: str) -> Optional[CharacterVariant]:
        """
        Read all variants of a character.
        """
        logger.critical(self._character_variant_filepath(series_id=series_id, character_id=character_id, variant_id=variant_id))
        return self._read_object(
            filepath=self._character_variant_filepath(series_id=series_id, character_id=character_id, variant_id=variant_id),
            cls=CharacterVariant
        )
        

    
    def find_character_variants(self, series_id: str, character_id: str) -> list[CharacterVariant]:
        """
        Read all variants of a character.
        """
        return self._read_all_objects(
            path=self._all_character_variants_path(series_id=series_id, character_id=character_id),
            cls=CharacterVariant,
            filename='variant.json'
        )
    
    def find_character_image(self, series_id: str, character_id: str) -> Optional[str]:
        """
        Find the image of a character.
        """
        logger.trace("character.image_filepath() called")
        # Get the base variant
        variants = self.find_character_variants(series_id=series_id, character_id=character_id)
        while len(variants) > 0:
            variant = variants.pop(0)
            filepath = self.find_variant_image(series_id=series_id, character_id=character_id, variant_id=variant.id)
            if filepath is not None:
                return filepath
        # If no image is found, return None
        return None
    

    # -------------------------------------------------------------------------
    # CharacterVariant CRUD Operations
    # -------------------------------------------------------------------------
    
    def _all_character_variants_path(self, series_id: str, character_id: str) -> str:
        """
        Get the path to the all character variants folder.
        """
        return self._character_path(series_id=series_id, character_id=character_id)
    
    def _character_variant_path(self, series_id: str, character_id: str, variant_id: str) -> str:
        """
        Get the path to the character variant folder.
        """
        return os.path.join(self._all_character_variants_path(series_id=series_id, character_id=character_id), variant_id)  
    
    def _character_variant_filepath(self, series_id: str, character_id: str, variant_id: str) -> str:
        """
        Get the path to the character variant file.
        """
        return os.path.join(self._character_variant_path(series_id=series_id, character_id=character_id, variant_id=variant_id),  'variant.json')
    
    def _character_variant_styled_image_path(self, series_id: str, character_id: str, variant_id: str, style_id: str) -> str:
        """
        Get the path to the character variant styled image folder.
        """
        return os.path.join(self._character_variant_path(series_id=series_id, character_id=character_id, variant_id=variant_id), 'images', style_id)
    
    def _character_variant_styled_image_filepath(self, series_id: str, character_id: str, variant_id: str, style_id: str, image_name: str) -> str:
        """
        Get the path to the character variant styled image file.
        """
        return os.path.join(self._character_variant_styled_image_path(series_id=series_id, character_id=character_id, variant_id=variant_id, style_id=style_id), image_name)   

    def create_character_variant(self, variant_data):
        raise NotImplemented("Not yet implemented")

    
    def find_character_variant(self, series_id: str, character_id: str, variant_id: str) -> Optional[CharacterVariant]:
        return self._read_object(
            filepath=self._character_variant_filepath(series_id=series_id, character_id=character_id, variant_id=variant_id),
            cls=CharacterVariant
        )

    def find_character_variants(self, series_id: str, character_id: str) -> list[CharacterVariant]:
        return self._read_all_objects(
            path=self._all_character_variants_path(series_id=series_id, character_id=character_id),
            cls=CharacterVariant,
            filename='variant.json'
        )
    
    def update_character_variant(self, data: CharacterVariant):
        return self._update_object(
            filepath=self._character_variant_filepath(series_id=data.series, character_id=data.character, variant_id=data.id),
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
        variant = self.find_character_variant(series_id=series_id, character_id=character_id, variant_id=variant_id)
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
        logger.warning(f"No image found for character model {variant.character}({variant.name}).")
        return None

    # -------------------------------------------------------------------------
    # StyledImage Crud Operations
    # -------------------------------------------------------------------------
    
    def create_styled_image(self, styled_image_data):
        raise NotImplemented("Not yet implemented")

    
    def find_styled_image(self, series_id: str, character_id: str, variant_id: str, style_id: str, name: str) -> Optional[StyledImage]:
        filepath = name

        if not os.path.exists(filepath):
            self._logger.warning(f"Styled image {name} for character {character_id} in series {series_id} with variant {variant_id} and style {style_id} not found.")
            return None
        
        if not os.path.isfile(filepath):
            self._logger.error(f"Path {filepath} is not a file.")
            raise NotADirectoryError(f"Path {filepath} is not a file.")
        

        return filepath

    def find_styled_images(self, series_id: str, character_id: str, variant_id: str, style_id: str) -> list[StyledImage]:
        path = self._character_variant_styled_image_path(
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
                self._logger.debug(f"Skipping hidden or directory item: {basename}")
                continue
            ext = os.path.splitext(basename)[1]
            if ext.lower() not in ['.jpg', '.jpeg', '.png']:
                self._logger.debug(f"Skipping non-image file: {basename}")
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
    def _all_scenes_path(self, series_id: str, issue_id: str) -> str:
        return os.path.join(self._issue_path(series_id=series_id, issue_id=issue_id), 'scenes')
    
    def _scene_path(self, series_id: str, issue_id: str, scene_id: str) -> str:
        """
        Get the path to the scene folder.
        """
        return os.path.join(self._all_scenes_path(series_id=series_id, issue_id=issue_id), scene_id)    
    
    def _scene_filepath(self, series_id: str, issue_id: str, scene_id: str) -> str:
        """
        Get the path to the scene file.
        """
        return os.path.join(self._scene_path(series_id=series_id, issue_id=issue_id, scene_id=scene_id), 'scene.json')

    def create_scene(self, scene_data):
        raise NotImplemented("Not yet implemented")

    
    def find_scene(self, scene_id: str, issue_id: str, series_id: str) -> Optional[SceneModel]:
        """
        Find a scene by its ID.
        """
        return self._read_object(
            filepath=self._scene_filepath(scene_id=scene_id, issue_id=issue_id, series_id=series_id),
            cls=SceneModel
        )        

    def find_scenes(self, series_id: str, issue_id: str) -> list[SceneModel]:
        return self._read_all_objects(
            path=self._all_scenes_path(series_id=series_id, issue_id=issue_id),
            cls=SceneModel,
            filename='scene.json'
        )

    
    def update_scene(self, data: SceneModel) -> None:
        return self._update_object(
            filepath=self._scene_filepath(series_id=data.series, issue_id=data.issue, scene_id=data.id),
            data=data
        )

    
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
        panels = self.find_panels(scene_id=scene_id, issue_id=issue_id, series_id=series_id)
        if not panels:
            self._logger.warning(f"No panels found for scene {scene_id} in issue {issue_id} of series {series_id}.")
            return None
        
        # Sort the panels by their order
        for panel in panels:
            if panel.image is None:
                self._logger.warning(f"Panel {panel.id} in scene {scene_id} has no image.")
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
    
    def _all_panels_path(self, series_id: str, issue_id: str, scene_id: str) -> str:
        """
        Get the path to the all panels folder.
        """
        return os.path.join(self._scene_path(series_id=series_id, issue_id=issue_id, scene_id=scene_id), 'panels')
    
    def _panel_path(self, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str:
        """
        Get the path to the panel folder.
        """
        return os.path.join(self._all_panels_path(series_id=series_id, issue_id=issue_id, scene_id=scene_id), panel_id)

    def _panel_filepath(self, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> str:
        """
        Get the path to the panel file.
        """
        return os.path.join(self._panel_path(series_id=series_id, issue_id=issue_id, scene_id=scene_id, panel_id=panel_id), 'panel.json')

    def create_panel(self, panel_data):
        raise NotImplemented("Not yet implemented")

    
    def find_panel(self, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> Optional[Panel]:
        """
        Find a panel by its ID.
        """
        return self._read_object(
            filepath=self._panel_filepath(series_id=series_id, issue_id=issue_id, scene_id=scene_id, panel_id=panel_id),
            cls=Panel
        )

    def find_panels(self, series_id: str, issue_id: str, scene_id: str) -> list[Panel]:
        """
        Find all panels in a scene.
        """
        return self._read_all_objects(
            path=self._all_panels_path(series_id=series_id, issue_id=issue_id, scene_id=scene_id),
            cls=Panel,
            filename='panel.json'
        )

    
    def update_panel(self, data: Panel) -> None:
        return self._update_object(
            filepath=self._panel_filepath(series_id=data.series, issue_id=data.issue, scene_id=data.scene, panel_id=data.id),
            data=data
        )

    
    def delete_panel(self, panel_id):
        raise NotImplemented("Not yet implemented")
    
    def find_panel_images(self, series_id, issue_id, scene_id, panel_id):
        panel_path = self._panel_path(
            series_id=series_id,
            issue_id=issue_id,
            scene_id=scene_id,
            panel_id=panel_id
        )
        images_path = os.path.join(panel_path, 'images')

        if not os.path.exists(panel_path):
            self._logger.warning(f"Panel path {panel_path} does not exist.")
            return []
        images = []
        if not os.path.exists(images_path):
            os.makedirs(images_path, exist_ok=True)
        for img in os.listdir(images_path):
            if img.startswith("."):
                self._logger.debug(f"Skipping hidden image: {img}")
                continue
            
            img_filepath = os.path.join(panel_path, img)
            if not os.path.isfile(img_filepath):
                self._logger.debug(f"Skipping non-file item: {img}")
                continue
            
            images.append(img_filepath)
        return images

    def find_panel_reference_images(self, series_id, issue_id, scene_id, panel_id):
        """
        Find all reference images used for a panel.
        """
        panel = self.find_panel(
            series_id=series_id,
            issue_id=issue_id,
            scene_id=scene_id,
            panel_id=panel_id
        )
        if panel is None:
            self._logger.warning(f"Panel {panel_id} in scene {scene_id} of issue {issue_id} in series {series_id} not found.")
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

    _ALL_STYLES_FOLDER = 'styles'
    _STYLE_FILENAME = 'style.json'
    
    def _all_styles_path(self) -> str:
        return os.path.join(self.base_path, self._ALL_STYLES_FOLDER)
    
    def _style_path(self, style_id: str) -> str:
        """
        Get the path to the style folder.
        """
        return os.path.join(self._all_styles_path(), style_id)
    
    def _style_filepath(self, style_id: str) -> str:
        return os.path.join(self._style_path(style_id), self._STYLE_FILENAME)
    
    def _style_image_path(self, style_id: str, example_type: str) -> str:
        """
        Get the path to the style image folder.
        """
        return os.path.join(self._style_path(style_id), 'images', example_type+'-style')
    
    def _style_image_filepath(self, style_id: str, image_name: str, example_type: str="art") -> str:
        """
        Get the path to the style image.
        """
        return os.path.join(self._style_image_path(style_id, example_type), image_name)

    def create_style(self, data):
        return self._create_object(
            path=self._all_styles_path(),
            data=data,
            create_folder=True,
            filename=self._STYLE_FILENAME
        )
           
    def read_style(self, id):
        """
        Read a style.
        """
        return self._read_object(
            filepath=self._style_filepath(id),
            cls=ComicStyle
        )


    
    def read_all_styles(self):
        """
        Read all styles.
        """
        return self._read_all_objects(
            path=self._all_styles_path(),
            cls=ComicStyle,
            filename=self._STYLE_FILENAME
        )

    
    def update_style(self, data):
        """
        Update a style.
        """
        self._update_object(
            filepath=self._style_filepath(data.id),
            data=data
        )

    
    def delete_style(self, id):
        """
        Delete a style.
        """
        self._delete_object(
            filepath=self._style_filepath(id),
            cls=ComicStyle,
            delete_folder=True
        )
    
    def find_style(self, name: str) -> Optional[ComicStyle]:
        """
        Find a style by name.   The name is case-insensitive and can be a partial match.
        """
        all_styles = self.read_all_styles()
        for style in all_styles:
            if style.name.lower() == name.lower():
                return style
        return None
    
    def find_style_image(self, style_id: str) -> Optional[str]:
        """
        Find the image of a style.
        """
        style = self.read_style(id=style_id)
        if style is None:
            self._logger.warning(f"Style {style_id} not found.")
            return None
        # Check if the style has an image
        if style.image is None:
            self._logger.warning(f"Style {style_id} has no image.")
            return None
        
        # Get the image file path
        return style.image['art']
    
    def find_style_images(self, style_id: str, example_type: str='art') -> list[str]:
        """
        Find all images of a style.
        """
        images = []
        images_path = self._style_image_path(style_id=style_id, example_type=example_type)
        if not os.path.exists(images_path):
            self._logger.warning(f"Style image path {images_path} does not exist.")
            return images
        for img in os.listdir(images_path):
            if img.startswith("."):
                self._logger.debug(f"Skipping hidden image: {img}")
                continue
            
            img_filepath = os.path.join(images_path, img)
            if not os.path.isfile(img_filepath):
                self._logger.debug(f"Skipping non-file item: {img}")
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
    
    _PUBLISHER_FILENAME = 'publisher.json'
    _ALL_PUBLISHERS_FOLDER = 'publishers'

    def _all_publishers_path(self) -> str:
        return os.path.join(self.base_path, self._ALL_PUBLISHERS_FOLDER)
    
    def _publisher_path(self, id: str) -> str:
        """
        Get the path to the publisher folder.
        """
        return os.path.join(self._all_publishers_path(), id)
    
    def _publisher_filepath(self, id: str) -> str:
        return os.path.join(self._publisher_path(id), self._PUBLISHER_FILENAME)


    def create_publisher(self, data: Publisher):
        return self._create_object(
            path=self._all_publishers_path(),
            data=data,
        )

    
    def read_publisher(self, id: str) -> Optional[Publisher]:
        return self._read_object(
            filepath=self._publisher_filepath(id),
            cls=Publisher
        )

    
    def read_all_publishers(self):
        """
        Read all publishers.
        """
        return self._read_all_objects(
            path=self._all_publishers_path(),
            cls=Publisher,
            filename=self._PUBLISHER_FILENAME
        )

    
    def update_publisher(self, data:Publisher):
        """
        Update a publisher.
        """
        self._update_object(
            filepath=self._publisher_filepath(data.id),
            data=data
        )
    
    def delete_publisher(self, publisher_id):
        """
        Delete a publisher.
        """
        return self._delete_object(
            filepath=self._publisher_filepath(publisher_id),
            cls=Publisher,
            delete_folder=True
        )

    def find_publisher(self, name: str) -> Optional[Publisher]:
        """
        Find a publisher by name.   The name is case-insensitive and can be a partial match.
        """
        all_publishers = self.read_all_publishers()
        for publisher in all_publishers:
            if publisher.name.lower() == name.lower():
                return publisher
        return None

    def find_publisher_image(self, publisher_id: str) -> Optional[str]:
        """
        Find the image of a publisher.
        """
        publisher = self.read_publisher(id=publisher_id)
        if publisher is None:
            self._logger.warning(f"Publisher {publisher_id} not found.")
            return None
        # Check if the publisher has an image
        if publisher.image is None:
            self._logger.warning(f"Publisher {publisher_id} has no image.")
            return None
        
        # Get the image file path
        return publisher.image
    
    def find_publisher_images(self, publisher_id: str) -> list[str]:
        """
        Find all images of a publisher.
        """
        publisher_path = self._publisher_path(id=publisher_id)
        images_path = os.path.join(publisher_path, 'images')
        images = []
        if not os.path.exists(images_path):
            self._logger.warning(f"Publisher image path {images_path} does not exist.")
            return images
        for img in os.listdir(images_path):
            if img.startswith("."):
                self._logger.debug(f"Skipping hidden image: {img}")
                continue
            
            img_filepath = os.path.join(images_path, img)
            if not os.path.isfile(img_filepath):
                self._logger.debug(f"Skipping non-file item: {img}")
                continue
            
            images.append(img_filepath)
        return images
        
    def upload_publisher_image(self, publisher_id, image_name, image_data, mime_type):
        """
        Upload an image for a publisher.
        """
        if not mime_type.startswith("image/"):
            raise ValueError("Uploaded file is not an image")
        
        publisher_path = self._publisher_path(id=publisher_id)
        images_path = os.path.join(publisher_path, 'images')
        if not os.path.exists(images_path):
            os.makedirs(images_path, exist_ok=True)
        
        filepath = os.path.join(images_path, image_name)
        with open(filepath, 'wb') as f:
            f.write(image_data.read())
        
        self._logger.info(f"Uploaded publisher image to {filepath}")
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
        path = os.path.join(self._cover_path(issue_id=issue_id, series_id=series_id, location=location), 'uploads')
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
        path = os.path.join(self._panel_path(series_id=series_id, issue_id=issue_id, scene_id=scene_id, panel_id=panel_id), 'images')
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
        path = self._style_image_path(style_id=style_id, example_type=example_type)
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
        scene_path = self._scene_path(
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
        panel_path = self._panel_path(
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
        path = self._character_variant_styled_image_path(
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