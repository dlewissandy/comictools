from pydantic import BaseModel, Field
from schema.enums import Relation

class ReferenceImage(BaseModel):
    id: str = Field(..., description="A unique identifier for the reference image")
    image: str = Field(..., description="The filepath of the reference image")
    relation: Relation = Field(..., description="The relation of the reference image to the panel")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the reference image
        """
        return {
            "image_id": self.id,
            "relation": self.relation.value
        }
