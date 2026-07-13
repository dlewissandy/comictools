from typing import Optional
from pydantic import BaseModel, Field
from schema.character_reference import CharacterRef
from schema.setting import Prop
from schema.layout_feel import LayoutFeel

class SceneModel(BaseModel):
    """
    A scene is a collection of pannels that tell a story.   For example, a scene could be a page in a comic book.
    A scene has a setting (setting + time), a cast with wardrobe
    (character variants), props, and blocking notes describing how the characters move through the setting.
    """
    scene_id: str = Field(..., description="The unique identifier of the scene.  This is the same as the title, but with spaces replaced by underscores.")
    issue_id: str = Field(..., description="The identifier of the issue comic book or project that this scene belongs to. default to empty string")
    series_id: str = Field(..., description="The identifier of the series that this scene belongs to. default to empty string")
    name: str = Field(..., description="A short title for the scene.   Default to a short (5 words or less) description of the scene'")
    story: str = Field(..., description="The story or narrative arc of the scene")
    style_id: str = Field(..., description="The art style of the scene.   Default to 'vintage-four-color'")
    scene_number: int = Field(..., description="The scene number.   Default to 1")

    # PRODUCTION METADATA (all optional so pre-existing scenes still load)
    setting_id: Optional[str] = Field(None, description="The setting where this scene takes place.  Default to None.")
    setting_shot_id: Optional[str] = Field(None, description="Which named SHOT of the setting this scene uses (angle + time of day); None means the establishing master.  Default to None.")
    time_of_day: Optional[str] = Field(None, description="The time of day of the scene's setting, e.g. 'day', 'night', 'dusk'.  Default to None.")
    mood: Optional[str] = Field(None, description="The emotional tone and lighting mood of the scene, e.g. 'tense, low warm lamplight'.  Default to None.")
    cast: list[CharacterRef] = Field(default_factory=list, description="The characters appearing in this scene with the variant (wardrobe) they wear.  Default to empty list.")
    props: list[Prop] = Field(default_factory=list, description="Scene-specific props beyond the setting's standing props.  Default to empty list.")
    blocking: Optional[str] = Field(None, description="Blocking notes: how the characters are staged and move through the setting during the scene.  Default to None.")
    layout_feel: Optional[LayoutFeel] = Field(None, description="This scene's OVERRIDE of the book's page-flow feel (density/verticality/irregularity/variety); None means inherit the issue's feel.  Default None.")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the scene
        """
        return {
            "scene_id": self.scene_id,
            "issue_id": self.issue_id,
            "series_id": self.series_id,
        }
    
    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the scene
        """
        return {
            "issue_id": self.issue_id,
            "series_id": self.series_id,
        }
    
    @property
    def id(self) -> str:
        """
        return the id of the scene
        """
        return self.scene_id
