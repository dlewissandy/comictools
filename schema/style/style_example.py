from pydantic import BaseModel, Field, field_validator
from enum import StrEnum

class ExampleKind(StrEnum):
    ART = "art"
    CHARACTER = "character"
    NARRATION = "narration"
    CHAT = "chat"
    SHOUT = "shout"
    THOUGHT = "thought"
    SOUND_EFFECT = "sound-effect"
    WHISPER = "whisper"

class StyleExample(BaseModel):
    style_id: str = Field(..., description="The id of the style for which this example is generated.  e.g. 'vintage-four-color'")
    example_id: str = Field(..., description="The id of the example.  This is a unique identifier for the example.")

    # Validate that the example_id is the value of one of the ExampleKind values
    @field_validator("example_id")
    @classmethod
    def validate_example_id(cls, v: str) -> str:
        if v not in ExampleKind._value2member_map_:
            raise ValueError(f"example_id must be one of {list(ExampleKind._value2member_map_.keys())}, got '{v}'")
        return v
    
    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the style example
        """
        return {
            "style_id": self.style_id,
            "example_id": self.example_id,
        }
    
    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the style example
        """
        return {
            "style_id": self.style_id,
        }

    @property
    def id(self) -> str:
        """
        return the id of the style example
        """
        # Normalize the id:
        return self.style_id
    
    @property
    def name(self) -> str:
        """
        return the name of the style example
        """
        return self.style_id.replace("-", " ").title() + " Example"
    