import os
from gui.selection import SelectedKind
from schema import *

SERIES_NOT_FOUND_MESSAGE = lambda series_id: f"Series with ID {series_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all series."
CHARACTER_NOT_FOUND_MESSAGE = lambda character_id: f"Character with ID {character_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all characters."
STYLE_NOT_FOUND_MESSAGE = lambda style_id: f"Style with ID {style_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all styles."
PUBLISHER_NOT_FOUND_MESSAGE = lambda publisher_id: f"Publisher with ID {publisher_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all publishers."
ISSUE_NOT_FOUND_MESSAGE = lambda issue_id: f"Issue with ID {issue_id} not found.   Perhaps the locator is misspelled or it has been deleted.   Try checking the list of all issues."

TOPOSORT_ORDER = [
    "publisher_id",
    "series_id",
    "issue_id",
    "location",
    "character_id",
    "variant_id",
    "scene_id",
    "panel_id",
    "style_id",
    "image_id",
    "relation"
]

BASE_PATH = "data"

PATH_TEMPLATES = {}
ROOT_PATH_TEMPLATES = {}
ROOT_PATH_TEMPLATES[SelectedKind.PUBLISHER.value] = os.path.join("{base_path}", "publishers")
PATH_TEMPLATES[SelectedKind.PUBLISHER.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.PUBLISHER.value], "{publisher_id}")
ROOT_PATH_TEMPLATES[SelectedKind.STYLE.value] = os.path.join("{base_path}", "styles")
PATH_TEMPLATES[SelectedKind.STYLE.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.STYLE.value], "{style_id}")
ROOT_PATH_TEMPLATES[SelectedKind.SERIES.value] = os.path.join("{base_path}", "series")
PATH_TEMPLATES[SelectedKind.SERIES.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.SERIES.value], "{series_id}")
ROOT_PATH_TEMPLATES[SelectedKind.CHARACTER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SERIES.value], "characters")
PATH_TEMPLATES[SelectedKind.CHARACTER.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.CHARACTER.value], "{character_id}")
ROOT_PATH_TEMPLATES[SelectedKind.VARIANT.value] = os.path.join(PATH_TEMPLATES[SelectedKind.CHARACTER.value], "variants")
PATH_TEMPLATES[SelectedKind.VARIANT.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.VARIANT.value], "{variant_id}")
ROOT_PATH_TEMPLATES[SelectedKind.ISSUE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SERIES.value], "issues")
PATH_TEMPLATES[SelectedKind.ISSUE.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.ISSUE.value], "{issue_id}")
ROOT_PATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.ISSUE.value], "covers")
PATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.COVER.value], "{location}")
ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.ISSUE.value], "scenes")
PATH_TEMPLATES[SelectedKind.SCENE.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value], "{scene_id}")
ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SCENE.value], "panels")
PATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value], "{panel_id}")

ROOT_PATH_TEMPLATES[ComicStyle.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.STYLE.value]
ROOT_PATH_TEMPLATES[Series.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.SERIES.value]
ROOT_PATH_TEMPLATES[Publisher.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
ROOT_PATH_TEMPLATES[CharacterModel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.CHARACTER.value]
ROOT_PATH_TEMPLATES[CharacterVariant.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.VARIANT.value]
ROOT_PATH_TEMPLATES[Issue.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.ISSUE.value]
ROOT_PATH_TEMPLATES[Cover.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.COVER.value]
ROOT_PATH_TEMPLATES[SceneModel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.SCENE.value]
ROOT_PATH_TEMPLATES[Panel.__name__] = ROOT_PATH_TEMPLATES[SelectedKind.PANEL.value]
PATH_TEMPLATES[ComicStyle.__name__] = PATH_TEMPLATES[SelectedKind.STYLE.value]
PATH_TEMPLATES[Series.__name__] = PATH_TEMPLATES[SelectedKind.SERIES.value]
PATH_TEMPLATES[Publisher.__name__] = PATH_TEMPLATES[SelectedKind.PUBLISHER.value]
PATH_TEMPLATES[CharacterModel.__name__] = PATH_TEMPLATES[SelectedKind.CHARACTER.value]
PATH_TEMPLATES[CharacterVariant.__name__] = PATH_TEMPLATES[SelectedKind.VARIANT.value]
PATH_TEMPLATES[Issue.__name__] = PATH_TEMPLATES[SelectedKind.ISSUE.value]
PATH_TEMPLATES[Cover.__name__] = PATH_TEMPLATES[SelectedKind.COVER.value]
PATH_TEMPLATES[SceneModel.__name__] = PATH_TEMPLATES[SelectedKind.SCENE.value]
PATH_TEMPLATES[Panel.__name__] = PATH_TEMPLATES[SelectedKind.PANEL.value]
PATH_TEMPLATES[StyledVariant.__name__] = os.path.join(BASE_PATH, "styled_images", "{image_id}")

FILEPATH_TEMPLATES = {}
FILEPATH_TEMPLATES[SelectedKind.PUBLISHER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.PUBLISHER.value], "publisher.json")
FILEPATH_TEMPLATES[SelectedKind.SERIES.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SERIES.value], "series.json")
FILEPATH_TEMPLATES[SelectedKind.STYLE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.STYLE.value], "style.json")
FILEPATH_TEMPLATES[SelectedKind.CHARACTER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.CHARACTER.value], "character.json")
FILEPATH_TEMPLATES[SelectedKind.VARIANT.value] = os.path.join(PATH_TEMPLATES[SelectedKind.VARIANT.value], "variant.json")
FILEPATH_TEMPLATES[SelectedKind.ISSUE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.ISSUE.value], "issue.json")
FILEPATH_TEMPLATES[SelectedKind.COVER.value] = os.path.join(PATH_TEMPLATES[SelectedKind.COVER.value], "cover.json")
FILEPATH_TEMPLATES[SelectedKind.SCENE.value] = os.path.join(PATH_TEMPLATES[SelectedKind.SCENE.value], "scene.json")
FILEPATH_TEMPLATES[SelectedKind.PANEL.value] = os.path.join(PATH_TEMPLATES[SelectedKind.PANEL.value], "panel.json")
FILEPATH_TEMPLATES[Publisher.__name__] = FILEPATH_TEMPLATES[SelectedKind.PUBLISHER.value]
FILEPATH_TEMPLATES[Series.__name__] = FILEPATH_TEMPLATES[SelectedKind.SERIES.value]
FILEPATH_TEMPLATES[ComicStyle.__name__] = FILEPATH_TEMPLATES[SelectedKind.STYLE.value]
FILEPATH_TEMPLATES[CharacterModel.__name__] = FILEPATH_TEMPLATES[SelectedKind.CHARACTER.value]
FILEPATH_TEMPLATES[CharacterVariant.__name__] = FILEPATH_TEMPLATES[SelectedKind.VARIANT.value]
FILEPATH_TEMPLATES[Issue.__name__] = FILEPATH_TEMPLATES[SelectedKind.ISSUE.value]
FILEPATH_TEMPLATES[Cover.__name__] = FILEPATH_TEMPLATES[SelectedKind.COVER.value]
FILEPATH_TEMPLATES[SceneModel.__name__] = FILEPATH_TEMPLATES[SelectedKind.SCENE.value]
FILEPATH_TEMPLATES[Panel.__name__] = FILEPATH_TEMPLATES[SelectedKind.PANEL.value]
