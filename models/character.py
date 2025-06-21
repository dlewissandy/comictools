import os
from typing import Optional
from loguru import logger
from pydantic import BaseModel, Field
from helpers.generator import invoke_generate_api, invoke_generate_image_api
from helpers.constants import CHARACTERS_FOLDER, COMICS_FOLDER, DATA_FOLDER
from helpers.file import generate_unique_id, get_folder_contents, subfolders
from helpers.image import IMAGE_QUALITY

from style.comic import ComicStyle

def render_character_image(character_name: str, character_description: str, style_description: str, save_path: str):
    """
    generate an image of a character in the given style.

    Args:
        character_name (str): The name of the character.
        character_description (str): A description of the character.
        style_description (str): A description of the style.
        save_path (str): The path to save the image.

    Returns:
        str: The id of the generated image.
    """
    prompt = f"""
    Render a multi-angle character model of {character_name} using the following information:\n

    # Character Brief
    {character_description}

    # Artistic Style
    {style_description}

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
       - THE IMAGE LABEL: "{character_name}"
    * The facial closeup images should be BELOW the character model images, and should not overlap with the character model images.
    * ensure consistent appearance (color, accessories, clothing, weapons, physical features, etc) across all views.  Pay special attention to the facial closeup images,
       ensuring that the characters facial features (eyes, eye color, ears, teeth/tusks, hair, mouth, nose, etc) are consistent across all images.
    """
    
    logger.debug(f"Generating character image with prompt: {prompt}")
    raw_image = invoke_generate_image_api(prompt, n=1, size="1536x1024", quality=IMAGE_QUALITY.HIGH)
    logger.debug(f"Image generation complete.  Generating unique id for image.")
    image_id = generate_unique_id(save_path, create_folder=False)
    logger.debug(f"Unique id generated: {image_id}.  Saving image to {save_path}/{image_id}.jpg")
    save_filepath = f"{save_path}/{image_id}.jpg"
    with open(save_filepath, "wb") as f:
        f.write(raw_image.getbuffer())
    logger.debug(f"Image saved to {save_filepath} with id {image_id}")
    return image_id

class CharacterModel(BaseModel):
    # Note: The character name:variant is used as the key in the characters dictionary and must be unique
    series: str = Field(..., description="The comic book series (title) that the character belongs to.  Default to empty string")
    description: str = Field(..., description="A 1-2 sentence description of the character.  This should be sufficient to distinguish the character from others.")
    name: str = Field(..., description="The name of the character")
    
    @property
    def id(self) -> str:
        """
        return the id of the character
        """
        return self.name.lower().replace(" ", "-")

    def path(self) -> str:
        """
        return the path to the character model
        """
        return f"{COMICS_FOLDER}/{self.series.lower().replace(' ', '-')}/characters/{self.id}"
    
    def filepath(self) -> str:
        """
        return the filepath to the character model
        """
        return f"{self.path()}/character.json"
    
    @property
    def variant_ids(self) -> list[str]:
        """
        return the list of variant ids for the character model
        """
        # Get all the non-hidden subfolders in the character model folder
        return subfolders(self.path())

    @property
    def variants(self) -> list["CharacterVariant"]:
        """
        return the list of variants for the character model
        """
        result = []
        base_variant = self.get_variant("base")
        for variant_id in self.variant_ids:
            variant = CharacterVariant.read(series=self.series, character=self.id, id=variant_id)
            if variant is not None and variant.id != "base":
                result.append(variant)
        

        # sort the variants by name, but keep the base variant first
        result.sort(key=lambda x: x.lower().name)
        if base_variant is not None:
            result.insert(0, base_variant)

        return result

    def image_filepath(self):
        """
        return the filepath to the representative image for the character model
        """
        logger.trace("character.image_filepath() called")
        # Get the base variant
        variants = self.variants
        while len(variants) > 0:
            variant = variants.pop()
            filepath = variant.image_filepath()
            if filepath is not None:
                return filepath
        # If no image is found, return None
        return None

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

        prompt = f"""
        Generate a character description for the comic book character {name} from the 
        breif and style below.   Your description needs to be in sufficient detail
        to allow different comic book artist to draw the character recognizably and consistently.
        Do not paraphrase or eliminate important visual detials from given brief -- Assume that
        any visual details given are key to the character's identity.

        # Character Brief
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
            Do not include information about artistic style so that the artist can use this description in different
            styles or genres.  
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
        os.makedirs(self.path(), exist_ok=True)
        # write the character model to a file
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read(cls,  series: str, id: str | None = None, name: str | None = None) -> Optional["CharacterModel"]:
        """
        read the character model from a file.  If the charater model does not exist, then
        return None.
        """
        if id is None and name is None:
            logger.error("Either id or name must be specified")
            return None
        series = series.lower().replace(" ", "-")
        # read the character model from a file
        if id is None:
            id = os.path.join(name).lower().replace(" ", "-")
        filepath = f"{COMICS_FOLDER}/{series}/characters/{id}/character.json"
        if not os.path.exists(filepath):
            logger.warning(f"Character model {id} not found in {filepath}. Returning None.")
            return None
        logger.debug(f"Reading character model from {filepath}")
        with open(filepath, "r") as f:
            data = f.read()
            return cls.model_validate_json(data)

    def format(self):
        """
        format the character model for display
        """
        result = f"""# Character Model ({self.name})
