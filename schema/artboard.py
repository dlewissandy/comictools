from typing import Optional

from pydantic import BaseModel, Field

from schema.enums import FrameLayout


class ArtBoard(BaseModel):
    """
    AN ART BOARD: a mark that composes on the light table like any other
    board — the series MASTHEAD (hand-lettered wordmark) or the house LOGO.
    Three doors, all the bench's own: write the brief and proof it (from
    text), lay and explode acetates (from layers), or drop a take (from
    image).  Featuring a take writes through to the mark's home
    (series.title_images[style] / publisher.image).

    scope_id is the owner: the series_id for a masthead, the publisher_id
    for a logo.
    """
    board_id: str = Field(..., description="A unique identifier for the art board.")
    scope_id: str = Field(..., description="The owner: series_id (masthead) or publisher_id (logo).")
    board_kind: str = Field(..., description="'masthead' or 'logo'.")
    name: str = Field(..., description="A short name, e.g. 'Rugor masthead' or 'Foglamp Press logo'.")
    description: str = Field("", description="The brief: what the mark should say and how it should be lettered/drawn.  Default empty.")
    style_id: Optional[str] = Field(None, description="The comic style the mark is held to (mastheads are style-keyed).  Default None.")
    aspect: FrameLayout = Field(FrameLayout.LANDSCAPE, description="Mastheads letter wide (landscape); logos square.  Default landscape.")
    image: Optional[str] = Field(None, description="The featured take — the mark as it prints.  Default None.")

    # THE LIGHT TABLE (the same acetate model as Panel/Cover/Insert)
    figure_images: dict[str, str] = Field(default_factory=dict, description="Layer key -> acetate image path.  Default empty.")
    figure_blocking: dict[str, dict] = Field(default_factory=dict, description="Layer key -> blocking (x, y, h, z, rot, flip, on).  Default empty.")
    layer_groups: dict[str, list[str]] = Field(default_factory=dict, description="Named groups of layer keys.  Default empty.")

    # the bench duck-types boards: an artboard walks like one
    character_references: list = Field(default_factory=list, description="Unused on marks; the bench expects the field.  Default empty.")

    @property
    def issue_id(self) -> str:
        """Marks live outside any issue; the bench's data plumbing expects
        the field — blank reads as 'no issue' everywhere it matters."""
        return ""

    @property
    def series_id(self) -> str:
        """The bench reads series_id off every board; a mark's scope stands in
        (a logo's publisher scope simply matches no series assets)."""
        return self.scope_id

    @property
    def primary_key(self) -> dict[str, str]:
        return {"scope_id": self.scope_id, "board_id": self.board_id}

    @property
    def parent_key(self) -> dict[str, str]:
        return {"scope_id": self.scope_id}

    @property
    def id(self) -> str:
        return self.board_id
