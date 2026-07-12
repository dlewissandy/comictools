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
        page = comic_page()
        page.__enter__()
        packer = PagePacker(12)
        mosaic = ui.element('div').classes('comic-mosaic cspan-12')
        mosaic.__enter__()

        # Description callout — a text panel takes only the size its text needs.
        desc = series.description or ""
        desc_rows = max(2, min(6, 1 + (len(desc) + 269) // 270))
        with packer.place_cell([(10, desc_rows)], fudge=False):
            with ui.card().classes(TAILWIND_CARD + ' mosaic-card').style('overflow-y: auto;'):
                markdown_field_editor(state, "Description", series.description)

        # Publisher logo — a square corner box, like the publisher mark on a cover.
        with packer.place_cell([(2, 2)], fudge=False):
            with ui.card().classes(TAILWIND_CARD + ' mosaic-card cursor-pointer') as pub_card:
                header("Publisher", 4)
                pub_image = pub.image if pub else None
                if pub_image and os.path.exists(pub_image):
                    ui.image(source=pub_image)
                else:
                    ui.label("Click to select").classes('text-gray-500').style('text-align: center;')
            pub_sel = state.selection + [SelectionItem(name="Pick Publisher", id=get_id(), kind=SelectedKind.PICK_PUBLISHER)]
            pub_card.on('click', lambda _, s=pub_sel: state.change_selection(new=s))

        # THE TITLE ART: the series masthead, hand-lettered per style — the
        # reference every cover's title lettering is held to.  Ghost cards
        # letter the styles the series' issues use but don't have art for.
        from schema import ComicStyle
        from gui.elements import HEADER_CLASSES

        def ink_title(st):
            # THE LETTERER TAKES DIRECTION: name the look before the render
            from agentic.tools.imaging import generate_series_title_art_body
            from helpers.render_queue import enqueue_renders
            with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 420px;'):
                ui.label(f'Letter the masthead in {st.name.title()}').classes('caption-box caption-box-sm')
                notes = ui.input(placeholder="lettering direction — 'circus poster woodtype', "
                                             "'drippy horror letters', 'chrome sci-fi'…") \
                    .props('outlined dense').classes('w-full q-mt-sm')

                def go():
                    dlg.close()
                    ui.notify(f"Lettering the {series.name.title()} masthead in {st.name.title()} — "
                              f"it lands here when it's done.", type='info')
                    enqueue_renders(state, [(
                        f"title art — {series.name} in {st.name}",
                        lambda n=(notes.value or '').strip() or None:
                            generate_series_title_art_body(state, series.series_id, st.style_id, n),
                    )], role='the Letterer')
                with ui.row().classes('w-full justify-end q-mt-sm'):
                    ui.button('Letter it', icon='brush').props('unelevated dense no-caps') \
                        .on('click', lambda _: go())
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
                    else:
                        art = st.image.get('art') if isinstance(st.image, dict) else st.image
                        if art and os.path.exists(art):
                            ui.image(source=art).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                        with ui.column().classes('absolute inset-0 items-center justify-center z-10'):
                            ui.button(f'Letter it in {st.name.title()}', icon='brush') \
                                .props('unelevated dense no-caps size=sm') \
                                .tooltip('Letter the series masthead in this style') \
                                .on('click', lambda _, st=st: ink_title(st))
        if True:
            def _issue_label(_i, issue):
                from schema import SceneModel, Panel
                done = total = 0
                for sc in storage.read_all_objects(SceneModel, {"series_id": series.series_id, "issue_id": issue.issue_id}):
                    for p in storage.read_all_objects(Panel, {"series_id": series.series_id, "issue_id": issue.issue_id, "scene_id": sc.scene_id}):
                        total += 1
                        if p.image and os.path.exists(p.image):
                            done += 1
                pulse = f"  ·  {done}/{total} 🎨" if total else "  ·  no panels"
                return f"{issue.name}{pulse}"

            view_all_instances(
                state=state, 
                get_instances=lambda: storage.read_all_objects(Issue, primary_key={"series_id": series.series_id}, order_by="issue_number"), 
                get_image_locator=lambda x: storage.find_issue_image(series_id=series.series_id, issue_id=x.issue_id),
                kind="issue",
                get_name=_issue_label,
                aspect_ratio="16/27",
                # 4x6 preferred: a 4x6 cover shares its bottom rule with THREE
                # 3x2 character rows exactly (span 6 = three span-2s + gutters)
                packer=packer, variants=[(4, 6), (2, 3)],
                overlap_caption=_cap("Issues", "I would like to create a new issue")
                ).style('margin-top: 0px; margin-bottom: 0px')

        # A cardwall for viewing and adding characters to the comic series.
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
                overlap_caption=_cap("Characters", "I would like to create a new character")
                ):
                pass
        uploader_card(
            state=state,
            on_upload=lambda e: upload_and_ask(e, "I would like to create a new character"),
            packer=packer,
            label='Drop image to create a character',
            overlap_caption=None if characters else _cap("Characters", "I would like to create a new character")
        )

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
                overlap_caption=_cap("Settings", "I would like to create a new setting")
                ).style('margin-top: 0px; margin-bottom: 0px')
        uploader_card(
            state=state,
            on_upload=lambda e: upload_and_ask(e, "I would like to create a new setting"),
            packer=packer,
            label='Drop image to create a setting',
            overlap_caption=None if settings else _cap("Settings", "I would like to create a new setting")
        )

        # Props and wardrobe: the reusable stuff panels are dressed with.
        def asset_image(a):
            return next((img for img in (a.images or {}).values() if img and os.path.exists(img)), None)

        props = storage.read_all_objects(PropAsset, primary_key={"series_id": series.series_id}, order_by="name")
        if props:
            view_all_instances(
                state=state,
                get_instances=lambda: props,
                get_image_locator=asset_image,
                kind="prop",
                aspect_ratio="3/2",
                get_name=lambda _, x: x.name,
                packer=packer, variants=[(3, 2)],
                overlap_caption=_cap("Props", "I would like to create a new prop")
                )
        uploader_card(
            state=state,
            on_upload=lambda e: upload_and_ask(e, "I would like to create a new prop"),
            packer=packer,
            label='Drop image to create a prop',
            overlap_caption=None if props else _cap("Props", "I would like to create a new prop")
        )

        outfits = storage.read_all_objects(Outfit, primary_key={"series_id": series.series_id}, order_by="name")
        if outfits:
            view_all_instances(
                state=state,
                get_instances=lambda: outfits,
                get_image_locator=asset_image,
                kind="outfit",
                aspect_ratio="3/2",
                get_name=lambda _, x: x.name,
                packer=packer, variants=[(3, 2)],
                overlap_caption=_cap("Wardrobe", "I would like to create a new outfit")
                )
        uploader_card(
            state=state,
            on_upload=lambda e: upload_and_ask(e, "I would like to create a new outfit"),
            packer=packer,
            label='Drop image to create an outfit',
            overlap_caption=None if outfits else _cap("Wardrobe", "I would like to create a new outfit")
        )
        packer.finalize()
        mosaic.__exit__(None, None, None)
        page.__exit__(None, None, None)
        