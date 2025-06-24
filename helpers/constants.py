import os

DATA_FOLDER = "data"

# The shortest and longest side allowed for images passed to the OpenAI API
MAX_LONGEST_SIDE = 2000
MAX_SHORTEST_SIDE = 768

# Paths to the folders where the data is stored
CHARACTERS_FOLDER = os.path.join(DATA_FOLDER, "characters")
COMICS_FOLDER = os.path.join(DATA_FOLDER, "series")
PANELS_FOLDER = os.path.join(DATA_FOLDER, "panels")
SCENES_FOLDER = os.path.join(DATA_FOLDER, "scenes")
STYLES_FOLDER = os.path.join(DATA_FOLDER, "styles")

IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'bmp', "tiff", 'webp']


def STYLED_CHARACTER_IMAGES_FOLDER(character_id: str, style_id: str) -> str:
    """
    Get the path to the styled character images folder.
    """
    return os.path.join(CHARACTERS_FOLDER, character_id, style_id)

def STYLED_PANEL_IMAGES_FOLDER(comic_id: str, scene_id: str) -> str:
    """
    Get the path to the styled scene images folder.
    """
    return os.path.join(COMICS_FOLDER, comic_id, scene_id)

def STYLED_COMIC_IMAGES_FOLDER(comic_id: str, style_id: str) -> str:
    """
    Get the path to the styled comic images folder.
    """
    return os.path.join(COMICS_FOLDER, comic_id, style_id)