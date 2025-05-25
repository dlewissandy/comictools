import os
from nicegui import ui
from gui.selection import SelectionItem, change_selection
from gui.elements import init_cardwall, view_all_instances
from gui.elements import markdown, image_field_editor
from models.scene import SceneModel


def view_scene(state):
    """
    View the details of a scene.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    from style.comic import ComicStyle
    details = state.get("details")
    selection = state.get("selection")
    scene_id = selection[-1].id
    issue_id = selection[-2].id
    scene = SceneModel.read(issue=issue_id, id=scene_id)
    if scene is None:
        details.clear()
        message = f"Scene with ID {scene_id} not found in issue {issue_id}."
        with details:
            ui.markdown(message)
        return
    
    style = ComicStyle.read(id=scene.style) if scene.style else None
    
    with details:
        with ui.row().classes('w-full flex-nowrap'):
            with ui.column().classes('w-3/4'):
                ui.markdown("# Story").style('margin-top: 0; padding-top: 0; bottom-margin: 0; padding-bottom: 0;')
                markdown(scene.story)
            with ui.column().classes('w-1/4'):
                ui.markdown(f"# Style").style('margin-top: 0; padding-top: 0; bottom-margin: 0; padding-bottom: 0;')
                cardwall = init_cardwall(1)
                image_field_editor(
                    state, "pick-style", "Style", 
                    lambda: style.name if style else None, 
                    lambda: style.id if style else None, 
                    lambda: style.image_filepath() if style else None
                )
                
        ui.markdown("# Panels").style('margin-top: 0; padding-top: 0; bottom-margin: 0; padding-bottom: 0;')
        panels = scene.get_panels()
        if not panels or panels == []:
            ui.markdown("No panels available for this scene.")
        else:
            with init_cardwall():
                for i,panel in enumerate(panels.values()):
                    image = None
                    if hasattr(panel, "image"):
                        image = getattr(panel, "image")
                        if image == "":
                            image == None
                    card = ui.card().classes('mb-2 p-2 bg-blue-100 break-inside-avoid')
                    with card:
                        if image is not None:
                            ui.image(source=os.path.join(scene.path, "panels", "images", f"image.py"))
                        else:
                            if isinstance(panel, str):
                                ui.markdown(f"## Panel {i+1}\n\n{panel}")
                            else:
                                markdown(f"## Panel {i+1}\n\n{panel.story}")
                    new_itm = SelectionItem(name=f"panel {i+1}", id=panel.id, kind='panel')
                    new_sel = [s for s in selection]+[new_itm]
                    card.on('click', lambda _, new_sel=new_sel: change_selection(state, new=new_sel))

