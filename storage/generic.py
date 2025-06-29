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
    def read_all_objects(self, cls: BaseModel, primary_key: dict[str,str] = {}) -> list[BaseModel]:
        """
        Read all objects from a directory and return them as a list of instances of the specified class.
        
        Args:
            cls (BaseModel): The class to which the objects should be converted.
            primary_key (dict[str,str]): The primary key of the parent object (if any).   This is used to
              construct the filepath to the object.
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