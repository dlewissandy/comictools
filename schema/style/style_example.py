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
    example_type: str = Field(..., description="The id of the example.  This is a unique identifier for the example.")
    image_id: str = Field(..., description="The id of the image for the example.  This is a unique identifier for the image.")
    mime_type: str = Field("image/png", description="The MIME type of the example image. Defaults to 'image/png'.")

    # Validate that the example_type is the value of one of the ExampleKind values    
    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the style example
        """
        return {
            "style_id": self.style_id,
            "example_type": self.example_type,
            "image_id": self.image_id,
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
        return self.image_id
    
    @property
    def name(self) -> str:
        """
        return the name of the style example
        """
        return f"{self.style_id.replace("-", " ").title()} {self.example_type} Example"
    