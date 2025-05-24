from loguru import logger
from nicegui import ui
from gui.elements import init_cardwall
from gui.state import GUIState
from gui.selection import SelectionItem, change_selection
from gui.elements import markdown, header, view_all_instances, image_field_editor
from style.comic import ComicStyle
from gui.constants import TAILWIND_CARD


# def style_selector(state: GUIState, cardwall, style_id):
#     """
#     Create a style selector card.
    
#     Args:
#         state: The GUI elements containing the details and selection.
#         cardwall: The cardwall UI element.
#         new_sel: The new selection item to be added.
#     """
#     selection = state.get("selection")
#     new_itm = SelectionItem(name=f"Style picker", id=style_id, kind='style-picker')
#     new_sel = [s for s in selection]+[new_itm]
#     with cardwall:
#         if style_id is not None and style_id != "":
#             style = ComicStyle.read(id=style_id)
#             if style is None:
#                 card = ui.card().classes(TAILWIND_CARD)
#                 with card:
#                     header("Not Yet Selected", 4)
#                 card.on('click', lambda _, new_sel=new_sel: change_selection(state, new=new_sel))
#                 return
#             image_filepath = style.image_filepath()
#             if image_filepath is None:
#                 card = ui.card().classes(TAILWIND_CARD)
#             else:
#                 card = ui.card().classes(TAILWIND_CARD)
#             with card:
#                 header(style.id.replace("-", " ").title(), 4)
#                 if image_filepath:
#                     ui.image(source=image_filepath).style('top-padding: 0; bottom-padding:0')  
#                 card.on('click', lambda _, new_sel=new_sel: change_selection(state, new=new_sel))
#             return
#         else:
#             msg = f"No style has been selected."
#             logger.error(msg)
#             card = ui.card().classes(TAILWIND_CARD)
#             with card:
#                 header("Not Yet Selected", 4)
#             new_itm = SelectionItem(name=new_itm.name, id=None, kind=new_itm.kind)
#             new_sel = [s for s in selection]+[new_itm]
#             card.on('click', lambda _, new_sel=new_sel: change_selection(state, new=new_sel))

def view_style(state: GUIState):
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
    logger.debug("view_pick_style")

    # Dereference the state to get the selection and details.
    selection = state.get("selection")
    parent_id = selection[-2].id
    parent_kind = selection[-2].kind
    if parent_kind == "issue":
        parent = Issue.read(id=parent_id)
    elif parent_kind == "scene":
        parent = SceneModel.read(id=parent_id, issue=selection[-3].id)
    
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