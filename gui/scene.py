import os
from nicegui import ui
from gui.selection import SelectionItem, change_selection
from gui.cardwall import init_cardwall
from gui.markdown import markdown
from models.scene import SceneModel

def view_scene(breadcrumbs, details, chat_history, selection):
    """
    View the details of a scene.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
        selection: The current selection.
    """
    scene_id = selection[-1].id
    issue_id = selection[-2].id
    scene = SceneModel.read(issue=issue_id, id=scene_id)
    if scene is None:
        details.clear()
        message = f"Scene with ID {scene_id} not found in issue {issue_id}."
        with details:
            ui.markdown(message)
        return
    
    with details:
        markdown(scene.format(no_panels=True))
        ui.markdown("# Panels")
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
                    card.on('click', lambda _, new_sel=new_sel: change_selection(breadcrumbs, details, chat_history, selection, new=new_sel))

