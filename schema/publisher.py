from pydantic import BaseModel, Field
from loguru import logger

class Publisher(BaseModel):
    publisher_id: str  = Field(None, description="The unique identifier for the publisher.  This is usually the publisher name in lowercase with spaces replaced by dashes.  defaults to null")
    name: str = Field(..., description="The name of the publisher")
    description: str | None = Field(..., description="A description of the publisher.  defaults to null")
    logo: str | None = Field(..., description="A description of the logo of the publisher.  defaults to null")
    image: str | None = Field(None, description="The selected image for the logo")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the publisher
        """
        return {
            "publisher_id": self.id,
        }

    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the publisher
        """
        return {}
    
    @property
    def id(self) -> str:
        """
        return the id of the publisher
        """
        return self.publisher_id
