import os
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field
from helpers.generator import invoke_generate_api, invoke_generate_image_api
from helpers.constants import CHARACTERS_FOLDER, COMICS_FOLDER
from helpers.file import generate_unique_id, get_folder_contents, subfolders
from helpers.image import IMAGE_QUALITY

from style.comic import ComicStyle


class CharacterModel(BaseModel):
    # Note: The character name:variant is used as the key in the characters dictionary and must be unique
    id: str = Field(..., description="A unique identifier for the character/variant.  e.g. '<name>/<variant>'")
    series: str = Field(..., description="The comic book series (title) that the character belongs to.  Default to empty string")
    description: str = Field(..., description="A 1-2 sentence description of the character.  This should be sufficient to distinguish the character from others.")
    name: str = Field(..., description="The name of the character")
    variant: str | None = Field(None, description="The variant of the character. E.g 'young', 'armored', etc.")
    race: str = Field(..., description="The race of the character.  Default to 'human'")
    gender: str = Field(..., description="The gender of the character")
    attire: str = Field(..., description="What the character is wearing")
    behavior: str  = Field(..., description="Notes on the The character's behavior")
    appearance: str  = Field(..., description="Notes on the The character's appearance")
    image: Optional[dict[str,str]]  = Field(None, description="A dictionary of style to character image filepath.  default to None")

    def path(self) -> str:
        """
        return the path to the character model
        """
        # Normalize the id:
        if self.variant is None or self.variant == "":
            variant = "base"
        else:
            variant = self.variant
        return f"{COMICS_FOLDER}/{self.series.lower().replace(' ', '-')}/characters/{self.name.lower().replace(' ', '-')}/{variant.lower().replace(' ', '-')}"
    
    def filepath(self) -> str:
        """
        return the filepath to the character model
        """
        return f"{self.path()}/character.json"


    @classmethod
    def generate(cls, series: str, name: str, description: str, variant: str = ""):
        """
        generate new character model (potentially based on prior character model) using generative AI
        """
        logger.info(f"name: {name}, description: {description}, variant: {variant}")
        if variant is None or variant == "":
            variant = "base"
        id =  os.path.join(name,variant).lower().replace(" ", "-")
        # verify that the variant does not exist
        path = f"{COMICS_FOLDER}/{series}/characters/{id}"
        if os.path.exists(path):
            logger.warning(f"Character model {id} already exists.  Returning existing model.")
            return cls.read(name=name, variant=variant,series=series)
        
        # Read the base character model in, if it exists.
        base = None
        if variant != "base":
            base = CharacterModel.read(name=name, series=series, variant=None)

        prompt = f"""Generate a character description for the comic book character {name} from the following description:

        # Character
        {description}

        """.strip()
        if base is not None:
            prompt += f"""
            # Base Character
            This is a character model is a variation ({variant}) of the following character model:

            {base.format()}

            Note that the new character model may differ in attire, attributes, and behavior, but should be
            consistent with the base character model.

            """.strip()
    
        prompt += """
            Focus on visual details, including the attire, accessories,
            physical features, coloration etc, that would help a comic book artist to draw the character.
            Do not include information about style so that the artist can use this description in different
            styles or genres.  
            Be as concise as possible -- the summary should be in enough detail to allow the artist to draw
            the character consistently, but no more than that.
        """

        response = invoke_generate_api(prompt, text_format=cls)
        
        response.id = id
        response.series = series
        response.name = name
        response.variant = variant
        response.write()
        return response

    def write(self):
        """
        write the character model to a file
        """
        # create the directory if it doesn't exist
        variant = self.variant
        if self.variant is None or self.variant == "":
            variant = "base"
        # Normalize the id:
        self.id =  os.path.join(self.name,variant).lower().replace(" ", "-")
        # Verify folder exists
        os.makedirs(self.path(), exist_ok=True)
        # write the character model to a file
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read(cls,  series: str, variant: str | None = None, id: str | None = None, name: str | None = None) -> Optional["CharacterModel"]:
        """
        read the character model from a file.  If the charater model does not exist, then
        return None.
        """
        if id is None and name is None:
            logger.error("Either id or name must be specified")
            return None
        if variant is None or variant == "":
            # if the variant is not specified, then use the id as the variant
            variant = "base"
        # read the character model from a file
        if id is None:
            id = os.path.join(name,variant).lower().replace(" ", "-")
        filepath = f"{COMICS_FOLDER}/{series}/characters/{id}/character.json"
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)

    def format(self):
        """
        format the character model for display
        """
        result = f"""
        # Character Model
* **Name**: {self.name}
* **Race**: {self.race}
* **Gender**: {self.gender}
* **Description**: {self.description}
* **Attire**: {self.attire}
        """.strip()
        if self.behavior is not None and self.behavior != "":
            result += f"\n* **Behavior**: {self.behavior}"
        if self.appearance is not None and self.appearance != "":
            result += f"\n* **Appearance**: {self.appearance}"
        return result

    def render(self, style: ComicStyle):
        """
        render the character model using generative AI
        """

        prompt = f"""Generate a multi-angle character model of {self.name} using the following information:\n
        
        {style.format(include_bubble_styles=False)}

        {self.format()}

        # Guidelines
        * The image must have a landscape aspect ratio.
        * First row (75% of the image height), THREE poses of the character model:
          - front view
          - side view
          - back view
        * Maintain a neutral stance with neutral background, and ensure the character is fully visible in each pose without clipping
        * Second row (25% of image height) from left to right:
           - Face closeup view - joy
           - Face closeup view - anger
           - Face closeup view - fear
           - face closeup view - sadness
           - face closeup view - surprise
           - THE IMAGE LABEL: "{self.name}"
        * The facial closeup images should be BELOW the character model images, and should not overlap with the character model images.
        * ensure consistent appearance (color, accessories, clothing, weapons, physical features, etc) across all views.  Pay special attention to the facial closeup images,
           ensuring that the characters facial features (eyes, eye color, ears, teeth/tusks, hair, mouth, nose, etc) are consistent across all images.
        """
        variant = self.variant
        if variant is None or variant == "":
            variant = "base"
        raw_image = invoke_generate_image_api(prompt, n=1, size="1536x1024", quality=IMAGE_QUALITY.HIGH)
        savepath = f"{CHARACTERS_FOLDER}/{self.id}/{style.id}"
        image_id = generate_unique_id(savepath, create_folder=False)
        savefilepath = f"{savepath}/{image_id}.jpg"
        with open(savefilepath, "wb") as f:
            f.write(raw_image.getbuffer())
        if style.id not in self.image:
            self.image[style.id] = image_id
            self.write()
        return raw_image

    def set_image(self, image_id: str, style_id: str):
        """
        select the image for the character model
        """
        # verify that the file exists
        variant = self.variant
        if self.variant is None or self.variant == "":
            variant = "base"
        filepath = f"{CHARACTERS_FOLDER}/{self.id}/{variant}/{style_id}/{image_id}.jpg"
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Image {filepath} not found")
        # set the image
        self.image[style_id] = image_id
        self.write()

    def reset_image(self, style: str):
        """
        reset the image for the character model
        """
        # if the key exists, then delete it
        if style in self.image:
            del self.image[style]
            self.write()

    def images(self,style_id: str) -> list[str]:
        """
        return the list of images for the character model and given style
        """
        variant = self.variant
        if self.variant is None or self.variant == "":
            variant = "base"
        return get_folder_contents(f"{CHARACTERS_FOLDER}/{self.id}/{variant}/{style_id}")
    
    def styles(self) -> list[str]:
        """
        return the list of styles for which the character model has images
        """
        # Get all the non-hidden subfolders in the character model folder
        variant = self.variant
        if self.variant is None or self.variant == "":
            variant = "base"
        return subfolders(f"{CHARACTERS_FOLDER}/{self.id}/{variant}")
        

    @classmethod
    def fromImage(cls, name: str, variant: str | None, imagepaths: list[str] | str):
        """
        create a character model from an image or list of images
        """
        prompt = """
        Generate a character model of {self.name} using the provided images.  Focus
        on visual details, including the attire, accessories, tattoos, physical features, coloration etc,
        that would help a comic book artist to draw the character."""
        id = f"{name}/{variant}".lower().replace(" ", "-")
        # verify that the variant does not exist
        if os.path.exists(f"{CHARACTERS_FOLDER}/{id}"):
            logger.warning(f"Character model {id} already exists.  Returning existing model.")
            return cls.read(name, variant)
        if isinstance(imagepaths, str):
            imagepaths = [imagepaths]
        # Invoke the OpenAI API to generate a character description
        response = invoke_generate_api(prompt, images=imagepaths, text_format=cls)
        response.id = f"{name}/{variant}".lower().replace(" ", "-")
        response.name = name
        response.variant = variant
        response.write()
        return response
    
    def generate_variant(self, prompt, variant: str):
        """
        generate a new character model based on the current character model
        """
        # Invoke the OpenAI API to generate a character description
        if self.variant is not None and self.variant != "":
            # Raise an error! can only generate a variant from the base character model
            raise ValueError(f"Cannot generate a variant from a variant character model ({self.variant})")
        return self.generate(name=self.name, description=prompt, variant=variant, base=self)
    
    def revise(self, feedback: str):
        prompt = f"""
    Revise the comic book character for {self.name} to reflect the author's feedback

    # Character
    {self.format()}

    # Feedback
    {feedback}

    Focus on visual details, including the attire, accessories,
    physical features, coloration etc, that would help a comic book artist to draw the character consistently.
    Do not include information about style so that the artist can use this description in different
    Be as concise as possible -- the summary should be in enough detail to allow the artist to draw
    the character consistently, but no more than that.
        """.strip()
        # Invoke the OpenAI API to generate a character description
        response = invoke_generate_api(prompt, text_format=CharacterModel)

        self.description = response.description
        self.race = response.race
        self.gender = response.gender
        self.attire = response.attire
        self.behavior = response.behavior
        self.appearance = response.appearance
        self.write()
        return self