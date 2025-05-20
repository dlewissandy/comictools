import os
from style.comic import ComicStyle
from models.issue import Issue
from models.scene import SceneModel
from models.series import Series
from models.character import CharacterModel
from models.panel import RoughBoardModel, BeatBoardModel
from helpers.constants import COMICS_FOLDER, STYLES_FOLDER

def get_style_node(style: ComicStyle):
    return {
        "id": f"style:{style.id}",
        "key": style.id,
        "children": []
    }

def get_style_nodes():
    nodes = []
    for item in os.listdir(STYLES_FOLDER):
        style = ComicStyle.read(id=os.path.splitext(item)[0])
        if style:
            nodes.append(get_style_node(style))
    return nodes

def get_panel_node(panel: RoughBoardModel | BeatBoardModel):
    return {
        "key": panel.id,
        "id": f"panel:{panel.id}:{panel.scene}:{panel.issue}",
    }

def get_scene_node(scene: SceneModel):
    panels = scene.get_panels()
    return {
        "key": scene.id,
        "id": f"scene:{scene.id}:{scene.issue}",
        "children": [get_panel_node(panel) for panel in panels.values()]
    }

def get_scene_nodes(issue: Issue):
    scenes = issue.get_scenes()
    return [get_scene_node(scene) for scene in scenes]

def get_issue_nodes(series: Series):
    issues = series.get_issues()
    nodes = []
    for issue in issues.values():
        if issue.issue_title:
            key = f"{issue.issue_title} ({issue.issue_number})"
        else:
            key = f"issue {issue.issue_number}"
        nodes.append({
            "key": key,
            "id": f"issue:{issue.id}:{series.id}",
            "children": get_scene_nodes(issue)
        })
    return nodes

def get_character_nodes(series: Series):
    characters = series.get_characters()
    nodes = []
    for character in characters.values():
        nodes.append({
            "key": f"{character.name} ({character.variant})",
            "id": f"character:{character.id}:{series.id}",
        })
    return nodes


def get_series_node(series: Series):
    return {
        "key": series.series_title,
        "id": f"series:{series.id}",
        "children": [
            {"key": "characters", "id":f"all_characters:{series.id}", "children": get_character_nodes(series)},
            {"key": "issues", "id": f"all_issues:{series.id}", "children": get_issue_nodes(series)},
        ],
    }

def get_series_nodes():
    nodes = []
    for item in os.listdir(COMICS_FOLDER):
        series = Series.read(id=item)
        if series:
            nodes.append(get_series_node(series))
    return nodes


def get_nodes():
    return [
        {"key": "series", "children": get_series_nodes(), "id": "all_series"},
        {"key": "styles", "children": get_style_nodes(), "id": "all_styles"},
    ]
