import os
from gui.elements import view_all_instances
from gui.state import APPState
from models.series import Series
from models.publisher import Publisher
from style.comic import ComicStyle
        

def view_all_styles(state: APPState):
    from gui.messaging import new_item_messager
    with state.details:
        new_item_messager(state, "STYLES", "I would like to create a new comic book style.")
        view_all_instances(
            state=state,
            get_instances=ComicStyle.read_all,
            kind="style",
            aspect_ratio="1/1")
        
def view_all_publishers(state: APPState):
    from gui.messaging import new_item_messager
    with state.details:
        new_item_messager(state, "PUBLISHERS", "I would like to create a new comic book publisher.")
        view_all_instances(
            state=state,
            get_instances=Publisher.read_all,
            kind="publisher",
            aspect_ratio="1/1")
        
def view_all_series(state: APPState):
    from gui.messaging import new_item_messager
    with state.details:
        new_item_messager(state, "SERIES", "I would like to create a new comic book series.")
        view_all_instances(
            state=state,
            get_instances=Series.read_all,
            kind="series",
            aspect_ratio="16/27")