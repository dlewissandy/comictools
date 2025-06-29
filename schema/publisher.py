from pydantic import BaseModel, Field
from loguru import logger

class Publisher(BaseModel):
    publisher_id: str  = Field(None, description="The unique identifier for the publisher.  This is usually the publisher name in lowercase with spaces replaced by dashes.  defaults to null")
    name: str = Field(..., description="The name of the publisher")
    description: str | None = Field(..., description="A description of the publisher.  defaults to null")
    logo: str | None = Field(..., description="A description of the logo of the publisher.  defaults to null")
    image: str | None = Field(None, description="The selected image for the logo")

    @property
    def primary_key(self) -> dict[str, str]:
        """
        return the primary key for the publisher
        """
        return {
            "publisher_id": self.id,
        }

    @property
    def parent_key(self) -> dict[str, str]:
        """
        return the parent key for the publisher
        """
        return {}
    
    @property
    def id(self) -> str:
        """
        return the id of the publisher
        """
        return self.publisher_id

    # def render(self):
    #     """
    #     render the logo for the publisher on success, returns the id of the generated image.
    #     """
    #     if self.logo is None or self.logo =="":
    #         return None
        
    #     prompt = f"""Generate a rendering of the logo for {self.id.replace("-"," ").title()} using the following information:\n
        
    #     {self.logo}

    #     # Guidelines
    #     * The image must have a square (1:1) aspect ratio.
    #     * The logo should be on a neutral background.
    #     * The logo should be easily recognizable, and not too complex.
    #     """
    #     id = self.id.replace(" ", "-").lower()
    #     raw_image = invoke_generate_image_api(prompt, n=1, size="1024x1024", quality=IMAGE_QUALITY.HIGH)
    #     savepath = os.path.join(self.path(), "images")
    #     image_id = generate_unique_id(savepath, create_folder=False)
    #     savefilepath = os.path.join(savepath,f"{image_id}.jpg")
    #     if self.image is None or self.image == "":
    #         self.image = image_id
    #         self.write()
    #     with open(savefilepath, "wb") as f:
    #         f.write(raw_image.getbuffer())
    #     return image_id
    
    # def format(self, heading_level: int = 1) -> str:
    #     """
    #     format the publisher model for display
    #     """
    #     heading = "#" * heading_level
    #     output = f"{heading} Publisher\n"
    #     output += f"* **Name:** {self.name}\n"
    #     if self.description:
    #         output += f"* ** Description ** {self.description}\n"
    #     if self.logo:
    #         output += f"* **Logo:** {self.logo}\n"
    #     return output