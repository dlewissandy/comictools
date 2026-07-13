from pydantic import BaseModel, Field


class LayoutFeel(BaseModel):
    """Four aesthetic dials on the page auto-flow.  Each is a float in [-1, 1];
    0 is neutral (the plain flow).  They steer only UNLOCKED panels — a locked
    panel is always honored — and the plain flow is exactly all-zero.
    """
    density: float = Field(0.0, ge=-1.0, le=1.0, description="Panels per page: -1 = a few big panels, +1 = many small ones.  Default 0.")
    verticality: float = Field(0.0, ge=-1.0, le=1.0, description="Orientation bias: -1 = wide/cinematic (landscape), +1 = tall/towering (portrait).  Default 0.")
    irregularity: float = Field(0.0, ge=-1.0, le=1.0, description="Rhythm: -1 = steady grid, +1 = dynamic (a big panel among small ones).  Default 0.")
    variety: float = Field(0.0, ge=-1.0, le=1.0, description="Restlessness: +1 = avoid repeating the previous page's layout.  Default 0.")

    def is_neutral(self) -> bool:
        return not (self.density or self.verticality or self.irregularity or self.variety)
