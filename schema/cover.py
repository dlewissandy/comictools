from typing import Optional
from pydantic import BaseModel, Field
from schema.enums import CoverLocation, FrameLayout
from schema.character_reference import CharacterRef
from schema.reference_image import ReferenceImage

class TitleBoardModel(BaseModel):
    id: str = Field(..., description="A unique identifier for the panel.   Default '<location>-cover'")
    location: CoverLocation = Field(..., description="The location of the cover.  front, inside-front, inside-back or back.  Default to front")
    issue: str = Field(..., description="The parent issue of the panel.   Default to empty string")
    series: str = Field(..., description="The parent series of the panel.   Default to empty string")
    characters: list[CharacterRef]  = Field(..., description="The names of the characters in the panel")
    style: str = Field(..., description="The art style of the panel.  Default to 'vintage-4-color'")
    aspect: FrameLayout = Field(..., description="The aspect ratio of the panel.  landscape, portrait or square.  Default to portrait")
    reference_images: list[ReferenceImage] = Field(..., description="The reference images for the panel")
    foreground: str = Field(..., description="The foreground of the panel")
    background: str | None = Field(None, description="The background of the panel")
    image: str | None = Field(None, description="The selected image for this panel")

    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the title board model
        """
        return {
            "series_id": self.series,
            "issue_id": self.issue,
            "location": self.location.value
        }


#     def format(self, heading_level: int = 1) -> str:
#         """
#         format the panel model for display
#         """
#         text = f"""
# * **location**: {self.location}
# * **style**: {self.style}
# * **aspect**: {self.aspect}
# * **characters**:
# {"\n".join([f"  - {character}" for character in self.characters])}
# * **foreground**: {self.foreground}
# * **background**: {self.background}
# """
#         return text
    

#     def render(self) -> str:
#         """
#         Render the cover for the currently selected comic book issue.
        
#         Returns:
#             A string indicating the status of the rendering operation.
#         """
#         from schema.style.comic import ComicStyle      # Needed for style description
#         from schema.publisher import Publisher  # Needed for publisher logo
#         from schema.series import Series        # Needed for Series name
#         from schema.issue import Issue          # Needed for issue name, price, creative team, etc.
#         from schema.character import CharacterVariant # Needed for character models and images

#         # Read the style, issue, series and characters
#         try:
#             style = ComicStyle.read(id=self.style)  # Ensure the style is loaded
#             issue = Issue.read(id=self.issue, series_id=self.series)
#             series = Series.read(id=self.series)
#             characters = [CharacterVariant.read(series=self.series, character=char.character, id=char.variant) for char in self.characters]
#         except Exception as e:
#             logger.error(f"Error loading related models: {e}")
#             return f"Error rendering cover: {e}"
        
#         reference_image_filepaths = [ref.image_filepath() for ref in self.reference_images if ref.image_filepath() is not None]

#         # If any of them didn't load, then we need to return a warning
#         warnings = []
#         if style is None:
#             warnings.append(f"The style ({self.style}) does not exist.")
#         if issue is None:
#             warnings.append(f"The issue ({self.issue}) does not exist.")
#         if series is None:
#             warnings.append(f"The series ({self.series}) does not exist.")
#             publisher = None
#         else:
#             publisher = Publisher.read(id=series.publisher)
#             if publisher is None:
#                 warnings.append(f"The publisher ({series.publisher}) does not exist.")
#             if not publisher.image_filepath() is None:
#                 reference_image_filepaths.append(publisher.image_filepath()) 
#         for char, ref in zip(characters, self.characters):
#             if char is None:
#                 warnings.append(f"The character variant ({ref.character}/{ref.variant}) in series {self.series} does not exist.")
#             else:
#                 if char.image_filepath(self.style) is not None:
#                     reference_image_filepaths.append(char.image_filepath(self.style))
        
#         if publisher is None:
#             warnings.append(f"The publisher ({series.publisher}) does not exist.")

#         # Get the reference images
#         for ref in reference_image_filepaths:
#             if not os.path.exists(ref):
#                 warnings.append(f"Reference image {ref} does not exist.")

#         if len(warnings) > 0:
#             msg = f"errors encountered while rendering cover:\n {"\n".join(warnings)}"
#             logger.error(msg)
#             return msg
        
#         location_name = self.location.value.replace("_", " ").title()

#         character_information = ""
#         if len(characters) > 0:
#             for character in characters:
#                 character_information += character.format(heading_level=2) + "\n"
#         # If we got here, then we have all the information that we need to render the cover.
#         prompt = f"""
#         Create a comic book {location_name} cover.   The image should be have a {self.aspect.value} orientation/aspect ratio.


# # Series
# * ** Title **: "{series.name}".   This should appear prominently across the top of the cover.
# * ** Subtitle **: "{issue.name}".  This should appear in smaller font below the title.
# {'* ** Price **: ' + str(issue.price) +".   Place below subtitle on left." if issue.price else ""}
# {'* ** Issue Number **: ' + str(issue.issue_number) + ".   Place below subtitle on right." if issue.issue_number else ""}
# {'* ** Issue Date **: ' + issue.publication_date + ".   Place below issue number right in small font." if issue.publication_date else ""}
# {'* ** Artist **: ' + issue.artist + ".   Place in small font at bottom of image" if issue.artist else ""}
# {'* ** Writer **: ' + issue.writer + ".   Place in small font at bottom of image" if issue.writer else ""}
# {'* ** Colorist **: ' + issue.colorist + ".   Place in small font at bottom of image" if issue.colorist else ""}
# {'* ** Creative Minds **: ' + issue.creative_minds + ".   Place in small font at bottom of image" if issue.creative_minds else ""}


# {issue.format(heading_level=1)}

# # Publisher
# * ** Logo **: (PLACE IN SMALL SQUARE IN LOWER RIGHT CORNER) {publisher.logo} 

# # Characters
# {character_information}

# # Style
# {style.format(heading_level=1)}

# # Cover Design
# * ** Foreground **: {self.foreground}
# {'* ** Background **: ' + self.background if self.background else ""}
# """

#         from helpers.generator import invoke_edit_image_api, invoke_generate_image_api, decode_image_response
#         try:
#             if len(reference_image_filepaths) > 0:
#                 # We have to use the edit image API
#                 raw_image = invoke_edit_image_api(
#                     prompt=prompt,
#                     size=frame_layout_to_dims(self.aspect),
#                     reference_images=reference_image_filepaths,
#                 )
#             else:
#                 # We can use the generate image API
#                 raw_image = invoke_generate_image_api(
#                     prompt=prompt,
#                     size=frame_layout_to_dims(self.aspect)
#                 )
#         except Exception as e:
#             msg = f"Error generating cover image: {e}"
#             logger.error(msg)
#             return msg
        
#         # Write the image bytes to the image path
#         image_path = os.path.join(self.path(), "images")
#         image_id = generate_unique_id(image_path, create_folder = False)
#         image_filepath = os.path.join(self.image_path(), f"{image_id}.jpg")

#         with open(image_filepath, "wb") as f:
#             f.write(raw_image)
#         self.set_image(image_id)
#         self.write()
#         return f"Cover rendered successfully for issue {issue.name} at location {location_name}."
