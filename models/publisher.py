import os
from pydantic import BaseModel, Field
from helpers.constants import DATA_FOLDER
from helpers.generator import invoke_generate_image_api
from helpers.file import generate_unique_id
from helpers.image import IMAGE_QUALITY

class Publisher(BaseModel):
    name: str = Field(..., description="The name of the publisher")
    description: str | None = Field(..., description="A description of the publisher.  defaults to null")
    logo: str | None = Field(..., description="A description of the logo of the publisher.  defaults to null")
    image: str | None = Field(None, description="The selected image for the logo")

    @property
    def id(self) -> str:
        """
        return the id of the publisher
        """
        return self.name.replace(" ", "-").lower()

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
    
    @classmethod
    def read(cls, id: str | None = None, name: str | None = None) -> "Publisher":
        """
        read the publisher model from a file
        """
        if not (id is None or name is None):
            raise ValueError("You must provide either id or name, not both.")
        if id is None and name is None:
            raise ValueError("You must provide an id or name.")
        if name is not None:
            id = name.replace(" ", "-").lower()
        filepath = os.path.join(DATA_FOLDER, "publishers", id, "publisher.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)
        
    def write(self):
        """
        write the publisher model to a file
        """
        # create the directory if it doesn't exist
        os.makedirs(self.path(), exist_ok=True)
        # write the publisher model to a file
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read_all(cls) -> list["Publisher"]:
        """
        read all publishers from the data folder
        """
        publishers = []
        for item in os.listdir(os.path.join(DATA_FOLDER, "publishers")):
            if item.startswith('.'):
                continue
            if os.path.isdir(os.path.join(DATA_FOLDER, "publishers", item)):
                # if it is a file then it is a publisher
                publisher = cls.read(id=item)
                if publisher:
                    publishers.append(publisher)
        return publishers

    def set_image(self, image: str):
        """
        set the image for the publisher
        """
        # Verify that the image exists
        if not os.path.exists(os.path.join(self.path(), "images", f"{image}.jpg")):
            raise ValueError(f"Image {image} does not exist.")
        
        self.image = image
        self.write()

    def all_images(self) -> list[str]:
        """
        return all images for the publisher
        """
        images = []
        images_path = os.path.join(self.path(), "images")
        if not os.path.exists(images_path):
            return images
        
        if os.path.isdir(images_path):
            for item in os.listdir(images_path):
                if item.endswith(".jpg") and not item.startswith('.'):
                    images.append(item[:-4])
        return images
    
    def delete(self):
        """
        delete the publisher model
        """
        from shutil import rmtree
        # delete the publisher directory and all its contents
        rmtree(self.path())

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