from pydantic import BaseModel, Field


class CharacterVariantMinimal(BaseModel):
    description: str = Field(..., description="A 3-5 sentence description of the character.  This should be sufficient to distinguish the character from others.")
    race: str = Field(..., description="The race of the character.  Default to 'human'")
    gender: str = Field(..., description="The gender of the character")
    age: str = Field(..., description="The age of the character.  Default to 'adult'")
    height: str = Field(..., description="The height of the character.  Default to 'average'")
    attire: str = Field(..., description="A detailed description (3-5 paragraphs) of what the character is wearing.   This should be in sufficient detail so that an artist can recreate the character's attire without a reference image.")
    behavior: str  = Field(..., description="Notes on the The character's behavior")
    appearance: str  = Field(..., description="A detailed description (3-5 paragraphs) of the character's physical appearance and attributes.   This should be in sufficient detail so that an artist can recreate the character's appearance without a reference image.    ")


class CharacterVariant(BaseModel):
    variant_id: str = Field(..., description="The unique identifier for the character variant.  This is usually the character name in lowercase with spaces replaced by dashes.  defaults to null")
    series_id: str = Field(..., description="The comic book series (title) that the character belongs to.  Default to empty string")
    character_id: str = Field(..., description="The identifier of the character for which this is a variant.  e.g. '<name>'")
    description: str = Field(..., description="A 3-5 sentence description of the character.  This should be sufficient to distinguish the character from others.")
    name: str = Field(None, description="The variant of the variant. E.g 'young', 'armored', etc.")
    race: str = Field(..., description="The race of the character.  Default to 'human'")
    gender: str = Field(..., description="The gender of the character")
    age: str = Field(..., description="The age of the character.  Default to 'adult'")
    height: str = Field(..., description="The height of the character.  Default to 'average'")
    attire: str = Field(..., description="What the character is wearing")
    behavior: str  = Field(..., description="Notes on the The character's behavior")
    appearance: str  = Field(..., description="Notes on the The character's physical appearance and attributes")
    images: dict[str,str] = Field(..., description="The reference images that can be used by artists to draw this character.   defaults {}")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the character variant
        """
        return {
            "character_id": self.character_id,
            "variant_id": self.variant_id,
            "series_id": self.series_id,
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
        # Normalize the id:
        return self.variant_id