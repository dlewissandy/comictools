from pydantic import BaseModel, Field


class PanelRef(BaseModel):
    """A panel placed on a page (panels live under scenes)."""
    scene_id: str = Field(..., description="The scene the panel belongs to.")
    panel_id: str = Field(..., description="The panel to place.")


class PanelCell(BaseModel):
    """A panel's exact box on the page, in the 6-wide x 10-tall unit grid a
    US comic page divides into.  Fractions are legal (thirds keep bands on
    grid); art is cropped-to-fill its box, never distorted."""
    scene_id: str = Field(..., description="The scene the panel belongs to.")
    panel_id: str = Field(..., description="The panel placed in this cell.")
    x: float = Field(..., description="Left edge, 0-6 units from the page's left.")
    y: float = Field(..., description="Top edge, 0-10 units from the page's top.")
    w: float = Field(..., description="Width in units.")
    h: float = Field(..., description="Height in units.")


class Page(BaseModel):
    """
    One page of the printed issue.   A page is rows of panels: each row holds
    1-3 panels side by side; a single row with a single panel is a splash page.
    Panels keep their aspect; a row's height follows from fitting its panels
    across the page width.

    A STITCHED page also carries cells: exact boxes on the 6x10 unit grid,
    produced by the page stitcher's banding.  When cells are present they are
    the authoritative geometry and rows mirror the band grouping (so every
    rows-based reader keeps working); edits re-stitch the page.
    """
    page_id: str = Field(..., description="A unique identifier for the page.  Usually 'page-<number>'.")
    issue_id: str = Field(..., description="The issue this page belongs to.")
    series_id: str = Field(..., description="The series this page belongs to.")
    page_number: int = Field(..., description="The page number in reading order, 1-based.")
    rows: list[list[PanelRef]] = Field(default_factory=list, description="The page grid: a list of rows, each row a list of 1-3 panels placed left to right.")
    cells: list[PanelCell] = Field(default_factory=list, description="Exact unit-grid boxes (6 wide x 10 tall) for each placed panel.  Authoritative when non-empty; kept in sync with rows by the stitcher.")

    @property
    def primary_key(self) -> dict[str, str]:
        return {
            "page_id": self.page_id,
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
        return self.page_id
