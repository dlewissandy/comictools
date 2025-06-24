import os
from pydantic import BaseModel, Field
from helpers.constants import DATA_FOLDER
from helpers.generator import invoke_generate_image_api
from helpers.file import generate_unique_id
from helpers.image import IMAGE_QUALITY

class Publisher(BaseModel):
    id: str | None = Field(None, description="The unique identifier for the publisher.  This is usually the publisher name in lowercase with spaces replaced by dashes.  defaults to null")
    name: str = Field(..., description="The name of the publisher")
    description: str | None = Field(..., description="A description of the publisher.  defaults to null")
    logo: str | None = Field(..., description="A description of the logo of the publisher.  defaults to null")
    image: str | None = Field(None, description="The selected image for the logo")

    def path(self) -> str:
        """
        return the path to the publisher model
        """
        return os.path.join(DATA_FOLDER, "publishers", self.id)

    def filepath(self) -> str:
        """
        return the filepath to the publisher model
        """
        return os.path.join(self.path(), "publisher.json")
    
    def image_path(self) -> str:
        """
        return the path to the images for the publisher
        """
        return os.path.join(self.path(), "images")

    def image_filepath(self) -> str | None:
        """
        return the filepath to the image
        """
        if self.image is None or self.image == "":
            return None
        return os.path.join(self.path(), "images", f"{self.image}.jpg")
        
    def render(self):
        """
        render the logo for the publisher on success, returns the id of the generated image.
        """
        if self.logo is None or self.logo =="":
            return None
        
        prompt = f"""Generate a rendering of the logo for {self.id.replace("-"," ").title()} using the following information:\n
        
        {self.logo}

        # Guidelines
        * The image must have a square (1:1) aspect ratio.
        * The logo should be on a neutral background.
        * The logo should be easily recognizable, and not too complex.
        """
        id = self.id.replace(" ", "-").lower()
        raw_image = invoke_generate_image_api(prompt, n=1, size="1024x1024", quality=IMAGE_QUALITY.HIGH)
        savepath = os.path.join(self.path(), "images")
        image_id = generate_unique_id(savepath, create_folder=False)
        savefilepath = os.path.join(savepath,f"{image_id}.jpg")
        if self.image is None or self.image == "":
            self.image = image_id
            self.write()
        with open(savefilepath, "wb") as f:
            f.write(raw_image.getbuffer())
        return image_id
    
    def format(self, heading_level: int = 1) -> str:
        """
        format the publisher model for display
        """
        heading = "#" * heading_level
        output = f"{heading} Publisher\n"
        output += f"* **Name:** {self.name}\n"
        if self.description:
            output += f"* ** Description ** {self.description}\n"
        if self.logo:
            output += f"* **Logo:** {self.logo}\n"
        return output