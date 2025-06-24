from typing import Optional
from pydantic import BaseModel, Field

        

class Issue(BaseModel):
    id: str = Field(..., description="A unique identifier for the comic book.   Default to str(issue_number)")
    name: str = Field(..., description="The name of the issue.")
    style: str = Field(..., description="The style of the comic book.  Default to 'vintage-four-color'")
    series: str = Field(..., description="The identifier for the comic book series.  ")
    story: Optional[str] = Field(..., description="The story of the comic book.  Optional.  Default to None")
    
    issue_number: int = Field(..., description="The issue number.  Optional.  default to 1")
    publication_date: Optional[str] = Field(..., description="The publication date of the issue.  Optional.  Default to None")
    
    price: Optional[float] = Field(..., description="The price of the issue.  Default to None")
    writer: Optional[str] = Field(..., description="The writer of the issue.  Optional.   Default to None")
    artist: Optional[str] = Field(..., description="The artist of the issue.  Optional.   Default to None")
    colorist: Optional[str] = Field(..., description="The colorist of the issue.  Optional.   Default to None")
    creative_minds: Optional[str] = Field(..., description="The creative minds behind the issue. Optional. Default to None")

    characters: list[str] = Field(..., description="The characters in the issue.  Default to empty string")
    style: Optional[str]  = Field(..., description="The style of the comic book.   Default to 'vintage-four-color'")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the issue
        """
        return {
            "issue_id": self.id,
            "series_id": self.series,
        }

    def format(self, heading_level: int=1) -> str:
        """
        Format the comic book for display
        """
        text = f"{'#'* heading_level} ISSUE {self.issue_number}\n\n"
        if self.title is not None:
            text += f" * **title** {self.title}\n\n"
        if self.publication_date is not None:
            text += f" * **date** {self.publication_date}\n\n"
        if self.writer is not None:
            text += f" * **writer** {self.writer}\n\n"
        if self.artist is not None:
            text += f" * **artist** {self.artist}\n\n"
        if self.colorist is not None:
            text += f" * **colorist** {self.colorist}\n\n"
        if self.creative_minds is not None:
            text += f" * **creative minds** {self.creative_minds}\n\n"
        if self.price is not None:
            text += f" * **price** {self.price}\n\n"
        return text