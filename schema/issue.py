from typing import Optional
from pydantic import BaseModel, Field

        

class Issue(BaseModel):
    issue_id: str = Field(..., description="A unique identifier for the comic book.   Default to str(issue_number)")
    name: str = Field(..., description="The name of the issue.")
    style_id: str = Field(..., description="The style of the comic book.  Default to 'vintage-four-color'")
    series_id: str = Field(..., description="The identifier for the comic book series.  ")
    story: Optional[str] = Field(..., description="The story of the comic book.  Optional.  Default to None")
    
    issue_number: int = Field(..., description="The issue number.  Optional.  default to 1")
    publication_date: Optional[str] = Field(..., description="The publication date of the issue.  Optional.  Default to None")
    
    price: Optional[float] = Field(..., description="The price of the issue.  Default to None")
    writer: Optional[str] = Field(..., description="The writer of the issue.  Optional.   Default to None")
    artist: Optional[str] = Field(..., description="The artist of the issue.  Optional.   Default to None")
    colorist: Optional[str] = Field(..., description="The colorist of the issue.  Optional.   Default to None")
    creative_minds: Optional[str] = Field(..., description="The creative minds behind the issue. Optional. Default to None")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the issue
        """
        return {
            "issue_id": self.issue_id,
            "series_id": self.series_id,
        }
    
    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the issue
        """
        return {
            "series_id": self.series_id,
        }
    
    @property
    def id(self) -> str:
        """
        return the id of the issue
        """
        if self.issue_id is None or self.issue_id == "":
            return str(self.issue_number)
        return self.issue_id