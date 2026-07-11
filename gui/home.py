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
            get_instances=lambda: storage.read_all_objects(ComicStyle),
            kind="style",
            aspect_ratio="1/1")
        
def view_all_publishers(state: APPState):
    from gui.elements import PagePacker, caption_action, CrudButtonKind as _CK
    from gui.messaging import post_user_message
    storage: GenericStorage = state.storage
    with state.details:
        packer = PagePacker(12)
        with ui.element('div').classes('comic-mosaic w-full q-mt-md'):
            view_all_instances(
                state=state,
                get_image_locator=lambda publisher: publisher.image,
                get_instances=lambda: storage.read_all_objects(Publisher),
                kind="publisher",
                aspect_ratio="1/1",
                packer=packer, variants=[(2, 2)],
                overlap_caption=lambda: caption_action("Publishers", _CK.CREATE,
                    lambda _: post_user_message(state, "I would like to create a new comic book publisher."), 3))
        
def view_all_series(state: APPState):
    from gui.messaging import new_item_messager
    storage: GenericStorage = state.storage
    with state.details:
        new_item_messager(state, "SERIES", "I would like to create a new comic book series.")
        view_all_instances(
            state=state,
            get_image_locator=lambda x: storage.find_series_image(series_id=x.series_id),
            get_instances=lambda: storage.read_all_objects(Series),
            kind="series",
            aspect_ratio="16/27")