from loguru import logger
from pydantic import BaseModel, Field
from nicegui import ui


class SelectionItem(BaseModel):
    name: str = Field(..., description="The name that will be displayed on the breadcrumbs")
    id: str | None = Field(..., description="The id of the item.  This will be used to identify the item in the system.")
    kind: str = Field(..., description="The kind of item.  This will be used to identify the item in the system.")

def thoughts_container():
    """
    Create a container for displaying the bot's thoughts.
    
    Returns:
        A UI element representing the thoughts container.
    """
    return ui.expansion("Thoughts", value=False).classes('w-full').classes("text-sm")

