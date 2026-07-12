from typing import Optional
from pydantic import BaseModel, Field
from gui.selection import SelectionItem, SelectedKind

class Series(BaseModel):
    series_id: str = Field(..., description="The unique identifier for the comic book series.  This is usually the series title in lowercase with spaces replaced by dashes.")
    name: str = Field(..., description="The series title of the comic book")
    description: str | None = Field(..., description="A short paragraph describing the comic book series")
    publisher_id: Optional[str] = Field(..., description="The publisher of the comic book.  Optional.  Default to None")

    # THE TITLE ART: the series masthead (hand-lettered wordmark of the
    # title), one per comic style, on transparent acetate — the reference
    # art every cover's title lettering is held to, and an overlay for
    # art-only covers.  Keyed by style_id.
    title_images: dict[str, str] = Field(default_factory=dict, description="The series title masthead art, keyed by comic style id.  Transparent wordmark images used as the official title lettering reference on covers.  Default to empty dict.")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the series
        """
        return {
            "series_id": self.series_id,
        }
    
    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the series
        """
        return {}
    
    @property
    def id(self) -> str:
        """
        return the id of the series
        """
        return self.series_id
        
