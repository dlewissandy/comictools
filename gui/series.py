import os
from schema import Series, Issue, CharacterModel, Publisher, Setting, PropAsset, Outfit
from gui.elements import (
    header, view_all_instances, markdown_field_editor, crud_button, post_user_message, CrudButtonKind)
from nicegui import ui
from gui.state import APPState
from storage.generic import GenericStorage
from gui.selection import SelectionItem

def view_series(state: APPState):

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

        # Description callout — a text panel takes only the size its text needs.
        desc = series.description or ""
        desc_rows = max(2, min(6, 1 + (len(desc) + 269) // 270))
        with packer.place_cell([(10, desc_rows)], fudge=False):
            with ui.card().classes(TAILWIND_CARD + ' mosaic-card').style('overflow-y: auto;'):
                markdown_field_editor(state, "Description", series.description)

        # THE ISSUES HANG ON THE STUDIO WALL — the series room keeps only
        # what the series OWNS: its masthead and its reusable assets.

        # A cardwall for viewing and adding characters to the comic series.
        # THE MASTHEAD IS JUST ANOTHER ASSET (the author's ruling): the
        # FIRST tile in the assets list — no special title-art interface.
        # The tile opens the mark board that actually HOLDS the art (the
        # newest take wins); a bare series offers the issues' style.
        from schema import ArtBoard
        def _board_takes(b):
            return [i for i in storage.list_images(b) if os.path.exists(i)]
        _mboards = [(b, _board_takes(b)) for b in storage.read_all_objects(
            ArtBoard, primary_key={"scope_id": series.series_id})
            if b.board_kind == 'masthead']
        _inked = [(b, t) for b, t in _mboards if t]
        titled = {sid: img for sid, img in (getattr(series, 'title_images', {}) or {}).items()
                  if img and os.path.exists(img)}
        if _inked:
            _mb, _mtakes = max(_inked, key=lambda bt: max(os.path.getmtime(i) for i in bt[1]))
            mast_style = _mb.style_id or 'vintage-four-color'
            mast_img = (_mb.image if (_mb.image and os.path.exists(_mb.image))
                        else max(_mtakes, key=os.path.getmtime))
        else:
            issue_styles = [i.style_id for i in storage.read_all_objects(
                Issue, primary_key={"series_id": series.series_id}, order_by="issue_number")
                if i.style_id]
            mast_style = next((s for s in issue_styles if s in titled), None) \
                or (issue_styles[0] if issue_styles else None) \
                or next(iter(titled), None) or 'vintage-four-color'
            mast_img = titled.get(mast_style) or next(iter(titled.values()), None)
        _st = storage.read_object(ComicStyle, primary_key={"style_id": mast_style})
        if _st is None:
            from types import SimpleNamespace
            _st = SimpleNamespace(style_id=mast_style,
                                  name=mast_style.replace('-', ' '))
        with packer.place_cell([(3, 2)], fudge=False):
            with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative cursor-pointer'
                                   + ('' if mast_img else ' ghost-card')) as mcard:
                ui.label('Masthead').classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                if mast_img:
                    ui.image(source=mast_img).props('fit=contain')
                else:
                    with ui.column().classes('absolute inset-0 items-center justify-center'):
                        ui.label('bare — letter it on the mark bench') \
                            .classes('text-xs text-gray-500')
            mcard.tooltip('The series wordmark — open the mark bench '
                          '(from text, a dropped image, or a rough)')
            mcard.on('click', lambda _: open_mark_bench(_st))

        # (the 'redraw the cast in one hand' door is shelved until house
        # artists land — the author's call; it returns with that feature)
        characters = storage.read_all_objects(CharacterModel, primary_key={"series_id": series.series_id})
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
        