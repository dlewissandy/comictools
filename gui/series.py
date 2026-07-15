import os
from loguru import logger
from nicegui.events import UploadEventArguments
from schema import Series, Issue, CharacterModel, Publisher, Setting, PropAsset, Outfit
from gui.elements import (
    markdown, header, uploader_card, view_all_instances, markdown_field_editor, crud_button, post_user_message, view_attributes, CrudButtonKind)
from nicegui import ui
from gui.state import APPState
from storage.generic import GenericStorage
from gui.selection import SelectionItem, SelectedKind

def view_series(state: APPState):
    from gui.messaging import new_item_messager

    # Dereference the state to get the selection and detials.
    selection: list[SelectionItem] = state.selection
    storage: GenericStorage = state.storage
    series: Series = storage.read_object(cls=Series, primary_key={"series_id": selection[-1].id}) if selection else None


    details = state.details
    details.clear()

    # Create safe accessors for the publisher's name, id and image filepath.
    pub = None if series.publisher_id is None else storage.read_object(cls=Publisher, primary_key={"publisher_id": series.publisher_id})
    get_name = lambda i, x : None if pub is None else pub.name
    get_id = lambda : None if pub is None else pub.id
    get_image_filepath = lambda : None if pub is None else pub.image_filepath()

    def upload_and_ask(e: UploadEventArguments, request: str):
        """Save a dropped image into the series uploads and ask the coauthor
        to create the named asset from it."""
        images_path = os.path.join(series.path(), 'uploads')
        if not e.name:
            logger.error("No file name provided in upload event.")
        if not e.type.startswith('image/'):
            logger.error(f"Uploaded file is not an image: {e.type}")
            return
        save_filepath = os.path.join(images_path, e.name)
        os.makedirs(images_path, exist_ok=True)
        with open(save_filepath, 'wb') as f:
            f.write(e.content.read())
        logger.debug(f"Saved uploaded file to {save_filepath}")
        post_user_message(state, f"{request} using this image as a reference: ![image]({save_filepath})")


    
    # Render the controls
    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(series.name.title(), 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current series."),size=1)
            
        # THE PAGE: everything rules onto one 12-unit comic page.
        from gui.elements import comic_page, caption_action, CrudButtonKind as _CK, PagePacker
        from gui.constants import TAILWIND_CARD
        def _cap(text, msg):
            return lambda: caption_action(text, _CK.CREATE, lambda _, m=msg: post_user_message(state, m), 3)
        def _ink_cast():
            from gui.create_asset import ink_cast_dialog
            ink_cast_dialog(state, series.series_id)
        def _create_cap(text, asset_kind):
            # THE CREATE DOOR: three paths (describe / from an image / copy),
            # the same for every reusable asset
            from gui.create_asset import create_asset_dialog
            return lambda: caption_action(text, _CK.CREATE,
                lambda _, k=asset_kind: create_asset_dialog(state, series.series_id, k), 3)
        page = comic_page()
        page.__enter__()
        packer = PagePacker(12)
        mosaic = ui.element('div').classes('comic-mosaic cspan-12')
        mosaic.__enter__()

        # THE TITLE ART: the series masthead, hand-lettered per style — the
        # reference every cover's title lettering is held to.  Ghost cards
        # letter the styles the series' issues use but don't have art for.
        from schema import ComicStyle
        from gui.elements import HEADER_CLASSES

        def ink_title(st):
            # THE CONVERSATION IS THE MODAL: the lettering direction is
            # typed in the box; Enter sends it straight to the Letterer
            from agentic.tools.imaging import generate_series_title_art_body
            from helpers.render_queue import enqueue_renders
            prefix = f"Letter the {series.name} masthead in {st.name}: "

            def _go(direction, st=st):
                enqueue_renders(state, [(
                    f"title art — {series.name} in {st.name}",
                    lambda n=direction: generate_series_title_art_body(
                        state, series.series_id, st.style_id, n),
                )], role='the Letterer')
            state.user_input.value = prefix
            state._input_intercept = (prefix, _go, None)
            try:
                state.user_input.run_method('focus')
            except Exception:
                pass
            ui.notify("Describe the lettering — 'circus poster woodtype', 'drippy "
                      "horror letters'…  (Enter alone lets the style decide.)",
                      type='info', position='bottom', timeout=4000)

        def open_mark_bench(st):
            # FROM LAYERS: the mark composes on the light table — the same
            # bench as everything else (don't reinvent the wheel)
            from schema import ArtBoard
            from gui.selection import SelectedKind
            bid = f"masthead-{st.style_id}"
            board = storage.read_object(cls=ArtBoard, primary_key={
                "scope_id": series.series_id, "board_id": bid})
            if board is None:
                board = ArtBoard(board_id=bid, scope_id=series.series_id,
                                 board_kind='masthead',
                                 name=f"{series.name} masthead · {st.name}",
                                 description=f"The series title “{series.name}” as a wordmark.",
                                 style_id=st.style_id)
                storage.create_object(data=board, overwrite=True)
            state.change_selection(new=[*state.selection, SelectionItem(
                name=board.name, id=bid, kind=SelectedKind.ARTBOARD)])

        def masthead_from_image(st):
            # FROM A REFERENCE IMAGE: the wordmark you drop BECOMES the
            # masthead for that style — the same door every asset has
            from gui.elements import studio_dialog
            with studio_dialog(f'A wordmark for {st.name.title()}', min_w=420) as dlg:
                ui.label('Drop the lettering image — it becomes the masthead '
                         'this style holds covers to.').classes('text-sm q-mt-sm')

                def on_upload(e, st=st):
                    locator = storage.upload_image(obj=series, name=e.name,
                                                   data=e.content, mime_type=e.type)
                    fresh = storage.read_object(cls=Series,
                                                primary_key={"series_id": series.series_id}) or series
                    fresh.title_images = dict(fresh.title_images or {})
                    fresh.title_images[st.style_id] = locator
                    storage.update_object(fresh)
                    dlg.close()
                    from gui.light_table import table_receipt
                    table_receipt(state, f"🖼 the {st.name} masthead now wears your wordmark",
                                  bench='the series room')
                    state.refresh_details()
                ui.upload(on_upload=on_upload, auto_upload=True).props('accept=image/*') \
                    .classes('w-full q-mt-sm')
            dlg.open()

        titled = {sid: img for sid, img in (getattr(series, 'title_images', {}) or {}).items()
                  if img and os.path.exists(img)}
        used_styles = {i.style_id for i in storage.read_all_objects(Issue, primary_key={"series_id": series.series_id})
                       if i.style_id} | set(titled.keys())
        title_entries = [(st, titled.get(st.style_id))
                         for st in storage.read_all_objects(ComicStyle, order_by='name')
                         if st.style_id in used_styles]
        for ti, (st, timg) in enumerate(title_entries):
            with packer.place_cell([(3, 2), (4, 8/3), (6, 4)], fudge=False):
                with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative'
                                       + ('' if timg else ' ghost-card')):
                    if ti == 0:
                        with ui.element('div').classes('panel-caption'):
                            _cap("Title Art", "I would like new title art (the series masthead) for this series.")()
                    ui.label(st.name.title()).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                    if timg:
                        ui.image(source=timg).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                        from gui.elements import art_tools
                        art_tools(state, timg,
                                  on_reink=lambda st=st: ink_title(st),
                                  reink_tip='Re-letter the masthead — with fresh direction',
                                  heal_name=f'{series.name} masthead')
                        ui.button(icon='add_photo_alternate').props('flat round dense size=xs') \
                            .classes('absolute bottom-1 left-1 z-10 bg-white/70 dark:bg-black/50') \
                            .tooltip('Swap in a wordmark image instead') \
                            .on('click', lambda _, st=st: masthead_from_image(st))
                        ui.button(icon='layers').props('flat round dense size=xs') \
                            .classes('absolute bottom-1 left-8 z-10 bg-white/70 dark:bg-black/50') \
                            .tooltip('Compose this masthead in layers on the mark bench') \
                            .on('click', lambda _, st=st: open_mark_bench(st))
                    else:
                        art = st.image.get('art') if isinstance(st.image, dict) else st.image
                        if art and os.path.exists(art):
                            ui.image(source=art).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                        with ui.column().classes('absolute inset-0 items-center justify-center z-10') \
                                .style('gap: 6px;'):
                            ui.button(f'Letter it in {st.name.title()}', icon='brush') \
                                .props('unelevated dense no-caps size=sm') \
                                .tooltip('Describe the lettering — the Letterer inks it') \
                                .on('click', lambda _, st=st: ink_title(st))
                            ui.button('From a wordmark image', icon='add_photo_alternate') \
                                .props('flat dense no-caps size=sm') \
                                .tooltip('Drop lettering art — it becomes this masthead') \
                                .on('click', lambda _, st=st: masthead_from_image(st))
                            ui.button('Compose on the light table', icon='layers') \
                                .props('flat dense no-caps size=sm') \
                                .tooltip('Lay it out in layers on the mark bench') \
                                .on('click', lambda _, st=st: open_mark_bench(st))
        # Description callout — a text panel takes only the size its text needs.
        desc = series.description or ""
        desc_rows = max(2, min(6, 1 + (len(desc) + 269) // 270))
        with packer.place_cell([(10, desc_rows)], fudge=False):
            with ui.card().classes(TAILWIND_CARD + ' mosaic-card').style('overflow-y: auto;'):
                markdown_field_editor(state, "Description", series.description)

        # THE ISSUES HANG ON THE STUDIO WALL — the series room keeps only
        # what the series OWNS: its masthead and its reusable assets.

        # A cardwall for viewing and adding characters to the comic series.
        characters = storage.read_all_objects(CharacterModel, primary_key={"series_id": series.series_id})
        if len(characters) > 1:
            # ONE HAND FOR THE CAST: redraw every character in a single style
            # so they don't look drawn by different artists
            with packer.place_cell([(12, 1)], fudge=False):
                with ui.row().classes('w-full items-center').style('gap: 8px;'):
                    ui.label('Cast').classes('comic-label-sm')
                    ui.button('Redraw the cast in one hand', icon='brush') \
                        .props('flat dense no-caps') \
                        .tooltip('Re-ink every character in one style so the whole '
                                 'cast is drawn by a single artist') \
                        .on('click', lambda _: _ink_cast())
        if characters:
            with view_all_instances(
                state=state, 
                get_instances = lambda: characters, 
                get_image_locator=lambda x: storage.find_character_image(series_id=series.series_id, character_id=x.character_id),
                kind="character",
                aspect_ratio="6/5",
                get_name=lambda _,x: x.name,
                packer=packer, variants=[(3, 2)],
                overlap_caption=_create_cap("Characters", "character")
                ):
                pass
        from gui.create_asset import create_drop_card
        create_drop_card(state, series.series_id, "character",
            'Drop an image to create a character', packer=packer,
            overlap_caption=None if characters else _create_cap("Characters", "character"))

        # A cardwall for viewing and adding the recurring settings of the series.
        def setting_image(loc: Setting):
            # Show the first rendered master background, if any.
            return next((img for img in (loc.images or {}).values() if img and os.path.exists(img)), None)

        settings = storage.read_all_objects(Setting, primary_key={"series_id": series.series_id}, order_by="name")
        if settings:
            view_all_instances(
                state=state,
                get_instances=lambda: settings,
                get_image_locator=setting_image,
                kind="setting",
                aspect_ratio="3/2",
                get_name=lambda _, x: x.name,
                packer=packer, variants=[(3, 2), (6, 4)],
                overlap_caption=_create_cap("Settings", "setting")
                ).style('margin-top: 0px; margin-bottom: 0px')
        create_drop_card(state, series.series_id, "setting",
            'Drop an image to create a setting', packer=packer,
            overlap_caption=None if settings else _create_cap("Settings", "setting"))

        # Props and wardrobe: the reusable stuff panels are dressed with.
        def asset_image(a):
            return next((img for img in (a.images or {}).values() if img and os.path.exists(img)), None)

        def _strike_asset_overlay(deleter_tool, key_name):
            # ONE-CLICK REVERSIBLE STRIKE riding each asset card — the same
            # wastebasket-backed delete the detail page uses, but right here in
            # the roster so a junk prop/outfit never needs a trip inside.
            def overlay(asset):
                from gui.strike import strike
                _id = getattr(asset, key_name)
                ui.button(icon='delete_outline').props('flat round dense size=xs') \
                    .classes('absolute top-0 right-0 z-10') \
                    .style('background: rgba(255,255,255,.72);') \
                    .tooltip(f"Strike '{asset.name}' — it waits in the wastebasket") \
                    .on('click.stop', lambda _, a=asset: strike(
                        state, deleter_tool,
                        {"series_id": series.series_id, key_name: getattr(a, key_name)},
                        f"the '{a.name}' {'prop' if key_name == 'prop_id' else 'outfit'}"))
            return overlay

        props = storage.read_all_objects(PropAsset, primary_key={"series_id": series.series_id}, order_by="name")
        if props:
            from agentic.tools.assets import delete_prop
            view_all_instances(
                state=state,
                get_instances=lambda: props,
                get_image_locator=asset_image,
                kind="prop",
                aspect_ratio="3/2",
                get_name=lambda _, x: x.name,
                packer=packer, variants=[(3, 2)],
                overlap_caption=_create_cap("Props", "prop"),
                card_overlay=_strike_asset_overlay(delete_prop, "prop_id"),
                )
        create_drop_card(state, series.series_id, "prop",
            'Drop an image to create a prop', packer=packer,
            overlap_caption=None if props else _create_cap("Props", "prop"))

        outfits = storage.read_all_objects(Outfit, primary_key={"series_id": series.series_id}, order_by="name")
        if outfits:
            from agentic.tools.assets import delete_outfit
            view_all_instances(
                state=state,
                get_instances=lambda: outfits,
                get_image_locator=asset_image,
                kind="outfit",
                aspect_ratio="3/2",
                get_name=lambda _, x: x.name,
                packer=packer, variants=[(3, 2)],
                overlap_caption=_create_cap("Wardrobe", "outfit"),
                card_overlay=_strike_asset_overlay(delete_outfit, "outfit_id"),
                )
        create_drop_card(state, series.series_id, "outfit",
            'Drop an image to create wardrobe', packer=packer,
            overlap_caption=None if outfits else _create_cap("Wardrobe", "outfit"))
        packer.finalize()
        mosaic.__exit__(None, None, None)
        page.__exit__(None, None, None)
        