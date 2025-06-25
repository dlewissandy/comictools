from pydantic import BaseModel, Field
from schema.dialog import Naration, Dialogue, NarationLocation
from schema.enums import FrameLayout
from schema.reference_image import ReferenceImage
from schema.character_reference import CharacterRef

class Panel(BaseModel):
    # IDENTIFIERS
    id: str = Field(..., description="A unique identifier for the panel.   Default to 1")
    issue: str = Field(..., description="The parent issue of the panel.   Default to empty")
    scene: str = Field(..., description="The parent scene of the panel.   Default to empty string")
    series: str = Field(..., description="The parent series of the panel.   Default to empty string")

    #PROPERTIES
    description: str = Field(..., description="A detailed description of the image in the panel.   This should describe the image in sufficient detail so that different artists could from this information alone reproduce the same image.   This should include the setting, foreground, background, characters, props, scenery and any other elements in the panel.")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to square")
    characters: list[CharacterRef] = Field(..., description="A dictionary mapping the names of the characters that appear in the panel to the visual variant that should be used as reference.   Default to empty dict")

    # DIALOGUE AND NARATION
    narration: list[Naration] = Field(..., description="The narration of the panel.  default to empty list")
    dialogue: list[Dialogue] = Field(..., description="The dialogue of the panel, default to empty list")
    
    # IMAGES
    image: str | None = Field(None, description="The selected image for this panel.  default to None")
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel.  default to empty list")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the panel model
        """
        return {
            "panel_id": self.id,
            "issue_id": self.issue,
            "scene_id": self.scene,
            "series_id": self.series,
        }


#     def format(self, heading_level: int = 1) -> str:
#         """
#         format the panel model for display
#         """
#         text = f"""
# * **story**: {self.description}
# * **characters**:
# {"\n".join([f"  - {character}" for character in self.characters])}
# * **aspect**: {self.aspect}
# """
#         return text
    
    def format_dialogue(self) -> str:
        """
        format the dialogue for display
        """
        text = ""
        top = "\n\n".join([n.format() for n in self.narration if n.location == NarationLocation.TOP])
        bottom = "\n\n".join([n.format() for n in self.narration if n.location == NarationLocation.BOTTOM])
        dialogue = "\n\n".join([d.format() for d in self.dialogue])
        if top:
            text += top + f"\n\n"
        if dialogue:
            text += dialogue + "\n\n"
        if bottom:
            text += bottom
        return text

    

        

        