* **Name**: {self.name}
* **Description**: {self.description}
        """.strip()
        return result

    def get_variant(self, variant_id: str) -> Optional["CharacterVariant"]:
        """
        return the variant of the character model with the given id
        """
        # Normalize the id:
        if variant_id is None or variant_id == "":
            variant_id = "base"
        variant_id = variant_id.lower().replace(" ", "-")
        return CharacterVariant.read(series=self.series, character=self.id, id=variant_id)
    
    
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
    
    def delete(self):
        """
        delete the character model and all its variants
        """
        # Delete the character model folder
        import shutil
        path = self.path()
        if os.path.exists(path):
            logger.info(f"Deleting character model {self.name} at {path}")
            shutil.rmtree(path)
    
class StyledImage(BaseModel):
    style_id: str = Field(..., description="The id of the style for which this image is generated.  e.g. 'vintage-four-color'")
    series_id: str = Field(..., description="The id of the comic book series for which this image is generated.  e.g. 'spiderman'")
    character_id: str = Field(..., description="The id of the character for which this image is generated.  e.g. 'spiderman'")
    variant_id: str = Field(..., description="The id of the character variant for which this image is generated.  e.g. 'base' or 'young'")
    image_id: str = Field(..., description="The id of the image.  This is a unique identifier for the image.")  

    @property
    def id(self) -> str:
        """
        return the id of the styled image
        """
        # Normalize the id:
        return self.style_id

    @property
    def name(self) -> str:
        """
        return the name of the styled image
        """
        return self.style_id.replace("-", " ").title() 
    
    def image_path(self) -> str:
        """
        return the path to the styled image
        """
        return os.path.join(COMICS_FOLDER, self.series_id.lower().replace(" ", "-"), "characters", self.character_id.lower().replace(" ", "-"), self.variant_id.lower().replace(" ", "-"), "images", self.style_id.replace(" ", "-").lower())
    
    def image_filepath(self) -> str:
        """
        return the filepath to the styled image
        """
        return os.path.join(self.image_path(), f"{self.image_id}.jpg")
    
    def set_image(self, image_id: str):
        """
        set the image for the styled image
        """
        # verify that the file exists
        self.image_id = image_id
        variant = CharacterVariant.read(series=self.series_id, character=self.character_id, id=self.variant_id)
        if variant is None:
            raise ValueError(f"Variant {self.variant_id} for character {self.character_id} in series {self.series_id} not found.")
        variant.images[self.style_id] = self.image_id
        variant.write()

class CharacterVariant(BaseModel):
    series: str = Field(..., description="The comic book series (title) that the character belongs to.  Default to empty string")
    character: str = Field(..., description="The identifier of the character for which this is a variant.  e.g. '<name>'")
    description: str = Field(..., description="A 3-5 sentence description of the character.  This should be sufficient to distinguish the character from others.")
    name: str = Field(None, description="The variant of the variant. E.g 'young', 'armored', etc.")
    race: str = Field(..., description="The race of the character.  Default to 'human'")
    gender: str = Field(..., description="The gender of the character")
    age: str = Field(..., description="The age of the character.  Default to 'adult'")
    height: str = Field(..., description="The height of the character.  Default to 'average'")
    attire: str = Field(..., description="What the character is wearing")
    behavior: str  = Field(..., description="Notes on the The character's behavior")
    appearance: str  = Field(..., description="Notes on the The character's physical appearance and attributes")
    images: dict[str,str] = Field(None, description="The reference images that can be used by artists to draw this character.   defaults to empty dict")

    @property
    def id(self) -> str:
        """
        return the id of the character variant
        """
        # Normalize the id:
        return self.name.lower().replace(" ", "-")

    def path(self) -> str:
        """
        The path to where the character variant is stored
        """
        return f"{COMICS_FOLDER}/{self.series.lower().replace(' ', '-')}/characters/{self.character.lower().replace(' ', '-')}/{self.id}"
    
    def filepath(self) -> str:
        """
        return the filepath to the character model
        """
        return f"{self.path()}/variant.json"

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

        prompt = f"""
        Generate a character description for the comic book character {name} from the 
        breif and style below.   Your description needs to be in sufficient detail
        to allow different comic book artist to draw the character recognizably and consistently.
        Do not paraphrase or eliminate important visual detials from given brief -- Assume that
        any visual details given are key to the character's identity.

        # Character Brief
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
            Do not include information about artistic style so that the artist can use this description in different
            styles or genres.  
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
        # Verify folder exists
        os.makedirs(self.path(), exist_ok=True)
        # write the character model to a file
        with open(self.filepath(), "w") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def read(cls,  series: str, character: str, id: str | None = None, name: str | None = None) -> Optional["CharacterModel"]:
        """
        read the character model from a file.  If the charater model does not exist, then
        return None.
        """
        character_id = character.lower().replace(" ", "-")
        series_id = series.lower().replace(" ", "-")
        
        if id is None and name is None:
            logger.error("Either id or name must be specified")
            return None
        
        variant_id = id.lower().replace(" ", "-") if id else None
        # read the character model from a file
        if id is None:
            id = name.lower().replace(" ", "-")
        filepath = f"{COMICS_FOLDER}/{series_id}/characters/{character_id}/{variant_id}/variant.json"
        logger.debug(f"Reading character variant from {filepath}")
        if not os.path.exists(filepath):
            logger.warning(f"Character variant {id} not found in {filepath}. Returning None.")
            return None
        with open(filepath, "r") as f:
            data = f.read()
            logger.debug(f"Character variant data read from {filepath}: {data}")
            return cls.model_validate_json(data)

    @classmethod
    def read_all(cls, series: str, character: str) -> list["CharacterVariant"]:
        """
        read all character variants for the given series and character
        """
        character_id = character.lower().replace(" ", "-")
        series_id = series.lower().replace(" ", "-")
        path = f"{COMICS_FOLDER}/{series_id}/characters/{character_id}"
        subfolders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f)) and not f.startswith('.')]
        
        variants = []
        for variant_dir in subfolders:
            variant_id = variant_dir.lower().replace(" ", "-")
            variant = cls.read(series=series_id, character=character_id, id=variant_id)
            if variant is not None:
                variants.append(variant)
            else:
                logger.warning(f"Variant {variant_id} for character {character} in series {series} not found.")
        return variants

    def format(self, heading_level: int = 2) -> str:
        """
        format the character model for display
        """
        result = f"""{'#'*heading_level} Character Model ({self.name})
* **Name**: {self.name}
* **Race**: {self.race}
* **Age**: {self.age}
* **Height**: {self.height}
* **Gender**: {self.gender}
* **Description**: {self.description}
* **Attire**: {self.attire}
        """.strip()
        if self.appearance is not None and self.appearance != "":
            result += f"\n* **Appearance**: {self.appearance}"
        if self.behavior is not None and self.behavior != "":
            result += f"\n* **Behavior**: {self.behavior}"
        return result

    def render(self, style: ComicStyle):
        """
        render the character model using generative AI
        """

        style_description = style.format(include_bubble_styles=False)
        character_description = self.format()
        character_name = self.name
        if self.variant is not None and self.variant != "":
            character_name += f" ({self.variant})"
        savepath = f"{CHARACTERS_FOLDER}/{self.id}/{style.id}"
        image_id = render_character_image(character_name, character_description, style_description, savepath)
        if style.id not in self.image:
            self.image[style.id] = image_id
            self.write()
        return "success"

    def image_filepath(self, style_id: str | None = None ) -> Optional[str]:
        """
        return the filepath to the representative image for the character model
        """
        if style_id is None or style_id == "":
            # We are going to try to find an image using any of the styles
            styles = self.images.keys()
            sorted_styles = sorted(styles, key=lambda x: x.lower())
            for style in sorted_styles:
                image = self.images.get(style, None)
                if image is not None:
                    filepath = os.path.join(self.path(), "images", style, f"{image}.jpg")
                    if os.path.exists(filepath):
                        return filepath
            logger.warning(f"No image found for character model {self.character}({self.name}).")
        else:
            # A style was specified, so we will try to find the image for that style

            image = self.images.get(style_id, None)
            if image is None:
                logger.warning(f"No image found for style {style_id} in character model {self.character}({self.name}).")
                return None
            filepath = os.path.join(self.path(),"images",style_id, f"{image}.jpg")
            if not os.path.exists(filepath):
                logger.warning(f"Image {filepath} does not exist.")
                return None
            return os.path.join(self.path(), "images", style_id, f"{image}.jpg")
        


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

    # def images(self,style_id: str) -> list[str]:
    #     """
    #     return the list of images for the character model and given style
    #     """
    #     variant = self.variant
    #     if self.variant is None or self.variant == "":
    #         variant = "base"
    #     return get_folder_contents(f"{CHARACTERS_FOLDER}/{self.id}/{variant}/{style_id}")
    
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
    
    def delete(self):
        """
        delete the character model and all its variants
        """
        # Delete the character model folder
        import shutil
        path = self.path()
        if os.path.exists(path):
            logger.info(f"Deleting character model {self.name} at {path}")
            shutil.rmtree(path)
        