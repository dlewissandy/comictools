from pydantic import BaseModel, Field


class Prop(BaseModel):
    """
    A prop that dresses a setting (or appears in a scene).   Described in enough
    detail that it can be drawn consistently whenever the setting appears.
    """
    name: str = Field(..., description="A short (1-4 word) name for the prop, e.g. 'brass telescope'")
    description: str = Field(..., description="A visual description of the prop detailed enough for consistent depiction: size, materials, colors, wear, and where it usually sits in the setting.")


class Setting(BaseModel):
    """
    A setting is a recurring place where scenes and panels take place.   It belongs to a
    series, is dressed with props, and can be rendered as a style-keyed master
    background that multiple panels share so the setting stays visually consistent.
    """
    setting_id: str = Field(..., description="A unique identifier for the setting.  This is usually the setting name in lowercase with spaces replaced by dashes.")
    series_id: str = Field(..., description="The identifier of the series that this setting belongs to.")
    name: str = Field(..., description="A short (1-5 word) name for the setting, e.g. 'The Rusty Nail Saloon'")
    description: str = Field(..., description="A detailed visual description of the setting: architecture, layout, lighting, mood, era, and palette.   Detailed enough that different artists would draw the same place.")
    interior: bool = Field(True, description="True for interior settings, False for exterior settings.")
    props: list[Prop] = Field(default_factory=list, description="The props that dress this setting.  Default to empty list.")
    images: dict[str, str] = Field(default_factory=dict, description="Style-keyed master backgrounds: maps style_id to the filepath of the rendered background for that style.  Default to empty dict.")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the setting
        """
        return {
            "setting_id": self.setting_id,
            "series_id": self.series_id,
        }

    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the setting
        """
        return {
            "series_id": self.series_id,
        }

    @property
    def id(self) -> str:
        """
        return the id of the setting
        """
        return self.setting_id
