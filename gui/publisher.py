import os
from loguru import logger
from typing import BinaryIO
from nicegui import ui
from gui.elements import header, crud_button, markdown_field_editor, full_width_image_selector_grid, view_all_instances, view_attributes, Attribute, CrudButtonKind
from gui.messaging import post_user_message
from gui.state import APPState
from storage.generic import GenericStorage
from schema import Publisher, Series


def view_publisher(state: APPState):
    """
    View the details of a publisher.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    storage = state.storage
    logger.debug("view_publisher")
    selection = state.selection
    publisher_id = selection[-1].id
    publisher = storage.read_object(Publisher, primary_key={"publisher_id": publisher_id}) if publisher_id else None
    details = state.details

    # MOUNT-ALL: every house is visible at once — the selection's trail
    # already scoped state.storage to this publisher's own house, so a
    # miss here is a genuine not-found, never a mount problem
    if publisher is None:
        details.clear()
        header(f"Publisher {publisher_id} not found", 0)
        return
    
    def set_image(image_id: str):
        """
        Set the image for the publisher.
        
        Args:
            image_id: The ID of the image to set.
        """
        publisher.image = image_id
        storage.update_object(data=publisher)

    def upload_image(name: str, data: BinaryIO, mime_type: str):
        """
        Upload an image for the publisher.
        
        Args:
            name: The name of the image.
            data: The binary data of the image.
            mime_type: The MIME type of the image.
        """
        # Create a new image in the storage
        file_locator = storage.upload_image(obj=publisher, name=name, data=data, mime_type=mime_type)
        # Set the image for the publisher
        publisher.image = file_locator
        storage.update_object(data=publisher)

    with details:
        # The title for the viewer is the Publisher name
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(publisher.name.title(), 0)
            ui.space()
            def retire_house(_=None):
                # deleting a publisher UN-REGISTERS its repo — the disk is
                # never touched; the house can always rejoin the rack
                from storage import registry
                slug = registry.house_of_publisher(publisher_id)
                house = next((h for h in registry.registered()
                              if h['slug'] == slug), None)
                if house is None:
                    post_user_message(state, "I would like to delete the current publisher.")
                    return
                from gui.elements import studio_dialog
                with studio_dialog('RETIRE THIS HOUSE?', min_w=440) as dlg:
                    ui.label(f"{publisher.name} leaves the rack.  Its repository stays "
                             f"untouched on disk at {house['path']} — nothing is deleted, "
                             f"and it can rejoin any time.").classes('text-sm q-mt-sm')
                    with ui.row().classes('w-full justify-end q-mt-sm').style('gap: 8px;'):
                        ui.button('Keep it').props('flat dense no-caps').on('click', lambda _: dlg.close())

                        def go():
                            registry.unregister(house['slug'])
                            dlg.close()
                            ui.notify(f"{publisher.name} retired — the repo stays at "
                                      f"{house['path']}.", type='info')
                            from gui.selection import SelectionItem, SelectedKind
                            state.change_selection(new=[SelectionItem(
                                name='Publishers', id=None, kind=SelectedKind.ALL_PUBLISHERS)])
                        ui.button('Retire the house', icon='logout').props('unelevated dense no-caps') \
                            .on('click', lambda _: go())
                dlg.open()
            crud_button(kind=CrudButtonKind.DELETE, action=retire_house, size=1)


        # Below that we have a full width row for editing the publisher's description
        # and a button to save the changes
        markdown_field_editor(state, "Description", publisher.description)

        # THE HOUSE ROOM IS THE HOUSE'S OWN THINGS — description, logo,
        # styles.  Its series hang on the studio wall (one home per door).
        from gui.elements import caption_action, CrudButtonKind as _CK
        from gui.elements import PagePacker

        # THE STYLE RACK: the house's styles — its OWN copies, edit them to
        # your heart's content.  Nothing outside this repo is ever used.
        def _new_style():
            from gui.create_asset import create_style_dialog
            create_style_dialog(state)
        from schema import ComicStyle
        style_packer = PagePacker(12)
        with ui.element('div').classes('mosaic-host'), ui.element('div').classes('comic-mosaic w-full'):
            view_all_instances(
                state=state,
                get_instances=lambda: storage.read_all_objects(ComicStyle, order_by="name"),
                get_image_locator=lambda st: st.image.get('art') if isinstance(st.image, dict) else None,
                kind="style",
                aspect_ratio="1/1",
                packer=style_packer, variants=[(3, 3)],
                # a style's art is abstract — its NAME must be readable
                # without hovering
                card_overlay=lambda st: ui.label(st.name.title())
                    .classes('caption-box caption-box-sm')
                    .style('position: absolute; bottom: 6px; left: 6px; z-index: 6;'),
                overlap_caption=lambda: caption_action("House Styles", _CK.CREATE,
                    lambda _: _new_style(), 3)
            )
            style_packer.finalize()

        # THE LOGO'S DOORS, like any asset: the current mark large with its
        # heal/rework tools, then describe (the pencil), render, or upload
        from gui.elements import art_tools

        def open_logo_bench(_=None):
            from schema import ArtBoard
            from gui.selection import SelectionItem, SelectedKind
            from schema.enums import FrameLayout
            bid = "logo"
            board = storage.read_object(cls=ArtBoard, primary_key={
                "scope_id": publisher_id, "board_id": bid})
            if board is None:
                board = ArtBoard(board_id=bid, scope_id=publisher_id,
                                 board_kind='logo',
                                 name=f"{publisher.name} logo",
                                 description=publisher.logo or
                                     f"The mark of the house “{publisher.name}”.",
                                 aspect=FrameLayout.SQUARE)
                storage.create_object(data=board, overwrite=True)
            state.change_selection(new=[*state.selection, SelectionItem(
                name=board.name, id=bid, kind=SelectedKind.ARTBOARD)])

        ui.button('Compose the logo on the light table', icon='layers') \
            .props('flat dense no-caps') \
            .tooltip('The mark bench: from text, from layers, or from a dropped image') \
            .on('click', open_logo_bench)

        if publisher.image and os.path.exists(publisher.image):
            with ui.card().classes('soft-card p-2 relative').style('max-width: 320px;'):
                ui.image(source=publisher.image).style('max-height: 160px;').props('fit=contain')
                art_tools(state, publisher.image,
                          on_reink=open_logo_bench,
                          reink_tip='Re-ink on the mark bench (text, image or rough)',
                          heal_name=f'the {publisher.name} logo')

        with view_attributes(
            state=state, 
            caption="Logo",
            attributes=[
                Attribute(caption="description", get_value=lambda: publisher.logo)
            ], 
            expanded=True, 
            individual_icons = False,
            header_size = 2
            ):

            # Below that we have a series of full width rows for selecting the
            # preferred image for the publisher's logo.
            full_width_image_selector_grid(
                state=state,
                image_kind_name="logo image",
                get_images=lambda: storage.list_images(publisher),
                get_selection=lambda : publisher.image,
                set_selection=set_image,
                upload_image=upload_image
            )        
                
def view_pick_publisher(state: APPState):
    """RETIRED: series never pick publishers (the repo IS the publisher)."""
    from gui.home import view_lobby
    return view_lobby(state)

