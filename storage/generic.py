from typing import Optional, BinaryIO
from abc import ABC, abstractmethod
from pydantic import BaseModel
from dataclasses import dataclass
from schema import *

class GenericStorage(ABC):
    """
    Abstract base class for generic storage systems.
    """

    @abstractmethod
    def create_object(self, data: BaseModel) -> str:
        """
        Create a new object in the specified path with the given data.
        """
        pass

    @abstractmethod
    def read_object(self, cls: BaseModel, primary_key: dict[str,str]={}) -> Optional[BaseModel]:
        """
        Read an object from a file and return it as an instance of the specified class.

        Args:
            cls (BaseModel): The class to which the object should be converted.
            primary_key (dict[str,str]): The primary key of the object to read.   This is used to
              construct the filepath to the object.
        """
        pass
            
    @abstractmethod
    def read_all_objects(self, cls: BaseModel, primary_key: dict[str,str] = {}, order_by: Optional[str] = None) -> list[BaseModel]:
        """
        Read all objects from a directory and return them as a list of instances of the specified class.
        
        Args:
            cls (BaseModel): The class to which the objects should be converted.
            primary_key (dict[str,str]): The primary key of the parent object (if any).   This is used to
              construct the filepath to the object.
            order_by: An optional key that represents the field in which the instances will be returned
        """
        pass
        
    @abstractmethod
    def update_object(self, data: BaseModel) -> None:
        """
        Update an existing object in the specified file with the given data.
        
        Args:
            filepath (str): The path to the file containing the object.
            data (BaseModel): The data to update the object with.
        """
        pass

    @abstractmethod
    def delete_object(self, cls: BaseModel, primary_key: dict[str,str]) -> Optional[BaseModel]:
        """
        Delete an object from a file.   If it existed, then return the object so
        that it could be used for further processing (e.g. logging, undoing, unlinking, etc).

        Args:
            filepath (str): The path to the file containing the object.
            delete_folder (bool): Whether to delete the folder containing the object. Defaults to True.
            cls (BaseModel): The class of the object to be deleted.
        """
        pass

    @abstractmethod
    def list_images(self, obj: BaseModel) -> list[str]:
        """
        List all images associated with a given object.

        Args:
            obj (BaseModel): The object for which to list images.

        Returns:
            list[str]: A list of image file paths.
        """
        pass

    @abstractmethod
    def find_image(self, obj: BaseModel, locator: str) -> Optional[str]:
        """
        Find an image associated with a given object.
        Args:
            obj (BaseModel): The object for which to find the image.
            locator (str): The locator of the image.
        Returns:
            Optional[str]: The file path of the image if found, otherwise None.
        """
        pass

    @abstractmethod
    def list_uploads(self, obj: BaseModel) -> list[str]:
        """
        List all uploads associated with a given object.

        Args:
            obj (BaseModel): The object for which to list uploads.

        Returns:
            list[str]: A list of upload file paths.
        """
        pass

    @abstractmethod
    def upload_image(self, obj: BaseModel, name: str, data: BinaryIO, mime_type: str) -> str:
        """
        Upload an image for a given object.

        Args:
            obj (BaseModel): The object to which the image belongs.
            name (str): The name of the image file.
            data (BinaryIO): The binary data of the image.
            mime_type (str): The MIME type of the image.

        Returns:
            str: The file locator of the uploaded image.
        """
        pass

    @abstractmethod
    def upload_reference_image(self, obj: BaseModel, name: str, data: BinaryIO, mime_type: str) -> str:
        """
        Upload a reference image for a given object.

        Args:
            obj (BaseModel): The object to which the image belongs.
            name (str): The name of the image file.
            data (BinaryIO): The binary data of the image.
            mime_type (str): The MIME type of the image.

        Returns:
            str: The file locator of the uploaded image.
        """
        pass