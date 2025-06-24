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
    id: str = Field(..., description="The unique identifier for the character variant.  This is usually the character name in lowercase with spaces replaced by dashes.  defaults to null")
    series: str = Field(..., description="The comic book series (title) that the character belongs to.  Default to empty string")
    character: str = Field(..., description="The identifier of the character for which this is a variant.  e.g. '<name>'")
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
            "character_id": self.character,
            "variant_id": self.id,
            "series_id": self.series,
        }


#     def format(self, heading_level: int = 2) -> str:
#         """
#         format the character model for display
#         """
#         from schema.style.comic import ComicStyle
#         result = f"""{'#'*heading_level} Character Model ({self.name})
# * **Name**: {self.name}
# * **Race**: {self.race}
# * **Age**: {self.age}
# * **Height**: {self.height}
# * **Gender**: {self.gender}
# * **Description**: {self.description}
# * **Attire**: {self.attire}
#         """.strip()
#         if self.appearance is not None and self.appearance != "":
#             result += f"\n* **Appearance**: {self.appearance}"
#         if self.behavior is not None and self.behavior != "":
#             result += f"\n* **Behavior**: {self.behavior}"
#         return result

#     def render(self, style: ComicStyle):
#         """
#         render the character model using generative AI
#         """

#         style_description = style.format(include_bubble_styles=False)
#         character_description = self.format()
#         character_name = self.name
#         if self.variant is not None and self.variant != "":
#             character_name += f" ({self.variant})"
#         savepath = f"{CHARACTERS_FOLDER}/{self.id}/{style.id}"
#         image_id = render_character_image(character_name, character_description, style_description, savepath)
#         if style.id not in self.image:
#             self.image[style.id] = image_id
#             self.write()
#         return "success"

