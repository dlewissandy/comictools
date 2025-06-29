from pydantic import BaseModel, Field

class SceneModel(BaseModel):
    """
    A scene is a collection of pannels that tell a story.   For example, a scene could be a page in a comic book.
    """
    scene_id: str = Field(..., description="The unique identifier of the scene.  This is the same as the title, but with spaces replaced by underscores.")
    issue_id: str = Field(..., description="The identifier of the issue comic book or project that this scene belongs to. default to empty string")
    series_id: str = Field(..., description="The identifier of the series that this scene belongs to. default to empty string")
    name: str = Field(..., description="A short title for the scene.   Default to a short (5 words or less) description of the scene'")
    story: str = Field(..., description="The story or narrative arc of the scene")
    style_id: str = Field(..., description="The art style of the scene.   Default to 'vintage-four-color'")

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

    def format(self, heading_level: int=1, no_panels: bool=False):
        """
        Format the scene for display
        """
        
        text = f"""
{'#' * heading_level} SCENE
* **id**: {self.scene_id}
* **story**: {self.story}
* **issue**: {self.issue_id}
* **style**: {self.style_id}
"""
        if not no_panels:
            text += f"""
{'#' * (heading_level +1)} PANELS
"""
            for i,panel in enumerate(self.read_panels()):
                text += f"""{'#' * (heading_level + 2)} PANEL {i}\n{panel.format()}\n"""
        return text