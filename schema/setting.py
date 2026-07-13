from typing import Optional
from pydantic import BaseModel, Field


class AssetOrigin(BaseModel):
    """
    Provenance stamp for an asset imported from another series' collection.
    Records where the copy came from so drift can later be detected and, when
    storage becomes canonical, copies can be reconciled into links.
    """
    series_id: str = Field(..., description="The series the asset was imported from.")
    asset_id: str = Field(..., description="The id of the source asset in its home series.")
    imported_at: str = Field(..., description="ISO timestamp of the import.")


class Prop(BaseModel):
    """
    A prop that dresses a setting (or appears in a scene).   Described in enough
    detail that it can be drawn consistently whenever the setting appears.
    """
    name: str = Field(..., description="A short (1-4 word) name for the prop, e.g. 'brass telescope'")
    description: str = Field(..., description="A visual description of the prop detailed enough for consistent depiction: size, materials, colors, wear, and where it usually sits in the setting.")


class SettingShot(BaseModel):
    """
    A reusable named SHOT of a setting — the establishing master re-framed at a
    new angle and/or time of day (e.g. 'wide · dawn', 'gate · night', 'low angle
    · dusk').   Built FROM the master so the place stays consistent, but it keeps
    its own style-keyed art so any scene can pick it, exactly like a character's
    base look plus its variant looks.
    """
    shot_id: str = Field(..., description="A slug id for the shot, e.g. 'wide-dawn'.  Usually the name lowercased with non-word runs dashed.")
    name: str = Field(..., description="A short display name for the shot, e.g. 'wide · dawn' or 'gate at night'.")
    angle: str = Field("", description="The camera/framing of the shot, e.g. 'wide establishing', 'low angle at the gate', 'reverse over the counter', 'tight on the doorway'.  Default empty.")
    time_of_day: str = Field("", description="The light/time of the shot, e.g. 'dawn', 'high noon', 'golden hour', 'dusk', 'night'.  Default empty.")
    description: str = Field("", description="Any extra direction for the shot (weather, mood, what's changed).  Default empty.")
    images: dict[str, str] = Field(default_factory=dict, description="Rendered shot art keyed like the master ('<style>' landscape, '<style>/orientation' otherwise).  Default empty dict.")
    images_stale: list[str] = Field(default_factory=list, description="Shot keys whose art predates the latest master or shot edit — re-render to clear.  Default empty list.")


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
    origin: Optional[AssetOrigin] = Field(None, description="Provenance if this setting was imported from another series' collection.  Default to None.")
    images: dict[str, str] = Field(default_factory=dict, description="Master backgrounds keyed by style (landscape) or 'style_id/orientation' (portrait, square): maps the key to the rendered background's filepath.  Default to empty dict.")
    images_stale: list[str] = Field(default_factory=list, description="Master keys whose art predates the latest setting/prop edit — re-render to clear.  Default to empty list.")
    shots: list[SettingShot] = Field(default_factory=list, description="Reusable named shots of this setting (angle + time of day), each re-framed from the master and pickable by any scene.  Default to empty list.")

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
