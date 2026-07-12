from typing import Optional
from pydantic import BaseModel, Field


class Insert(BaseModel):
    """
    A FULL-PAGE INSERT: a poster, an ad, a pin-up, the mailbag — a page
    that isn't story panels but belongs in the book.  Anchored after a
    scene (0 = right after the script pages), it prints full-bleed.
    """
    insert_id: str = Field(..., description="A unique identifier for the insert.")
    issue_id: str = Field(..., description="The issue this insert belongs to.")
    series_id: str = Field(..., description="The series this insert belongs to.")
    kind: str = Field("poster", description="What kind of page: 'poster', 'ad', 'pin-up', 'mailbag', 'title-page'.  Default to 'poster'.")
    name: str = Field(..., description="A short name for the insert, e.g. 'Carnival poster'.")
    description: str = Field("", description="What the page shows, in enough detail to render it.  For a mailbag: the letters and replies.  Default to empty string.")
    after_scene_number: int = Field(0, description="The insert appears after this scene number (0 = right after the script pages, before scene 1).  Default to 0.")
    image: Optional[str] = Field(None, description="The rendered full-page art.  Default to None.")

    @property
    def primary_key(self) -> dict[str, str]:
        return {
            "insert_id": self.insert_id,
            "issue_id": self.issue_id,
            "series_id": self.series_id,
        }

    @property
    def parent_key(self) -> dict[str, str]:
        return {
            "issue_id": self.issue_id,
            "series_id": self.series_id,
        }

    @property
    def id(self) -> str:
        return self.insert_id
