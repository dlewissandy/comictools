from pydantic import BaseModel, Field

class CharacterRef(BaseModel):
    series: str = Field(..., description="The series of the character variant")
    character: str = Field(..., description="The name of the character")
    variant: str = Field(..., description="The variant of the character")
    
    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the character variant
        """
        return {
            "series_id": self.series,
            "character_id": self.character,
            "variant_id": self.variant,
        }

    @property
    def id(self) -> str:
        """
        return the id of the character variant
        """
        return f"{self.series}/{self.character}/{self.variant}"
    
    @property
    def name(self) -> str:
        """
        return the name of the character variant
        """
        return f"{self.character.replace('_', ' ').title()} ({self.variant.replace('_', ' ').title()})"
