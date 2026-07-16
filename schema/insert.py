from typing import Optional
from pydantic import BaseModel, Field
from schema.character_reference import CharacterRef
from schema.enums import FrameLayout


class Insert(BaseModel):
    """
    A FULL-PAGE INSERT: a poster, an ad, a pin-up, the mailbag — a page
    that isn't story panels but belongs in the book.  Anchored after a
    scene (0 = right after the script pages), it prints full-bleed.

    An insert is a BOARD like a cover: it composes on THE LIGHT TABLE and,
    like a cover, is its own scene — it owns style_id and setting_id.
    """
    insert_id: str = Field(..., description="A unique identifier for the insert.")
    issue_id: str = Field(..., description="The issue this insert belongs to.")
    series_id: str = Field(..., description="The series this insert belongs to.")
    kind: str = Field("poster", description="What kind of page: 'poster', 'ad', 'pin-up', 'mailbag', 'title-page'.  Default to 'poster'.")
    name: str = Field(..., description="A short name for the insert, e.g. 'Carnival poster'.")
    description: str = Field("", description="What the page shows, in enough detail to render it.  For a mailbag: the letters and replies.  Default to empty string.")
    after_scene_number: int = Field(0, description="The insert appears after this scene number (0 = right after the script pages, before scene 1).  Default to 0.  Ignored when `location` is set.")
    location: Optional[str] = Field(None, description="Pin the insert to a cover slot instead of a page turn: 'inside-front' or 'inside-back' (the classic homes for ads and the mailbag).  The indicia still prints over inside-front art.  Default None (the insert rides its after_scene_number page turn).")
    image: Optional[str] = Field(None, description="The rendered full-page art.  Default to None.")

    # THE LIGHT TABLE (same acetate model as Panel and Cover — an insert
    # composes on the same table, so the fields match exactly)
    aspect: FrameLayout = Field(FrameLayout.PORTRAIT, description="A full page is portrait.  Default to portrait.")
    style_id: Optional[str] = Field(None, description="The art style of the insert.  Default to None (the issue's style).")
    setting_id: Optional[str] = Field(None, description="An optional setting whose master background anchors the page (a pin-up in the fortune teller's tent).  Default to None.")
    character_references: list[CharacterRef] = Field(default_factory=list, description="The characters appearing on the page.  Default to empty list.")
    figure_images: dict[str, str] = Field(default_factory=dict, description="Posed figure acetates for this insert: maps 'character_id/variant_id' to a transparent cut-out image.  Default to empty dict.")
    figure_blocking: dict[str, dict] = Field(default_factory=dict, description="Blocking for each acetate: maps a layer key to {x, y, h, z}.  Default to empty dict.")
    layer_groups: dict[str, list[str]] = Field(default_factory=dict, description="Named groups of light-table layers.  Default to empty dict.")

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
