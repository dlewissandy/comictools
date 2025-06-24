from pydantic import BaseModel, Field

class StyledImage(BaseModel):
    style_id: str = Field(..., description="The id of the style for which this image is generated.  e.g. 'vintage-four-color'")
    series_id: str = Field(..., description="The id of the comic book series for which this image is generated.  e.g. 'spiderman'")
    character_id: str = Field(..., description="The id of the character for which this image is generated.  e.g. 'spiderman'")
    variant_id: str = Field(..., description="The id of the character variant for which this image is generated.  e.g. 'base' or 'young'")
    image_id: str = Field(..., description="The id of the image.  This is a unique identifier for the image.")  

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the styled image
        """
        return {
            "style_id": self.style_id,
            "series_id": self.series_id,
            "character_id": self.character_id,
            "variant_id": self.variant_id,
            "image_id": self.image_id,
        }

    @property
    def id(self) -> str:
        """
        return the id of the styled image
        """
        # Normalize the id:
        return self.style_id

    @property
    def name(self) -> str:
        """
        return the name of the styled image
        """
        return self.style_id.replace("-", " ").title() 
