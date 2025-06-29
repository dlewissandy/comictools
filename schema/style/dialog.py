from typing import Optional
from pydantic import BaseModel, Field
from enum import StrEnum

class DialogType(StrEnum):
    CHAT = "chat"
    WHISPER = "whisper"
    SHOUT = "shout"
    THOUGHT = "thought"
    SOUND_EFFECT = "sound-effect"
    NARRATION = "narration"

class BubbleStyle(BaseModel):
    """
    Styling for any kind of text balloon or narration box within a comic.
    """
    shape: str = Field(
        ...,
        description="Geometric form of the bubble boundary guiding how the outline is drawn."
    )
    border: str = Field(
        ...,
        description="Combined border style and thickness for specifying the bubble’s outline appearance."
    )
    fill_color: str = Field(
        description="Descriptive name for the bubble interior color (e.g., 'white', 'light gray'), ensuring consistent text background."
    )
    font: str = Field(
        ...,
        description="Description of the font used for the text inside the bubble."
    )


    
    
    

class BubbleStyles(BaseModel):
    """
    Collection of bubble styles for different types of text.
    """
    chat: BubbleStyle = Field(
        ...,
        description="Bubble style for regular dialogue."
    )
    whisper: BubbleStyle = Field(
        ...,
        description="Bubble style for whispered dialogue."
    )
    shout: BubbleStyle = Field(
        ...,
        description="Bubble style for shouted dialogue."
    )
    thought: BubbleStyle = Field(
        ...,
        description="Bubble style for thought bubbles."
    )
    sound_effect: BubbleStyle = Field(
        ...,
        description="Bubble style for sound effects."
    )
    narration: BubbleStyle = Field(
        ...,
        description="Bubble style for narration text."
    )

