from enum import StrEnum
from pydantic import BaseModel, Field
from style.comic import ComicStyle
from models.issue import Issue
from models.character import CharacterModel
from models.series import Series

    
if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()

    from style.comic import ComicStyle

    style = ComicStyle.read(id="stained-glass")
    style.render_art_style()