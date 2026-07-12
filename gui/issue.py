"""
THE OPEN BOOK: the issue view IS the comic.

Open an issue and the book lies on the table in side-by-side spreads —
the front cover is a page, THE SCRIPT is a page, the panels are live
tiles in real page grids (art when inked, the beat's words on script
paper until then), loose panels wait on THE TRAY page, and the book
closes with the back cover and a COLOPHON page carrying credits,
downloads, and the production small print.

Everything is done ON the book: set a tile's aspect right on the tile,
break a bare scene into beats from the script page, stitch loose panels
from the tray, click any tile to walk into its rough board and the
'page N' chip walks you back.  No dashboards, no drill-down sections —
one unified book.
"""
import os

from loguru import logger
from nicegui import ui

from schema import ComicStyle, Issue, Cover, Panel, SceneModel, Page, FrameLayout
from gui.elements import header, Attribute, view_attributes, crud_button, CrudButtonKind, markdown_field_editor
from gui.state import APPState
from gui.messaging import post_user_message
from gui.selection import SelectionItem, SelectedKind

COVER_ORDER = ["front", "inside-front", "inside-back", "back"]
ASPECT_CYCLE = {"landscape": "portrait", "portrait": "square", "square": "landscape"}
SIZE_CYCLE = {"regular": "large", "large": "splash", "splash": "small", "small": "regular"}
SIZE_ICON = {"small": "photo_size_select_small", "regular": "crop_din",
             "large": "photo_size_select_large", "splash": "fullscreen"}


