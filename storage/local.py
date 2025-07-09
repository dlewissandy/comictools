import os
import json
import shutil
from uuid import uuid4
from loguru import logger
from typing import Optional, BinaryIO
from pydantic import BaseModel
from storage.generic import GenericStorage
from schema import *
from storage.filepath import (
    FILEPATH_TEMPLATES,
    ROOT_PATH_TEMPLATES,
    IMAGE_FILE_EXTENSIONS,
    cls_to_filepath,
    obj_to_filepath,
    obj_to_rootpath,
    obj_to_path,
    obj_to_imagepath,
    obj_to_reference_path,
    extract_format_keys,
    template_to_filepath,
    get_basenames,
    generate_unique_id,
    get_object_id_field_name,
    )




class LocalStorage(GenericStorage):

    def __init__(self, base_path: str):
        super().__init__()
        self.base_path = base_path
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

    def create_object(self, data: BaseModel) -> str:
        """
        Create a new object in the specified path with the given data.   This new object will
        be assigned a unique ID, and will be stored in a file using the object's 
        FILEPATH_TEMPLATE.

        Args:
            data (BaseModel): The data to create the object with.   Strictly speaking, this
            should be an instance of a class that has a primary_key, parent_key and id 
            property.

        Returns:
            str: The unique ID of the created object.
        """
        logger.trace(f"creating {data.__class__.__name__} with data: {data.model_dump()}")

        # Determine the root path of the object by using the appropriate path templates.
        # If the object is not a valid class, then this method throws an error.
        rootpath = obj_to_rootpath(data)

        # Verify that the rootpath exists and is a directory.   If it does not exist, then
        # create it.   If it exists but is not a directory, then raise an error.
        if not os.path.exists(rootpath):
            os.makedirs(rootpath)        
        if not os.path.isdir(rootpath):
            raise NotADirectoryError(f"Path {rootpath} is not a directory.")
        
        # Get the object's identifier field name.   This field will need to be set to ensure
        # That the primary key is globally unique.   If the field is not found then raise
        # an error.
        id_field = get_object_id_field_name(data)
        if id_field is None:
            msg = f"Object {data.__class__.__name__} does not have an identifier field."
        if not hasattr(data, id_field):
            msg = f"Object {data.__class__.__name__} does not have an id field named {id_field}."
            logger.error(msg)
            raise ValueError(msg)

        # If we get here, we know that the rootpath exists and is a directory, and that the
        # object has an identifier field.   We can now generate a unique ID for the object
        # and set the id field to that ID.   
        obj_id = generate_unique_id(path=rootpath, create_folder=True)
        setattr(data, id_field, obj_id)  # Set the id field to the generated unique ID
        filepath = obj_to_filepath(data)  # This will raise an error if the object is not valid
        parent_path = os.path.dirname(filepath)
        # make sure that file's folder exists
        if not os.path.exists(parent_path):
            os.makedirs(os.path.dirname(filepath))
        if not os.path.isdir(parent_path):
            raise NotADirectoryError(f"Path {parent_path} is not a directory.")

        # Write the object to the file in JSON format.   The file will be created if it does not exist.
        logger.debug(f"Writing object {data.__class__.__name__} to file {filepath}")
        with open(filepath, 'w') as f:
            f.write(data.model_dump_json(indent=2))
            f.flush()
            os.fsync(f.fileno())

        # sync the parent folder
        fs_dir = os.open(parent_path, os.O_DIRECTORY)
        os.fsync(fs_dir)
        os.close(fs_dir)

        # Return the unique ID of the created object.
        return obj_id

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
            logger.debug(f"File {filepath} does not exist. Returning None.")
            return None
        
        if not os.path.isfile(filepath):
            logger.error(f"Path {filepath} is not a file.")
            raise FileNotFoundError(f"Path {filepath} is not a file.")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
            f.flush()
            os.fsync(f.fileno())

        # sync the parent folder
        parent_path = os.path.dirname(filepath)
        fs_dir = os.open(parent_path, os.O_DIRECTORY)
        os.fsync(fs_dir)
        os.close(fs_dir)

        try: 
            return cls.model_validate(data)
        except Exception as e:
            msg = f"Failed to validate: {e}"
            logger.error(msg)
            raise

    def read_all_objects(self, cls: BaseModel, primary_key: dict[str,str] = {}, order_by: Optional[str] = None) -> list[BaseModel]:
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
            logger.debug(f"Path {rootpath} does not exist. Returning empty list.")
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

        if order_by is not None:
            objects.sort(key=lambda x: getattr(x, order_by))
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
            f.flush()
            os.fsync(f.fileno())

        # sync the parent folder
        parent_path = os.path.dirname(filepath)
        fs_dir = os.open(parent_path, os.O_DIRECTORY)
        os.fsync(fs_dir)
        os.close(fs_dir)

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
            logger.debug(f"File {cls.__name__} does not exist. Cannot delete.")
            return None
        
        filepath = obj_to_filepath(instance)
        logger.debug(f"Deleting file at {filepath}")
        shutil.rmtree(os.path.dirname(filepath), ignore_errors=True)

        # sync the parent folder
        parent_path = os.path.dirname(filepath)
        fs_dir = os.open(parent_path, os.O_DIRECTORY)
        os.fsync(fs_dir)
        os.close(fs_dir)

        return instance
    
    def _list_images(self, path: str) -> list[str]:
        logger.debug(f"Images path: {path}")
        images = []
        # If the folder does not exist, return an empty list
        if not os.path.exists(path):
            return images
        if not os.path.isdir(path):
            logger.error(f"Path {path} is not a directory.")
            raise NotADirectoryError(f"Path {path} is not a directory.")
        # If the image exists, then return all the image files in the folder.

        # Sync the directory
        dir_fd = os.open(path, os.O_DIRECTORY)
        os.fsync(dir_fd)  # ensure directory entry is committed
        os.close(dir_fd)

        for item in os.listdir(path):
            if item.startswith("."):
                logger.debug(f"Skipping hidden item: {item}")
                continue
            item_path = os.path.join(path, item)
            if not os.path.isfile(item_path):
                logger.debug(f"Skipping non-file item: {item}")
                continue
            ext = os.path.splitext(item)[1].lower()
            if ext in IMAGE_FILE_EXTENSIONS:
                images.append(item_path)
        return images

    def list_images(self, obj: BaseModel) -> list[str]:
        """
        List all images associated with a given object.
        """
        logger.trace(f"Listing images for {obj.__class__.__name__} with primary key: {obj.primary_key}")
        return self._list_images(obj_to_imagepath(obj))
    
    def find_image(self, obj: BaseModel, locator: str) -> Optional[str]:
        """
        Find an image associated with a given object.  The image_locator must be a file path.

        Args:
            obj (BaseModel): The object to which the image is associated.
            image_locator (str): The file path of the image to find.
        """
        logger.trace(f"Finding image for {obj.__class__.__name__} with primary key: {obj.primary_key} and image locator: {locator}")
        images = self.list_images(obj)
        logger.debug(f"Images found: {images}")
        for image in images:
            if image == locator:
                return image
        return None
    
    def find_reference_image(self, obj: BaseModel, image_locator: str) -> Optional[str]:
        """
        Find a reference image associated with a given object.  The image_locator must be a file path.
        The relation is used to determine the folder in which the image is stored.

        Args:
            obj (BaseModel): The object to which the image is associated.
            image_locator (str): The file path of the image to find.
            relation (Relation): The relation to use to determine the folder in which the image is stored.
        """
        logger.trace(f"Finding reference image for {obj.__class__.__name__} with primary key: {obj.primary_key}, image locator: {image_locator}, and relation: {relation}")
        uploads = self.list_uploads(obj)
        for upload in uploads:
            if upload == image_locator:
                return upload
        return None

    def list_uploads(self, obj: BaseModel) -> list[str]:
        """
        List all uploads associated with a given object.  These are stored in the 
        "uploads/relation" folder of the object.   
        """
        logger.trace(f"Listing uploads for {obj.__class__.__name__} with primary key: {obj.primary_key}")
        return self._list_images(obj_to_imagepath(obj))

    def _upload_image(self, path: str, name: str, data: BinaryIO, mime_type: str) -> str:
        if not mime_type.startswith("image/"):
            raise ValueError("Uploaded file is not an image")

        if not os.path.exists(path):
            os.makedirs(path)
        filepath = os.path.join(path, name)
        with open(filepath, 'wb') as f:
            f.write(data.read())
            f.flush()
            os.fsync(f.fileno())

        # sync the parent folder
        parent_path = os.path.dirname(filepath)
        fs_dir = os.open(parent_path, os.O_DIRECTORY)
        os.fsync(fs_dir)
        os.close(fs_dir)


        logger.info(f"Uploaded panel reference image to {filepath}")
        return filepath

    def upload_image(self, obj: BaseModel, name: str, data: BinaryIO, mime_type: str) -> str:
        """ Upload an image for a given object.   The image will be stored in uploads folder
        of the object.   On success it will return the file path of the uploaded image.
        """
        return self._upload_image(obj_to_imagepath(obj), name, data, mime_type)
    
    def upload_reference_image(self, obj: BaseModel, name: str, data: BinaryIO, mime_type: str) -> str:
        """ Upload an image for a given object.   The image will be stored in uploads folder
        of the object.   On success it will return the file path of the uploaded image.
        """
        return self._upload_image(obj_to_reference_path(obj), name, data, mime_type)


    # -------------------------------------------------------------------------
    # Series CRUD Operations
    # -------------------------------------------------------------------------
    def find_series_image(self, series_id: str) -> Optional[str]:
        issues: list[Issue] = self.read_all_objects(cls=Issue, primary_key={"series_id": series_id})
        # sort the issues by issue number
        issues.sort(key=lambda x: x.issue_number if x.issue_number is not None else float('inf'))
        for issue in issues:
            issue_covers: list[Cover] = self.read_all_objects(Cover, primary_key={"series_id": series_id, "issue_id": issue.issue_id})
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
    # Character CRUD Operations
    # -------------------------------------------------------------------------
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
            logger.debug(f"Variant {variant_id} for character {character_id} in series {series_id} not found.")
            return None
        variant: CharacterVariant = variant
        # We are going to try to find an image using any of the styles
        styles = variant.images.keys()
        sorted_styles = sorted(styles, key=lambda x: x.lower())
        for style in sorted_styles:
            filepath = variant.images.get(style, None)
            if os.path.exists(filepath):
                    return filepath
        logger.debug(f"No image found for character model {variant.character_id}({variant.name}).")
        return None

    # -------------------------------------------------------------------------
    # StyledImage Crud Operations
    # -------------------------------------------------------------------------
    
    def find_styled_image(self, series_id: str, character_id: str, variant_id: str, style_id: str, name: str) -> Optional[StyledVariant]:
        filepath = name

        if not os.path.exists(filepath):
            logger.debug(f"Styled image {name} for character {character_id} in series {series_id} with variant {variant_id} and style {style_id} not found.")
            return None
        
        if not os.path.isfile(filepath):
            logger.error(f"Path {filepath} is not a file.")
            raise NotADirectoryError(f"Path {filepath} is not a file.")
        

        return filepath

    def find_styled_images(self, series_id: str, character_id: str, variant_id: str, style_id: str) -> list[StyledVariant]:
        variant = self.read_object(
            cls=CharacterVariant,
            primary_key={
                "series_id": series_id,
                "character_id": character_id,
                "variant_id": variant_id
            }
        )
        style = self.read_object(
            cls=ComicStyle,
            primary_key={"style_id": style_id}
        )
        if variant is None:
            logger.debug(f"Variant {variant_id} for character {character_id} in series {series_id} not found.")
            return []
        if style is None:
            logger.debug(f"Style {style_id} not found.")
            return []
        return self.list_images(StyledVariant(
            series_id=series_id,
            character_id=character_id,
            variant_id=variant_id,
            style_id=style_id,
            image_id=""
        ))


    # -------------------------------------------------------------------------
    # Scene CRUD Operations
    # -------------------------------------------------------------------------
    def find_scene_image(self, scene_id: str, issue_id: str, series_id: str) -> Optional[str]:
        """
        Find the image of a scene.   This will search all the panels in the scene,
        ordered by their sequence number, and return the first image that exists.
        If no image is found in any of the panels, then return None.

        """
        panels: list[Panel] = self.read_all_objects(cls=Panel, primary_key={"scene_id": scene_id, "issue_id": issue_id, "series_id": series_id})    
        panels.sort(key=lambda x: x.panel_number)
        
        # Find the first panel that has an image
        for panel in panels:
            if panel.image is None:
                continue
            filepath = self.find_image(
                obj=panel,
                locator=panel.image
            )
            if filepath is not None:
                return filepath
        # No image found in any of the panels
        return None
    