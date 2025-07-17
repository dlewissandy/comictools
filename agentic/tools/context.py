from loguru import logger
from pydantic import BaseModel
from gui.state import APPState
from gui.selection import selection_to_context

def read_context( state: APPState) -> list[BaseModel]:
    """
    Reads the context from the selection and returns a list of BaseModel objects.
    
    Args:
        selection: A list of SelectionItem objects representing the current selection.
    
    Returns:
        A list of BaseModel objects representing the context of the selection.
    """
    selection = state.selection
    storage = state.storage
    context = selection_to_context(selection)
    objects = []
    for item in context:
        cls, pk = item
        obj = storage.read_object(cls, pk)
        if obj is None:
            msg = f"Object of type {cls.__name__} with primary key {pk} not found in the database."
            logger.error(msg)
            raise ValueError(msg)
        objects.insert(0, obj)  # Insert at the beginning to have the most specific object first
    return objects
