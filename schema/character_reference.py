from pydantic import BaseModel, Field

class CharacterRef(BaseModel):
    series_id: str = Field(..., description="The series of the character variant")
    character_id: str = Field(..., description="The name of the character")
    variant_id: str = Field(..., description="The variant of the character")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the character variant
        """
        return {
            "series_id": self.series_id,
            "character_id": self.character_id,
            "variant_id": self.variant_id,
        }
    
    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the character variant
        """
        return {
            "series_id": self.series_id,
            "character_id": self.character_id,
        }

    @property
    def id(self) -> str:
        """
        return the id of the character variant
        """
        return f"{self.series_id}/{self.character_id}/{self.variant_id}"
    
    @property
    def name(self) -> str:
        """
        return the name of the character variant
        """
        return f"{self.character_id.replace('_', ' ').title()} ({self.variant_id.replace('_', ' ').title()})"
    

