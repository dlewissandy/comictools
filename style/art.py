from pydantic import BaseModel, Field

class ArtStyle(BaseModel):
    """
    Art and ink stylistic guidelines for a comic series or title.
    """

    # Linework & Inking
    line_styles: str = Field(
        ...,
        description="A couple of sentences describing the line style used, including stroke thicknesses for outlines and detail lines, line variation, and line quality/texture."
    )
    inking_tools: str = Field(
        ...,
        description="Allowed inking instruments (e.g., 'brush', 'dip pen', 'digital'), specifying the tools for achieving the defined line style."
    )

    # Shading & Tones
    shading_style: str = Field(
        ...,
        description=(
            "Detailed shading parameters combining method (flat, crosshatch, halftone), overall density,"
            " and halftone specifics (dot size and density ranges) to guide tonal rendering."
        )
    )

    # Color
    color_palette: str = Field(
        ...,
        description="Describe the color palette used in the series’ main hues for characters, backgrounds, and props."
    )
    spot_colors: str = Field(
        ...,
        description="Describe any additional colors used for spot or special effects outside the main palette.  Default to empty string."
    )

    registration: str = Field(...,description="Describe the registration/alignment for color layers, including any specific tolerances or guidelines for color separation.")

    # Lettering & Text
    lettering_style: str = Field(
        ...,
        description="Describe the lettering and style, weight and size used for dialogue and captions to ensure text consistency."
    )

    def format(self):
        self_json = self.model_dump()
        result = "## Art Style\n  The art style defines the visual language of the medium, including linework.\n\n"
        for key, value in self_json.items():
            if value is None or value == "":
                continue
            result += f"* **{key.replace('_', ' ').capitalize()}**: {value}\n\n"
        return result
