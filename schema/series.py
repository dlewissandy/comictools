from typing import Optional
from pydantic import BaseModel, Field

class Series(BaseModel):
    id: str = Field(..., description="The unique identifier for the comic book series.  This is usually the series title in lowercase with spaces replaced by dashes.")
    name: str = Field(..., description="The series title of the comic book")
    description: str | None = Field(..., description="A short paragraph describing the comic book series")
    publisher: Optional[str] = Field(..., description="The publisher of the comic book.  Optional.  Default to None")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the series
        """
        return {
            "sceries_id": self.id,
        }
    
    def format(self):
        self_json = self.model_dump()
        result = "## Series\n\n"
        for key, value in self_json.items():
            if value is None or value == "":
                continue
            result += f"* **{key.replace('_', ' ').capitalize()}**: {value}\n\n"
        return result
    