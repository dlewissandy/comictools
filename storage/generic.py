from typing import Optional, BinaryIO
from abc import ABC, abstractmethod
from dataclasses import dataclass
from schema import *

class GenericStorage(ABC):
    """
    Abstract base class for generic storage systems.
    """
    # -------------------------------------------------------------------------
    # Series CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_series(self, data: Series) -> str:
        """
        Create a new series record.  Return the identifier of the created series.
        """
        pass

    def find_series_image(self, series_id: str) -> Optional[str]:
        """
        Find an image for depicting a series.   This searches the issues for the
        first issue that has a representative image.   If no image is found, return None.
        
        Args:
            series_id: The identifier of the series.
        
        Returns:
            The image URL or path if found, otherwise None.
        """
        pass

    @abstractmethod
    def read_series(self, id:str) -> Optional[Series]:
        """
        Read a series by its identifier.
        """
        pass

    def read_all_series(self) -> list[Series]:
        """
        Read all series records.
        """
        pass
    
    @abstractmethod
    def update_series(self, data: Series) -> None:
        """
        Update an existing series record.
        """
        pass

    @abstractmethod
    def delete_series(self, id: str) -> Optional[Series]:
        """
        Delete a series by its identifier.   On success, return the deleted series.
        """
        pass

    @abstractmethod
    def find_series(self, name: str) -> Optional[Series]:
        """
        Find a series by its name.
        
        Args:
            name: The name (or title) of the series to find.
        
        Returns:
            The Series object if found, otherwise None.
        """
        pass

    @abstractmethod
    def get_series(self, series_id: str) -> Optional[Series]:
        """
        Find a series by its name.
        
        Args:
            name: The series_id of the series to find.
        
        Returns:
            The Series object if found, otherwise None.
        """
        pass

    # -------------------------------------------------------------------------
    # Issue CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_issue(self, series_id: str, data: Issue) -> str:
        pass

    @abstractmethod
    def find_issue(self, series_id: str, id: str) -> Optional[Issue]:
        pass

    def find_issues(self, series_id: str) -> list[Issue]:
        pass

    @abstractmethod
    def update_issue(self, data: Issue):
        pass

    @abstractmethod
    def delete_issue(self, series_id, issue_id):
        pass

    @abstractmethod
    def find_issue_style(self, series_id: str, id: str) -> Optional[ComicStyle]:
        """
        Read the style of an issue.
        """
        pass

    def find_issue_image(self, series_id: str, issue_id: str) -> Optional[str]:
        """
        Find an image for depicting an issue.   This searches the panels for the
        first panel that has a representative image.   If no image is found, return None.
        
        Args:
            series_id: The identifier of the series.
            issue_id: The identifier of the issue.
        
        Returns:
            The image URL or path if found, otherwise None.
        """
        pass

    # -------------------------------------------------------------------------
    # Cover CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_cover(self, cover_data):
        pass

    @abstractmethod
    def find_cover(self, series_id: str, issue_id: str, location: CoverLocation)  -> Optional[TitleBoardModel]:
        pass

    @abstractmethod
    def find_covers(self, series_id: str, issue_id: str) -> list[TitleBoardModel]:
        pass

    @abstractmethod
    def update_cover(self, data: TitleBoardModel):
        pass

    @abstractmethod
    def delete_cover(self, series_id: str, str, issue_id: str, location: CoverLocation) -> Optional[TitleBoardModel]:
        pass

    @abstractmethod
    def read_cover_images(self, cover_id):
        pass

    @abstractmethod
    def read_cover_style(self, cover_id):
        """
        Read the style of a cover.
        """
        pass

    @abstractmethod
    def read_cover_characters(self, cover_id):
        """
        Read all characters featured on a cover.
        """
        pass

    @abstractmethod
    def read_cover_reference_images(self, cover_id):
        """
        Read all reference images used for a cover.
        """
        pass

    @abstractmethod
    def find_cover_image(self, series_id: str, issue_id: str, location: CoverLocation) -> Optional[str]:
        """
        Find an image for depicting a cover.   This searches the cover images for the
        first image that has a representative image.   If no image is found, return None.
        
        Args:
            series_id: The identifier of the series.
            issue_id: The identifier of the issue.
            location: The location of the cover.
        
        Returns:
            The image URL or path if found, otherwise None.
        """
        pass

    def find_cover_reference_images(self, series_id: str, issue_id: str, location: CoverLocation) -> list[str]:
        """
        Find all reference image locators for depicting a cover.   This searches the cover reference images for the
        images that have a representative image.   If no images are found, return an empty list.
        
        Args:
            series_id: The identifier of the series.
            issue_id: The identifier of the issue.
            location: The location of the cover.
        
        Returns:
            A list of reference image URLs or paths if found, otherwise an empty list.
        """
        pass

    @abstractmethod
    def find_cover_images(self, series_id: str, issue_id: str, location: CoverLocation) -> list[str]:
        """
        Find all image locators for depicting a cover.   This searches the cover images for the
        images that have a representative image.   If no images are found, return an empty list.
        
        Args:
            series_id: The identifier of the series.
            issue_id: The identifier of the issue.
            location: The location of the cover.
        
        Returns:
            A list of image URLs or paths if found, otherwise an empty list.
        """
        pass

    # -------------------------------------------------------------------------
    # Character CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_character(self, character_data):
        pass

    @abstractmethod
    def find_character(self, series_id: str, character_id: str) -> Optional[CharacterModel]:
        pass

    def find_characters(self, series_id: str) -> list[CharacterModel]:
        pass

    @abstractmethod
    def update_character(self, data: CharacterModel):
        pass

    @abstractmethod
    def delete_character(self, series_id: str, character_id: str) -> Optional[CharacterModel]:
        pass
    
    # -------------------------------------------------------------------------
    # CharacterVariant CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_character_variant(self, data: CharacterVariant) -> str:
        pass

    @abstractmethod
    def update_character_variant(self, data: CharacterVariant):
        pass

    @abstractmethod
    def find_character_variant(self, character_id: str, series_id: str, variant_id: str) -> Optional[CharacterVariant]:
        """
        Read all variants of a character.
        """
        pass

    @abstractmethod
    def find_character_variants(self, character_id: str, series_id: str) -> list[CharacterVariant]:
        """
        Read all variants of a character.
        """
        pass


    @abstractmethod
    def delete_character_variant(self, variant_id):
        pass

    @abstractmethod
    def find_variant_image(self, series_id: str, character_id: str, variant_id: str) -> Optional[str]:
        """
        Find an image for depicting a character variant.   This searches the character variants for the
        first variant that has a representative image.   If no image is found, return None.
        
        Args:
            series_id: The identifier of the series.
            character_id: The identifier of the character.
            variant_id: The identifier of the character variant.
        
        Returns:
            The image URL or path if found, otherwise None.
        """
        pass

    # -------------------------------------------------------------------------
    # StyledImage Crud Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_styled_image(self, styled_image_data):
        pass

    @abstractmethod
    def find_styled_image(self, series_id: str, character_id: str, variant_id, style_id: str, name: str) -> Optional[StyledImage]:
        pass

    def find_styled_images(self, series_id: str, character_id: str, variant_id, style_id: str) -> list[StyledImage]:
        pass

    @abstractmethod
    def update_styled_image(self, styled_image_id, styled_image_data):
        pass

    @abstractmethod
    def delete_styled_image(self, styled_image_id):
        pass


    # -------------------------------------------------------------------------
    # Scene CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_scene(self, scene_data):
        pass

    @abstractmethod
    def find_scene(self, series_id: str, issue_id: str, scene_id: str) -> Optional[SceneModel]:
        pass

    def find_scenes(self, series_id: str, issue_id: str) -> list[SceneModel]:
        """
        Find all scenes in an issue.
        """
        pass

    @abstractmethod
    def update_scene(self, data: SceneModel):
        pass

    @abstractmethod
    def delete_scene(self, scene_id):
        pass

    @abstractmethod
    def read_scene_style(self, scene_id):
        """
        Read the style of a scene.
        """
        pass

    def find_scene_image(self, series_id: str, issue_id: str, scene_id: str) -> Optional[str]:
        """
        Find an image for depicting a scene.   This searches the panels for the
        first panel that has a representative image.   If no image is found, return None.
        
        Args:
            series_id: The identifier of the series.
            issue_id: The identifier of the issue.
            scene_id: The identifier of the scene.
        
        Returns:
            The image URL or path if found, otherwise None.
        """
        pass

    # -------------------------------------------------------------------------
    # Panel CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_panel(self, data):
        pass

    @abstractmethod
    def find_panel(self, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> Optional[Panel]:
        pass

    def find_panels(self, series_id: str, issue_id: str, scene_id: str) -> list[Panel]:
        pass

    @abstractmethod
    def update_panel(self, data: Panel):
        pass

    @abstractmethod
    def delete_panel(self, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> Optional[Panel]:
        pass

    @abstractmethod
    def find_panel_images(self, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> list[str]:
        """
        Find all image locators for depicting a panel.   This searches the panel images for the
        images that have a representative image.   If no images are found, return an empty list.
        
        Args:
            series_id: The identifier of the series.
            issue_id: The identifier of the issue.
            scene_id: The identifier of the scene.
            panel_id: The identifier of the panel.
        
        Returns:
            A list of image URLs or paths if found, otherwise an empty list.
        """
        pass

    @abstractmethod
    def find_panel_reference_images(self, series_id: str, issue_id: str, scene_id: str, panel_id: str) -> list[str]:
        """
        Find all reference image locators for depicting a panel.   This searches the panel reference images for the
        images that have a representative image.   If no images are found, return an empty list.
        
        Args:
            series_id: The identifier of the series.
            issue_id: The identifier of the issue.
            scene_id: The identifier of the scene.
            panel_id: The identifier of the panel.
        
        Returns:
            A list of reference image URLs or paths if found, otherwise an empty list.
        """
        pass

    # -------------------------------------------------------------------------
    # PanelCharacter CRUD Operations
    # -------------------------------------------------------------------------

    @abstractmethod
    def read_panel_character(self, panel_id):
        """
        Read the character featured in a panel.
        """
        pass

    @abstractmethod
    def read_panel_characters(self, panel_id):
        """
        Read all characters featured in a panel.
        """
        pass

    @abstractmethod
    def update_panel_character(self, panel_id, character_data):
        """
        Update the character featured in a panel.
        """
        pass

    @abstractmethod
    def delete_panel_character(self, panel_id):
        """
        Delete the character featured in a panel.
        """
        pass

    # -------------------------------------------------------------------------
    # Panel Reference images CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_panel_reference_image(self, panel_id, reference_image_data):
        """
        Create a reference image for a panel.
        """
        pass

    @abstractmethod
    def read_panel_reference_image(self, panel_id, reference_image_id):
        """
        Read a reference image for a panel.
        """
        pass
        
    @abstractmethod
    def read_panel_reference_images(self, panel_id):
        """
        Read all reference images for a panel.
        """
        pass

    @abstractmethod
    def update_panel_reference_image(self, panel_id, reference_image_id, reference_image_data):
        """
        Update a reference image for a panel.
        """
        pass

    @abstractmethod
    def delete_panel_reference_image(self, panel_id, reference_image_id):
        """
        Delete a reference image for a panel.
        """
        pass

    # -------------------------------------------------------------------------
    # Style CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_style(self, data: ComicStyle) -> str:
        """
        Create a new style.
        """
        pass

    @abstractmethod
    def read_style(self, id: str) -> Optional[ComicStyle]:
        """
        Read a style.
        """
        pass


    @abstractmethod
    def read_all_styles(self) -> list[ComicStyle]:
        """
        Read all styles.
        """
        pass

    @abstractmethod
    def update_style(self, data: ComicStyle) -> None:
        """
        Update a style.
        """
        pass

    @abstractmethod
    def delete_style(self, id: str) -> Optional[ComicStyle]:
        """
        Delete a style.
        """
        pass

    @abstractmethod
    def find_style(self, name: str) -> Optional[ComicStyle]:
        """
        Find a style by its name.
        
        Args:
            name: The name of the style to find.
        
        Returns:
            The ComicStyle object if found, otherwise None.
        """
        pass

    def find_style_image(self, style_id: str, example_type: str) -> Optional[str]:
        """
        Find an image for depicting a style.   This searches the style example images for the
        first image that has a representative image.   If no image is found, return None.
        
        Args:
            style_id: The identifier of the style.
        
        Returns:
            The image URL or path if found, otherwise None.
        """
        pass

    def find_style_images(self, style_id: str, example_type: str) -> list[str]:
        """
        Find all image locators for depicting a style.   This searches the style example images for the
        images that have a representative image.   If no images are found, return an empty list.
        
        Args:
            style_id: The identifier of the style.
        
        Returns:
            A list of image URLs or paths if found, otherwise an empty list.
        """
        pass

    # -------------------------------------------------------------------------
    # Style Example Image
    # -------------------------------------------------------------------------

    @abstractmethod
    def create_style_example_image(self, style_id, art_image_data):
        """
        Create a new art image for a style.
        """
        pass

    @abstractmethod
    def create_style_example_image(self, style_id, art_image_id):
        """
        Read an art image for a style.
        """
        pass

    @abstractmethod
    def create_style_example_image(self, style_id):
        """
        Read all art images for a style.
        """
        pass

    @abstractmethod
    def create_style_example_image(self, style_id, art_image_id, art_image_data):
        """
        Update an art image for a style.
        """
        pass

    @abstractmethod
    def create_style_example_image(self, style_id, art_image_id):
        """
        Delete an art image for a style.
        """
        pass


    # -------------------------------------------------------------------------
    # Publisher CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_publisher(self, data: Publisher):
        """
        Create a new publisher.
        """
        pass

    @abstractmethod
    def read_publisher(self, id: str) -> Optional[Publisher]:
        """
        Read a publisher.
        """
        pass

    @abstractmethod
    def read_all_publishers(self) -> list[Publisher]:
        """
        Read all publishers.
        """
        pass

    @abstractmethod
    def update_publisher(self, data: Publisher) -> None:
        """
        Update a publisher.
        """
        pass

    @abstractmethod
    def delete_publisher(self, id) -> Optional[Publisher]:
        """
        Delete a publisher.
        """
        pass

    @abstractmethod
    def find_publisher(self, name: str) -> Optional[Publisher]:
        """
        Find a publisher by its name.
        
        Args:
            name: The name of the publisher to find.
        
        Returns:
            The Publisher object if found, otherwise None.
        """
        pass

    def find_publisher_image(self, publisher_id: str) -> Optional[str]:
        """
        Find an image for depicting a publisher.   This searches the publisher images for the
        first image that has a representative image.   If no image is found, return None.
        
        Args:
            publisher_id: The identifier of the publisher.
        
        Returns:
            The image URL or path if found, otherwise None.
        """
        pass

    def find_publisher_images(self, publisher_id: str) -> list[str]:
        """
        Find all image locators for depicting a publisher.   This searches the publisher images for the
        images that have a representative image.   If no images are found, return an empty list.
        
        Args:
            publisher_id: The identifier of the publisher.
        
        Returns:
            A list of image URLs or paths if found, otherwise an empty list.
        """
        pass

    def upload_publisher_image(self, publisher_id: str, image_name: str, image_data: BinaryIO, mime_type: str) -> str:
        """
        Upload an image for a publisher.  Returns the locator of the uploaded image.
        
        Args:
            publisher_id: The identifier of the publisher.
            image_name: The name of the image.
            image_data: The binary data of the image.
            mime_type: The MIME type of the image.
        
        Returns:
            The locator of the uploaded image.
        """
        pass

    # -------------------------------------------------------------------------
    # Publisher Reference Images CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def create_publisher_reference_image(self, publisher_id, reference_image_data):
        """
        Create a reference image for a publisher.
        """
        pass

    @abstractmethod
    def read_publisher_reference_image(self, publisher_id, reference_image_id):
        """
        Read a reference image for a publisher.
        """
        pass

    @abstractmethod
    def read_publisher_reference_images(self, publisher_id):
        """
        Read all reference images for a publisher.
        """
        pass

    @abstractmethod
    def update_publisher_reference_image(self, publisher_id, reference_image_id, reference_image_data):
        """
        Update a reference image for a publisher.
        """
        pass

    @abstractmethod
    def delete_publisher_reference_image(self, publisher_id, reference_image_id):
        """
        Delete a reference image for a publisher.
        """
        pass


    # -------------------------------------------------------------------------
    # Reference Image CRUD Operations
    # -------------------------------------------------------------------------
    @abstractmethod
    def upload_cover_reference_image(self, series_id: str, issue_id: str, location: CoverLocation, name: str, data: BinaryIO, mime_type: str) -> str:
        """
        Upload a reference image for a cover.  Returns the locator of the uploaded image.
        """
        pass

    @abstractmethod
    def upload_cover_image(self, series_id: str, issue_id: str, location: CoverLocation, image_name: str, image_data: BinaryIO, mime_type: str) -> str:
        """
        Upload an image for a cover.  Returns the locator of the uploaded image.
        """
        pass
   
    @abstractmethod
    def upload_style_image(self, style_id: str, example_type: str, image_name: str, image_data: BinaryIO, mime_type: str) -> str:
        """
        Upload an image for a style.  Returns the locator of the uploaded image.
        """
        pass

    def upload_scene_reference_image(self, series_id: str, issue_id: str, scene_id: str, name: str, data: BinaryIO, mime_type: str) -> str:
        """
        Upload a reference image for a scene.  Returns the locator of the uploaded image.
        """
        pass

    def upload_panel_reference_image(self, series_id:str, issue_id:str, scene_id:str, panel_id:str, name:str, data:BinaryIO, mime_type:str) -> str:
        """
        Upload a reference image for a panel.  Returns the locator of the uploaded image.
        """
        pass

    def upload_styled_variant_image(series_id: str, character_id: str, variant_id: str, style_id: str, name: str, data: BinaryIO, mime_type: str) -> str:
        """
        Upload a styled image for a character variant.  Returns the locator of the uploaded image.
        """
        pass