from enum import StrEnum

from typing import Union, Literal, Annotated
from pydantic import BaseModel, Field

class BeforeFirst(BaseModel):
    kind: Literal["before_first"] = Field(default="before_first", exclude=True, description="Insert the new item before the first item in the list.")

class Before(BaseModel):
    index: int
    kind: Literal["before"] = Field(default="before", exclude=True, description="Insert the new item before the item at the specified list index.")

class After(BaseModel):
    index: int
    kind: Literal["after"] = Field(default="after", exclude=True, description="Insert the new item after the item at the specified list index.")

class AfterLast(BaseModel):
    kind: Literal["after_last"] = Field(default="after_last", exclude=True, description="Insert the new item after the last item in the list.")

InsertionLocation = Annotated[
    Union[BeforeFirst, Before, After, AfterLast],
    Field(discriminator="kind")
]

class FrameLayout(StrEnum):
    SQUARE = "square"
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"

class Relation(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    LEFT = "left"
    RIGHT = "right"
    ABOVE = "above"
    BELOW = "below"
    BACKGROUND = "background"


class CoverLocation(StrEnum):
    FRONT = "front"
    INSIDE_FRONT = "inside-front"
    INSIDE_BACK = "inside-back"
    BACK = "back"

def frame_layout_to_dims(aspect: FrameLayout) -> str:
    """
    Convert a FrameLayout to a string representation of its dimensions.
    """
    if aspect == FrameLayout.LANDSCAPE:
        return "1536x1024"  # 3:2 aspect ratio
    elif aspect == FrameLayout.PORTRAIT:
        return "1024x1536"  # 2:3 aspect ratio
    else:
        return "1024x1024"  # Default to square for other cases

def frame_dimensions(aspect: FrameLayout) -> tuple[int, int]:
    if aspect == FrameLayout.LANDSCAPE:
        return 3,2
    elif aspect == FrameLayout.PORTRAIT:
        return 2,3
    else:
        return 2,2
    