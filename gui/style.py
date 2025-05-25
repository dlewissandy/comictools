from loguru import logger
from gui.elements import init_cardwall
from gui.state import GUIState
from gui.elements import markdown, header, view_all_instances
from style.comic import ComicStyle

def view_style(state: GUIState):
    """
    Editor for comic styles.
    """
    selection = state.get("selection")
    style = ComicStyle.read(id=selection[-1].id)
    details = state.get("details")
    with details:
        markdown(style.format())        
        init_cardwall()

def view_pick_style(state):
    """
    View the style picker.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    from models.series import Series
    from models.issue import Issue
    from models.scene import SceneModel
    from models.panel import TitleBoardModel,CoverLocation
    logger.debug("view_pick_style")

    # Dereference the state to get the selection and details.
    selection = state.get("selection")
    parent_id = selection[-2].id
    parent_kind = selection[-2].kind
    if parent_kind == "issue":
        parent = Issue.read(id=parent_id)
    elif parent_kind == "scene":
        parent = SceneModel.read(id=parent_id, issue=selection[-3].id)
    elif parent_kind == "front-cover":
        parent = TitleBoardModel.read(id=parent_id, location=CoverLocation.FRONT_COVER)
    elif parent_kind == "back-cover":
        parent = TitleBoardModel.read(id=parent_id, location=CoverLocation.BACK_COVER)
    elif parent_kind == "inside-front-cover":
        parent = TitleBoardModel.read(id=parent_id, location=CoverLocation.INSIDE_FRONT_COVER)
    elif parent_kind == "inside-back-cover":
        parent = TitleBoardModel.read(id=parent_id, location=CoverLocation.INSIDE_BACK_COVER)
    
    style_id = selection[-1].id
    style = ComicStyle.read(id=style_id) if style_id else None

    # Create a setter function for the publisher choice
    def set_style(style_id):
        if parent is not None:
            parent.style = style_id
            parent.write()

    with state.get("details"):
        header("Pick a Style", 1)
    view_all_instances(
        state=state,
        get_instances=style.read_all,
        kind="style",
        aspect_ratio="1/1",
        get_name=lambda x: x.name,
        get_choice=lambda : parent.style if parent else None,
        set_choice=set_style,
    )           