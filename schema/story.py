from pydantic import BaseModel, Field


class Story(BaseModel):
    """
    One story in the issue — classic comics run features and backups in a
    single book.  Stories are ordered script sections: each prints as a
    manuscript page in the open book and breaks down into scenes.
    """
    story_id: str = Field(..., description="A unique identifier for the story.")
    issue_id: str = Field(..., description="The issue this story belongs to.")
    series_id: str = Field(..., description="The series this story belongs to.")
    story_number: int = Field(..., description="The story's order in the book, 1-based.")
    name: str = Field(..., description="The story's title, e.g. 'The Witchlight Carnival' or 'Backup: The Mailbag Mystery'.")
    text: str = Field("", description="The story's script text.  Default to empty string.")

    @property
    def primary_key(self) -> dict[str, str]:
        return {
            "story_id": self.story_id,
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
        return self.story_id