def view_issue(state: APPState):
    selection = state.selection
    storage = state.storage

    series_id = selection[-2].id if len(selection) > 1 else None
    issue_id = selection[-1].id
    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id}) if series_id else None
    details = state.details
    if issue is None:
        state.clear_details()
        with details:
            ui.markdown(f"Issue with ID {issue_id} not found.")
        return

    if issue.style_id:
        style = storage.read_object(cls=ComicStyle, primary_key={"style_id": issue.style_id})
        if style is None:
            logger.warning(f"Issue {issue.id} has style set to {issue.style_id} but style not found.")

    # ---- one read of the whole book ------------------------------------
    scenes_all = storage.read_all_objects(SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id},
                                          order_by="scene_number")
    scene_of = {sc.scene_id: sc for sc in scenes_all}
    panels_by_scene = {sc.scene_id: storage.read_all_objects(
        Panel, primary_key={"series_id": series_id, "issue_id": issue_id, "scene_id": sc.scene_id},
        order_by="panel_number") for sc in scenes_all}
    panel_of = {p.panel_id: p for ps in panels_by_scene.values() for p in ps}
    total = len(panel_of)
    inked = sum(1 for p in panel_of.values() if p.image and os.path.exists(p.image))
    bare_scenes = [sc for sc in scenes_all if not panels_by_scene[sc.scene_id]]

    covers_all = storage.read_all_objects(Cover, primary_key={"series_id": series_id, "issue_id": issue_id})
    cover_at = {}
    for c in covers_all:
        cover_at.setdefault(c.location.value, c)
    pages_all = storage.read_all_objects(Page, primary_key={"series_id": series_id, "issue_id": issue_id},
                                         order_by="page_number")
    from helpers.binder import page_coverage
    _has, _placed, unplaced, dangling = page_coverage(storage, series_id, issue_id)
    export_dir = os.path.join("data", "series", series_id, "issues", issue_id, "exports")

    from gui.pages_board import open_panel
    from gui.light_table import table_receipt

    def goto(kind, id_, name):
        idx = next((i for i, s in enumerate(state.selection) if s.kind.value == 'issue'), None)
        base = state.selection[:idx + 1] if idx is not None else state.selection
        state.change_selection(new=[*base, SelectionItem(name=name, id=id_, kind=kind)])

    def open_scene_panel(scene_id, panel_id):
        open_panel(state, series_id, issue_id, scene_id, panel_id)

    def _repack_prints(panel_id):
        # the persisted PRINT layout follows the author's changes too
        from helpers.stitcher import repack_page
        for pm in storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id}):
            if pm.cells and any(r.panel_id == panel_id for row in pm.rows for r in row):
                repack_page(storage, pm)
                storage.update_object(pm)

    def cycle_aspect(scene_id, panel_id):
        """Turn the panel right on the tile; the book reflows around it."""
        p = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                        "scene_id": scene_id, "panel_id": panel_id})
        if p is None:
            return
        p.aspect = FrameLayout(ASPECT_CYCLE[p.aspect.value])
        storage.update_object(p)
        _repack_prints(panel_id)
        table_receipt(state, f"🔲 turned the panel {p.aspect.value} — the book reflowed around it")
        state.refresh_details()

    def cycle_size(scene_id, panel_id):
        """Resize the panel right on the tile; the book reflows around it."""
        p = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                        "scene_id": scene_id, "panel_id": panel_id})
        if p is None:
            return
        p.size = SIZE_CYCLE.get(getattr(p, 'size', None) or 'regular', 'regular')
        storage.update_object(p)
        _repack_prints(panel_id)
        table_receipt(state, f"🔲 made the panel a {p.size} — the book reflowed around it")
        state.refresh_details()

    def move_beat(scene_id, panel_id, d):
        """Nudge a beat through its scene; panels reflow across the pages."""
        sibs = sorted(storage.read_all_objects(Panel, primary_key={
            "series_id": series_id, "issue_id": issue_id, "scene_id": scene_id}),
            key=lambda p: p.panel_number)
        i = next((j for j, p in enumerate(sibs) if p.panel_id == panel_id), None)
        if i is None or not (0 <= i + d < len(sibs)):
            return
        sibs[i], sibs[i + d] = sibs[i + d], sibs[i]
        for j, p in enumerate(sibs):
            if p.panel_number != j + 1:
                p.panel_number = j + 1
                storage.update_object(p)
        table_receipt(state, f"↔️ moved the beat {'earlier' if d < 0 else 'later'} — "
                             f"the book reflowed around it")
        state.refresh_details()

    def move_scene(scene, d):
        sibs = sorted(storage.read_all_objects(SceneModel, primary_key={
            "series_id": series_id, "issue_id": issue_id}), key=lambda s: s.scene_number)
        i = next((j for j, s in enumerate(sibs) if s.scene_id == scene.scene_id), None)
        if i is None or not (0 <= i + d < len(sibs)):
            return
        sibs[i], sibs[i + d] = sibs[i + d], sibs[i]
        for j, s in enumerate(sibs):
            if s.scene_number != j + 1:
                s.scene_number = j + 1
                storage.update_object(s)
        table_receipt(state, f"↔️ moved **{sibs[i + d].name}** "
                             f"{'earlier' if d < 0 else 'later'} in the book")
        state.refresh_details()

    def scene_menu(sc):
        """Everything a scene needs, hanging off its caption box."""
        with ui.menu():
            ui.menu_item('Open the scene — cast, setting, story',
                         on_click=lambda _, s=sc: goto(SelectedKind.SCENE, s.scene_id, s.name))
            ui.menu_item('Move the scene earlier', on_click=lambda _, s=sc: move_scene(s, -1))
            ui.menu_item('Move the scene later', on_click=lambda _, s=sc: move_scene(s, 1))
            ui.menu_item('Add a beat to this scene',
                         on_click=lambda _, s=sc: post_user_message(
                             state, f"Add another panel to scene '{s.name}'."))
            ui.menu_item('Delete the scene…',
                         on_click=lambda _, s=sc: post_user_message(
                             state, f"I would like to delete scene '{s.name}'."))

    # ---- the tile: a panel living on a page ------------------------------
    # the page trim is 6.625 x 10.1875in; the 6x10 grid is the live area and
    # the difference breathes as margins, exactly like the printed page
    TRIM_W, TRIM_H = 6.625, 10.1875
    MX, MY = (TRIM_W - 6.0) / 2, (TRIM_H - 10.0) / 2

    def tile(scene_id, panel_id, x, y, w, h, grid_h=10.0, cap_scene=None):
        p = panel_of.get(panel_id)
        live_h = TRIM_H - 2 * MY
        box = (f'left: {(MX + x) / TRIM_W * 100:.2f}%; '
               f'top: {(MY + y / grid_h * live_h) / TRIM_H * 100:.2f}%; '
               f'width: {w / TRIM_W * 100:.2f}%; '
               f'height: {(h / grid_h * live_h) / TRIM_H * 100:.2f}%;')
        t = ui.element('div').classes('tile').style(box)
        with t:
            if p is None:
                ui.label('missing panel').classes('tile-beat text-xs text-gray-400')
            elif p.image and os.path.exists(p.image):
                ui.image(source=p.image).props('fit=cover').classes('absolute inset-0 w-full h-full')
            else:
                with ui.element('div').classes('tile-beat' + (' tile-beat--capped' if cap_scene else '')):
                    txt = (p.beat or '').strip()
                    ui.label(txt if txt else 'unwritten beat').classes(
                        'tile-beat__text' + ('' if txt else ' italic opacity-60'))
            if cap_scene is not None:
                # the scene announces itself on its first panel, comics-style;
                # its caption box is also the scene's handle (menu)
                cap = ui.label(f'{cap_scene.scene_number} · {cap_scene.name}'.upper()).classes('tile-cap')
                cap.tooltip('The scene — open it, move it, grow it')
                with cap:
                    scene_menu(cap_scene)
                cap.on('click.stop', lambda _: None)
            if p is not None:
                size = getattr(p, 'size', None) or 'regular'
                with ui.row().classes('tile-tools items-center flex-nowrap'):
                    ui.button(icon='chevron_left').props('flat round dense size=xs') \
                        .tooltip('Earlier in the scene') \
                        .on('click.stop', lambda _, s=scene_id, pid=panel_id: move_beat(s, pid, -1))
                    ui.button(icon={'landscape': 'crop_landscape', 'portrait': 'crop_portrait',
                                    'square': 'crop_square'}[p.aspect.value]) \
                        .props('flat round dense size=xs') \
                        .tooltip(f'{p.aspect.value} — click to turn the panel') \
                        .on('click.stop', lambda _, s=scene_id, pid=panel_id: cycle_aspect(s, pid))
                    ui.button(icon=SIZE_ICON[size]).props('flat round dense size=xs') \
                        .tooltip(f'{size} — click to resize the panel') \
                        .on('click.stop', lambda _, s=scene_id, pid=panel_id: cycle_size(s, pid))
                    ui.button(icon='chevron_right').props('flat round dense size=xs') \
                        .tooltip('Later in the scene') \
                        .on('click.stop', lambda _, s=scene_id, pid=panel_id: move_beat(s, pid, 1))
                    ui.button(icon='close').props('flat round dense size=xs') \
                        .tooltip('Tear this beat out of the book…') \
                        .on('click.stop', lambda _, p=p: post_user_message(
                            state, f"I would like to delete panel {p.panel_number} "
                                   f"('{p.name}') of this scene."))
        if p is not None:
            t.tooltip(f"beat {p.panel_number}: {p.name or ''} — open the rough board")
            t.on('click', lambda _, s=scene_id, pid=panel_id: open_scene_panel(s, pid))
        return t

    def cover_sheet(location, recto=False):
        c = cover_at.get(location)
        classes = 'book-page' + (' book-page--recto' if recto else '')
        if c is not None and c.image and os.path.exists(c.image):
            with ui.element('div').classes(classes) as sh:
                ui.image(source=c.image).props('fit=cover').classes('absolute inset-0 w-full h-full')
                ui.label(location.replace('-', ' ').upper()).classes('page-cap')
            sh.tooltip(f"The {location.replace('-', ' ')} cover — open its light table")
            sh.on('click', lambda _: goto(SelectedKind.COVER, c.cover_id, f"{location} cover"))
        elif c is not None:
            with ui.element('div').classes(classes + ' book-page--ghost') as sh:
                ui.label(f'{location.replace("-", " ")} cover').classes('page-cap')
                ui.label('bare board — open its light table').classes('page-ghost-hint')
            sh.on('click', lambda _: goto(SelectedKind.COVER, c.cover_id, f"{location} cover"))
        elif location in ('front', 'back'):
            with ui.element('div').classes(classes + ' book-page--ghost') as sh:
                ui.label(f'+ {location} cover').classes('page-ghost-cta')
            sh.tooltip('Every book needs one')
            sh.on('click', lambda _, loc=location: post_user_message(
                state, f"I would like to create a {loc} cover for this issue."))
        else:
            return False
        return True

    with details:
        # ---- the masthead over the table ---------------------------------
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0; gap: 12px;'):
            header(f"ISSUE {issue.issue_number}: {issue.name}", 0)
            from gui.light_table import style_swatch
            style_swatch(state, issue)
            ui.space()
            ui.button('Read', icon='menu_book').props('rounded') \
                .tooltip('Read the issue front to back') \
                .on('click', lambda _: ui.run_javascript(
                    f"window.open('/series/{series_id}/issue/{issue_id}/read', '_blank');"))
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current issue."))

        # ---- THE OPEN BOOK ------------------------------------------------
        with ui.element('div').classes('book w-full'):
            # the front cover opens the book alone on the recto, like a real one
            cover_sheet('front', recto=True)
            cover_sheet('inside-front')

            # THE SCRIPT: a manuscript page in the book
            with ui.element('div').classes('book-page book-page--script'):
                ui.label('THE SCRIPT').classes('page-cap')
                with ui.element('div').classes('script-body'):
                    if issue.story:
                        ui.markdown(issue.story).classes('script-text')
                    else:
                        ui.label('This book has no words yet.').classes('page-ghost-hint q-mt-lg')

                def edit_script():
                    with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 640px; max-width: 900px;'):
                        markdown_field_editor(state, "The script", issue.story)
                    dlg.open()
                with ui.row().classes('script-foot items-center').style('gap: 4px;'):
                    ui.button(icon='edit').props('flat round dense size=sm') \
                        .tooltip('Rewrite the script').on('click', lambda _: edit_script())
                    if not issue.story:
                        ui.chip('write it with me', icon='auto_stories').props('dense outline clickable') \
                            .on('click', lambda _: post_user_message(state, "Help me write the story for this issue."))
                    ui.chip('+ scene', icon='add').props('dense outline clickable') \
                        .tooltip('Another scene in the story') \
                        .on('click', lambda _: post_user_message(state, "I would like to create a new scene for this issue."))
            # THE BOOK FLOWS CONTINUOUSLY: beats pack across page turns the
            # way text reflows across lines — turning, resizing, or moving a
            # panel can carry its neighbors onto the next or previous page.
            # A scene with no beats yet holds its place as a manuscript page.
            from helpers.stitcher import pack_bands, paginate, justify, AR
            segments, run = [], []
            for sc in scenes_all:
                panels = panels_by_scene[sc.scene_id]
                if panels:
                    run += [((sc.scene_id, p.panel_id), AR.get(p.aspect.value, 1.5),
                             getattr(p, 'size', None) or 'regular') for p in panels]
                else:
                    if run:
                        segments.append(('flow', run))
                        run = []
                    segments.append(('manuscript', sc))
            if run:
                segments.append(('flow', run))

            first_tiles = {ps[0].panel_id: sc for sc in scenes_all
                           for ps in [panels_by_scene[sc.scene_id]] if ps}
            folio = 0
            for kind, seg in segments:
                if kind == 'flow':
                    band_pages = paginate(pack_bands(seg))
                    for pi, pb in enumerate(band_pages):
                        folio += 1
                        cells = justify(pb, is_last=(pi == len(band_pages) - 1))
                        grid_h = max(10.0, max(y + h for _k, _x, y, _w, h in cells))
                        with ui.element('div').classes('book-page'):
                            for key, x, y, w, h in cells:
                                tile(key[0], key[1], x, y, w, h, grid_h,
                                     cap_scene=first_tiles.get(key[1]))
                            ui.label(str(folio)).classes('page-folio')
                else:
                    sc = seg
                    folio += 1
                    with ui.element('div').classes('book-page book-page--script'):
                        cap = ui.label(f'{sc.scene_number} · {sc.name}'.upper()).classes('page-cap')
                        cap.tooltip('The scene — open it, move it, grow it')
                        with cap:
                            scene_menu(sc)
                        cap.on('click.stop', lambda _: None)
                        with ui.element('div').classes('script-body'):
                            if sc.story:
                                ui.markdown(sc.story).classes('script-text')
                            else:
                                ui.label('Nothing written for this scene yet.') \
                                    .classes('page-ghost-hint q-mt-lg')
                        with ui.row().classes('script-foot items-center').style('gap: 4px;'):
                            ui.chip('break it into beats', icon='grid_on') \
                                .props('dense outline clickable') \
                                .tooltip("I'll break this scene into beats — they flow "
                                         "onto these pages as tiles") \
                                .on('click', lambda _, s=sc: post_user_message(
                                    state, f"Break scene '{s.name}' into panels."))
                        ui.label(str(folio)).classes('page-folio')

            cover_sheet('inside-back')
            cover_sheet('back')

            # THE COLOPHON: credits, downloads, the production small print
            with ui.element('div').classes('book-page book-page--script'):
                ui.label('COLOPHON').classes('page-cap')
                with ui.element('div').classes('script-body'):
                    def _set(field):
                        def setter(value):
                            setattr(issue, field, value or None)
                            storage.update_object(data=issue)
                        return setter
                    view_attributes(
                        state=state, caption="", individual_icons=False,
                        attributes=[
                            Attribute(caption="writer", get_value=lambda: issue.writer, set_value=_set("writer")),
                            Attribute(caption="artist", get_value=lambda: issue.artist, set_value=_set("artist")),
                            Attribute(caption="colorist", get_value=lambda: issue.colorist, set_value=_set("colorist")),
                            Attribute(caption="creative minds", get_value=lambda: issue.creative_minds, set_value=_set("creative_minds")),
                            Attribute(caption="publication date", get_value=lambda: issue.publication_date, set_value=_set("publication_date")),
                            Attribute(caption="price", get_value=lambda: issue.price, set_value=lambda v: (setattr(issue, "price", float(v) if v else None), storage.update_object(data=issue))),
                        ])
                    with ui.row().classes('q-mt-md items-center').style('gap: 6px; flex-wrap: wrap;'):
                        for fname, label in ((f"{issue_id}.pdf", '⤓ PDF'), (f"{issue_id}.cbz", '⤓ CBZ')):
                            path = os.path.join(export_dir, fname)
                            if os.path.exists(path):
                                ui.chip(label, icon='download').props('dense outline clickable') \
                                    .on('click', lambda _, u='/' + path.replace(os.sep, '/'):
                                        ui.run_javascript(f"window.open('{u}', '_blank');"))
                        ui.chip('bind it', icon='menu_book').props('dense outline clickable') \
                            .tooltip("I'll bind the book and hand you the download") \
                            .on('click', lambda _: post_user_message(state, "Export the issue as a PDF."))
                # the small print tells the production truth
                bits = [f"{inked} of {total} panels inked" if total else "no panels yet",
                        "every panel placed" if pages_all and not unplaced and not dangling
                        else f"{len(unplaced)} panel(s) loose" if unplaced else "no pages yet"]
                if bare_scenes:
                    bits.append(f"{len(bare_scenes)} scene(s) still to break down")
                ui.label("  ·  ".join(bits)).classes('page-small-print')
