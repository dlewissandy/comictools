from enum import StrEnum

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