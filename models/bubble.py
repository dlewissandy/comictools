from pydantic import BaseModel, Field
from enum import StrEnum

class NarationLocation(StrEnum):
    TOP = "top"
    BOTTOM = "bottom"

class DialogueEmphasis(StrEnum):
    CHAT = "chat"
    WHISPER = "whisper"
    SHOUT = "shout"
    THOUGHT = "thought"
    SOUND_EFFECT = "sound effect"

class Naration(BaseModel):
    text: str = Field(..., description="The narration text")
    # The location is either "top" or "bottom"
    location: NarationLocation = Field(..., description="The location of the narration text")

    def format(self) -> str:
        """
        Format the narration for display
        """
        location = self.location.value
        text = self.text
        return f"**Narration** [{location}]: {text}"

class Dialogue(BaseModel):
    character: str = Field(..., description="The name of the character")
    text: str = Field(..., description="The dialogue text")
    # The location is either "top" or "bottom"
    emphasis: DialogueEmphasis = Field(..., description="The emphasis of the dialogue text")

    def format(self) -> str:
        """
        Format the dialogue for display
        """
        character_name = self.character.replace("-", " ").title()
        emphasis = self.emphasis.value
        text = self.text
        return f"**{character_name}** ({emphasis}): {text}"
