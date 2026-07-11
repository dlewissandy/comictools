from pydantic import BaseModel, Field


class PanelRef(BaseModel):
    """A panel placed on a page (panels live under scenes)."""
    scene_id: str = Field(..., description="The scene the panel belongs to.")
    panel_id: str = Field(..., description="The panel to place.")


class Page(BaseModel):
    """
    One page of the printed issue.   A page is rows of panels: each row holds
    1-3 panels side by side; a single row with a single panel is a splash page.
    Panels keep their aspect; a row's height follows from fitting its panels
    across the page width.
    """
    page_id: str = Field(..., description="A unique identifier for the page.  Usually 'page-<number>'.")
    issue_id: str = Field(..., description="The issue this page belongs to.")
    series_id: str = Field(..., description="The series this page belongs to.")
    page_number: int = Field(..., description="The page number in reading order, 1-based.")
    rows: list[list[PanelRef]] = Field(default_factory=list, description="The page grid: a list of rows, each row a list of 1-3 panels placed left to right.")

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
