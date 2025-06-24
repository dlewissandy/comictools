import os
from gui.elements import view_all_instances
from gui.state import APPState
from schema.series import Series
from schema.publisher import Publisher
from schema.style.comic import ComicStyle
from storage.generic import GenericStorage
        

def view_all_styles(state: APPState):
    from gui.messaging import new_item_messager
    storage: GenericStorage = state.storage
    with state.details:
        new_item_messager(state, "STYLES", "I would like to create a new comic book style.")
        view_all_instances(
            state=state,
            get_image_locator=lambda style: style.image.get('art', None) if style.image else None,
            get_instances=storage.read_all_styles,
            kind="style",
            aspect_ratio="1/1")
        
def view_all_publishers(state: APPState):
    from gui.messaging import new_item_messager
    storage: GenericStorage = state.storage
    with state.details:
        new_item_messager(state, "PUBLISHERS", "I would like to create a new comic book publisher.")
        view_all_instances(
            state=state,
            get_image_locator=lambda publisher: storage.find_publisher_image(publisher_id=publisher.id),
            get_instances=storage.read_all_publishers,
            kind="publisher",
            aspect_ratio="1/1")
        
def view_all_series(state: APPState):
    from gui.messaging import new_item_messager
    storage: GenericStorage = state.storage
    with state.details:
        new_item_messager(state, "SERIES", "I would like to create a new comic book series.")
        view_all_instances(
            state=state,
            get_image_locator=lambda x: storage.find_series_image(series_id=x.id),
            get_instances=storage.read_all_series,
            kind="series",
            aspect_ratio="16/27")