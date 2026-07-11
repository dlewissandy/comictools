from typing import Optional
from pydantic import BaseModel, Field
from schema.setting import AssetOrigin


class PropAsset(BaseModel):
    """
    A prop as a first-class studio asset: a thing that can dress a setting, be
    carried by a character variant, or appear in a panel — reusable everywhere,
    with its own reference art per style.
    """
    prop_id: str = Field(..., description="A unique identifier for the prop.  Usually the name in lowercase with dashes.")
    series_id: str = Field(..., description="The series that owns this prop.")
    name: str = Field(..., description="A short (1-4 word) name, e.g. 'cracked crystal ball'.")
    description: str = Field(..., description="A visual description detailed enough for consistent depiction: size, materials, colors, wear.")
    images: dict[str, str] = Field(default_factory=dict, description="Style-keyed reference art: maps style_id to the rendered reference image.  Default to empty dict.")
    origin: Optional[AssetOrigin] = Field(None, description="Provenance if imported from another series.  Default to None.")

    @property
    def primary_key(self) -> dict[str, str]:
        return {"prop_id": self.prop_id, "series_id": self.series_id}

    @property
    def parent_key(self) -> dict[str, str]:
        return {"series_id": self.series_id}

    @property
    def id(self) -> str:
        return self.prop_id


class Outfit(BaseModel):
    """
    Wardrobe as a first-class studio asset: an attire description with its own
    reference art, wearable by any character variant and reusable across series.
    """
    outfit_id: str = Field(..., description="A unique identifier for the outfit.  Usually the name in lowercase with dashes.")
    series_id: str = Field(..., description="The series that owns this outfit.")
    name: str = Field(..., description="A short (1-4 word) name, e.g. 'gnome disguise', 'Sunday best'.")
    description: str = Field(..., description="1-2 paragraphs describing the attire: garments, materials, colors, condition, accessories.")
    images: dict[str, str] = Field(default_factory=dict, description="Style-keyed reference art: maps style_id to the rendered reference image.  Default to empty dict.")
    origin: Optional[AssetOrigin] = Field(None, description="Provenance if imported from another series.  Default to None.")

    @property
    def primary_key(self) -> dict[str, str]:
        return {"outfit_id": self.outfit_id, "series_id": self.series_id}

    @property
    def parent_key(self) -> dict[str, str]:
        return {"series_id": self.series_id}

    @property
    def id(self) -> str:
        return self.outfit_id
