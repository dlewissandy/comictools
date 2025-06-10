from enum import StrEnum
from pydantic import BaseModel, Field
from style.comic import ComicStyle
from models.issue import Issue
from models.character import CharacterModel, render_character_image
from models.series import Series
from generators.constants import RUGOR_DESCRIPTION

    
if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()

    style = ComicStyle.read("stained-glass")
    if style is None:
        raise ValueError("Style not found")
    
    style_description = style.format(include_bubble_styles=False)
    character_description = RUGOR_DESCRIPTION
    save_path = "rugor"

    render_character_image(
        character_description=character_description,
        style_description=style_description,
        save_path=save_path,
        character_name="Rugor"
    )