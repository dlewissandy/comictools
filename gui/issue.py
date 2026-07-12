"""
THE ISSUE WORKSPACE: the comic front and center, one unified experience.

The book you're making IS the page: a masthead, THE SPINE RAIL (five stage
chips that report production truth AND set the viewing altitude — one click
collapses back up), THE SHELF (the physical book: covers, a spine that
thickens as pages land, every sheet leafable), THE SCRIPT, THE SCENES as
tiers that expand into beats — each beat wearing the lens of the altitude
you're at (words → table state → print) — and THE PRESSROOM at the bottom.

Click grammar: a chevron or rail chip changes what you SEE; the face of a
thing walks INTO its editor (cover → its light table, scene → its view,
beat → its light table, sheet → the page in hand).
"""
import os
import re

from loguru import logger
from nicegui import ui

from schema import ComicStyle, Issue, Cover, Panel, SceneModel, Page
from gui.elements import header, Attribute, view_attributes, crud_button, CrudButtonKind, markdown_field_editor
from gui.state import APPState
from gui.messaging import post_user_message
from gui.selection import SelectionItem, SelectedKind

RANK = {"script": 0, "scenes": 1, "beats": 2, "roughs": 3, "prints": 4}
COVER_ORDER = ["front", "inside-front", "inside-back", "back"]


def _workspace(state, issue_id):
    ws_all = getattr(state, '_workspace', None)
    if ws_all is None:
        ws_all = {}
        state._workspace = ws_all
    return ws_all.setdefault(issue_id, {"altitude": "scenes", "open": set()})


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

    ws = _workspace(state, issue_id)
    altitude = ws["altitude"]
    rank = RANK.get(altitude, 1)

    def set_altitude(a):
        ws["altitude"] = a
        ws["open"] = set()          # the rail clears per-scene overrides
        state.refresh_details()

    def toggle_scene(scene_id):
        ws["open"] ^= {scene_id}    # an override relative to the altitude floor
        state.refresh_details()

    # ---- one read of the whole book -----------------------------------
    scenes_all = storage.read_all_objects(SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id},
                                          order_by="scene_number")
    panels_by_scene = {sc.scene_id: storage.read_all_objects(
        Panel, primary_key={"series_id": series_id, "issue_id": issue_id, "scene_id": sc.scene_id},
        order_by="panel_number") for sc in scenes_all}
    all_panels = [p for ps in panels_by_scene.values() for p in ps]
    total = len(all_panels)
    inked = sum(1 for p in all_panels if p.image and os.path.exists(p.image))
    on_table = sum(1 for p in all_panels if (p.figure_images or (p.image and os.path.exists(p.image))))
    bare_scenes = sum(1 for sc in scenes_all if not panels_by_scene[sc.scene_id])

    covers_all = storage.read_all_objects(Cover, primary_key={"series_id": series_id, "issue_id": issue_id})
    covers_all.sort(key=lambda c: COVER_ORDER.index(c.location.value) if c.location.value in COVER_ORDER else 9)
    front_ok = any(c.location.value == "front" and c.image and os.path.exists(c.image) for c in covers_all)
    pages_all = storage.read_all_objects(Page, primary_key={"series_id": series_id, "issue_id": issue_id},
                                         order_by="page_number")
    from helpers.binder import page_coverage
    has_layout, _placed, unplaced, dangling = page_coverage(storage, series_id, issue_id)
    layout_ok = has_layout and not unplaced and not dangling
    placed_on = {}
    for pm in pages_all:
        for row in pm.rows:
            for ref in row:
                placed_on.setdefault(ref.panel_id, pm.page_number)
    export_path = os.path.join("data", "series", series_id, "issues", issue_id, "exports", f"{issue_id}.pdf")
    print_ready = bool(issue.story) and total > 0 and inked == total and front_ok and layout_ok

    from gui.pages_board import page_thumb, edit_page, pressroom, open_panel, stitch_now

    def goto(kind, id_, name):
        idx = next((i for i, s in enumerate(state.selection) if s.kind.value == 'issue'), None)
        base = state.selection[:idx + 1] if idx is not None else state.selection
        state.change_selection(new=[*base, SelectionItem(name=name, id=id_, kind=kind)])

    with details:
        # ---- MASTHEAD ---------------------------------------------------
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0; gap: 12px;'):
            header(f"ISSUE {issue.issue_number}: {issue.name}", 0)
            from gui.light_table import style_swatch
            style_swatch(state, issue)
            if print_ready and os.path.exists(export_path):
                ui.chip('ON THE STANDS', icon='celebration', color='green').props('dense clickable') \
                    .tooltip('The issue is print-ready — read it front to back') \
                    .on('click', lambda _: ui.run_javascript(
                        f"window.open('/series/{series_id}/issue/{issue_id}/read', '_blank');"))
            ui.space()
            ui.button('Read', icon='menu_book').props('rounded') \
                .tooltip('Read the issue front to back') \
                .on('click', lambda _: ui.run_javascript(
                    f"window.open('/series/{series_id}/issue/{issue_id}/read', '_blank');"))
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current issue."))

        # ---- THE SPINE RAIL: production truth + viewing altitude --------
        story_words = len((issue.story or '').split())
        n_sc = len(scenes_all)
        stages = [
            ("script", "THE SCRIPT", f"{story_words} words" if issue.story else "unwritten",
             100 if issue.story else 0),
            ("scenes", "SCENES", f"{n_sc}" if n_sc else "none yet",
             100 if n_sc else 0),
            ("beats", "BEATS",
             (f"{total}" + (f" · {bare_scenes} scene(s) bare" if bare_scenes else "")) if n_sc else "—",
             int(100 * (n_sc - bare_scenes) / n_sc) if n_sc else 0),
            ("roughs", "ROUGHS", f"{on_table}/{total} on the table" if total else "—",
             int(100 * on_table / total) if total else 0),
            ("prints", "PRINTS",
             (f"{inked}/{total} inked" + (f" · {len(unplaced)} unplaced" if has_layout and unplaced else "")) if total else "—",
             int(100 * inked / total) if total else 0),
        ]
        with ui.row().classes('w-full items-center').style('gap: 8px; flex-wrap: wrap;'):
            for key, label, sub, pct in stages:
                chip = ui.element('div').classes('stage-chip' + (' stage-chip--here' if altitude == key else '')
                                                 + (' stage-chip--done' if pct >= 100 else ''))
                chip.mark(f'altitude-{key}')
                chip.style(f'--pct: {pct}%;')
                with chip:
                    ui.label(label).classes('stage-chip__name')
                    ui.label(sub).classes('stage-chip__sub')
                chip.on('click', lambda _, k=key: set_altitude(k))
                chip.tooltip(f"See the book at {label.lower()} altitude")
            bound_ok = print_ready and os.path.exists(export_path)
            bc = ui.chip('⤓ bound', icon='check_circle' if bound_ok else 'radio_button_unchecked',
                         color='green' if bound_ok else 'orange').props('dense outline clickable')
            if bound_ok:
                bc.tooltip('Open the bound PDF')
                bc.on('click', lambda _: ui.run_javascript(
                    f"window.open('/{export_path.replace(os.sep, '/')}', '_blank');"))
            else:
                bc.tooltip("Click and I'll bind what's ready")
                bc.on('click', lambda _: post_user_message(state, "Export the issue as a PDF."))

        # ---- THE SHELF: the physical book -------------------------------
        with ui.row().classes('shelf w-full flex-nowrap items-end'):
            front = next((c for c in covers_all if c.location.value == 'front'), None)
            for c in covers_all:
                with ui.element('div').classes('shelf-sheet').style('width: 96px;') as sheet:
                    if c.image and os.path.exists(c.image):
                        ui.image(source=c.image).props('fit=cover').style('width: 96px; height: 144px;')
                    else:
                        ui.label(f'{c.location.value} cover\n(bare board)') \
                            .classes('text-xs text-gray-500 text-center') \
                            .style('width: 96px; height: 144px; display: flex; align-items: center; '
                                   'justify-content: center; white-space: pre-line;')
                    sheet.tooltip(f"The {c.location.value.replace('-', ' ')} cover — open its light table")
                    sheet.on('click', lambda _, c=c: goto(SelectedKind.COVER, c.cover_id,
                                                          f"{c.location.value} cover"))
            if front is None:
                with ui.element('div').classes('shelf-sheet shelf-ghost').style('width: 96px;') as g:
                    ui.label('+ front cover').classes('text-xs text-gray-500 text-center') \
                        .style('width: 96px; height: 144px; display: flex; align-items: center; justify-content: center;')
                    g.tooltip('Every book needs a face')
                    g.on('click', lambda _: post_user_message(state, "I would like to create a front cover for this issue."))
            # the spine thickens as the book grows
            ui.element('div').classes('shelf-spine').style(f'width: {4 + len(pages_all)}px; height: 144px;') \
                .tooltip(f"{len(pages_all)} page(s) and counting" if pages_all else "no pages yet")
            for pm in pages_all:
                with ui.element('div').classes('shelf-sheet').style('width: 96px;') as sheet:
                    ui.image(source=page_thumb(state, series_id, issue_id, pm)) \
                        .props('fit=contain').style('width: 96px;')
                    ui.label(f'{pm.page_number}').classes('shelf-folio')
                    sheet.tooltip(f'Page {pm.page_number} — take it in hand')
                    sheet.on('click', lambda _, pid=pm.page_id: edit_page(state, series_id, issue_id, pid))
            if total and not pages_all:
                with ui.element('div').classes('shelf-sheet shelf-ghost').style('width: 96px;') as g:
                    ui.label('🧵 stitch\nthe book').classes('text-xs text-center') \
                        .style('width: 96px; height: 144px; display: flex; align-items: center; '
                               'justify-content: center; white-space: pre-line;')
                    g.tooltip('Lay every panel onto pages, reading order, one click')
                    g.on('click', lambda _: stitch_now(state, series_id, issue_id))
            if covers_all or pages_all:
                with ui.element('div').classes('shelf-bookend') as be:
                    ui.label('READ').classes('shelf-bookend__label')
                    be.tooltip('Pick the book up — the reading room')
                    be.on('click', lambda _: ui.run_javascript(
                        f"window.open('/series/{series_id}/issue/{issue_id}/read', '_blank');"))

        # ---- THE SCRIPT --------------------------------------------------
        if altitude == 'script' or not issue.story:
            markdown_field_editor(state, "The script", issue.story)

            def _set(field):
                def setter(value):
                    setattr(issue, field, value or None)
                    storage.update_object(data=issue)
                return setter
            with ui.expansion('Credits & indicia — they print on the inside front cover') \
                    .classes('w-full section-flat'):
                view_attributes(
                    state=state, caption="", individual_icons=False,
                    attributes=[
                        Attribute(caption="publication date", get_value=lambda: issue.publication_date, set_value=_set("publication_date")),
                        Attribute(caption="price", get_value=lambda: issue.price, set_value=lambda v: (setattr(issue, "price", float(v) if v else None), storage.update_object(data=issue))),
                        Attribute(caption="writer", get_value=lambda: issue.writer, set_value=_set("writer")),
                        Attribute(caption="artist", get_value=lambda: issue.artist, set_value=_set("artist")),
                        Attribute(caption="colorist", get_value=lambda: issue.colorist, set_value=_set("colorist")),
                        Attribute(caption="creative minds", get_value=lambda: issue.creative_minds, set_value=_set("creative_minds")),
                    ])
        else:
            # the arc strip: beginning and destination in one line — the
            # writer's compass while working deep in a tier
            sentences = re.split(r'(?<=[.!?])\s+', issue.story.strip())
            arc = sentences[0] + ("  …  " + sentences[-1] if len(sentences) > 1 else "")
            with ui.row().classes('arc-strip w-full items-center flex-nowrap').style('gap: 8px;') as strip:
                ui.icon('history_edu').classes('text-lg')
                ui.label(arc).classes('arc-strip__text')
                ui.space()
                ui.label(f'{story_words} words').classes('text-xs text-gray-500').style('flex-shrink: 0;')
                strip.tooltip('The script — click to read and edit it')
                strip.on('click', lambda _: set_altitude('script'))

        # ---- THE SCENES: tiers that open into beats ----------------------
        with ui.row().classes('w-full items-center q-mt-sm').style('gap: 10px;'):
            ui.label('THE SCENES').classes('comic-label-sm')
            ui.button(icon='add').props('flat round dense size=sm') \
                .tooltip('Another scene') \
                .on('click', lambda _: post_user_message(state, "I would like to create a new scene for this issue."))
            if scenes_all and altitude == 'script':
                ui.label(f'{n_sc} scene(s) — the SCENES chip on the rail opens them') \
                    .classes('text-xs text-gray-500')
        if not scenes_all:
            ui.label('No scenes yet — expand the script into scenes with me.') \
                .classes('text-sm text-gray-500')

        if altitude != 'script':
            lens = altitude if rank >= RANK['beats'] else 'beats'
            for sc in scenes_all:
                panels = panels_by_scene[sc.scene_id]
                opened = (rank >= RANK['beats']) ^ (sc.scene_id in ws["open"])
                with ui.row().classes('light-layer tier-row w-full items-center flex-nowrap').style('gap: 8px;'):
                    ui.button(icon='expand_less' if opened else 'expand_more') \
                        .props('flat round dense size=sm') \
                        .tooltip('Fold the beats away' if opened else 'Open this scene into its beats') \
                        .on('click', lambda _, sid=sc.scene_id: toggle_scene(sid))
                    img = storage.find_scene_image(series_id=series_id, issue_id=issue_id, scene_id=sc.scene_id)
                    if img:
                        ui.image(source=img).props('fit=cover').style(
                            'width: 64px; height: 36px; border-radius: 3px; flex-shrink: 0;')
                    nm = ui.label(f"#{sc.scene_number} · {sc.name}").classes('tier-row__name') \
                        .tooltip('Open the scene view')
                    nm.on('click', lambda _, s=sc: goto(SelectedKind.SCENE, s.scene_id, s.name))
                    with ui.row().classes('items-center flex-nowrap').style('gap: 3px;'):
                        for p in panels:
                            done = p.image and os.path.exists(p.image)
                            half = bool(p.figure_images) and not done
                            ui.element('span').classes(
                                'ink-dot' + (' ink-dot--solid' if done else ' ink-dot--half' if half else '')) \
                                .tooltip(f"beat {p.panel_number}: "
                                         + ('inked' if done else 'on the table' if half else 'penciled'))
                    if not panels:
                        ui.chip('no beats yet — break it down', icon='edit', color='orange') \
                            .props('dense outline clickable') \
                            .tooltip("Click and I'll break this scene into beats with you") \
                            .on('click', lambda _, s=sc: post_user_message(
                                state, f"Break scene '{s.name}' into panels."))
                    ui.space()

                    def _nudge(scene, d):
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
                        from gui.light_table import table_receipt
                        table_receipt(state, f"↔️ moved **{sibs[i + d].name}** "
                                             f"{'earlier' if d < 0 else 'later'} in the issue")
                        state.refresh_details()
                    ui.button(icon='chevron_left').props('flat round dense size=xs') \
                        .tooltip('Earlier in the issue').on('click', lambda _, s=sc: _nudge(s, -1))
                    ui.button(icon='chevron_right').props('flat round dense size=xs') \
                        .tooltip('Later in the issue').on('click', lambda _, s=sc: _nudge(s, 1))

                if opened and panels:
                    with ui.row().classes('w-full flex-nowrap tier-beats').style(
                            'gap: 8px; overflow-x: auto; padding: 4px 2px 10px 44px;'):
                        for p in panels:
                            done = p.image and os.path.exists(p.image)
                            with ui.card().classes('soft-card beat-card p-1 cursor-pointer relative') as card:
                                if p.panel_id in placed_on and done:
                                    ui.element('div').classes('corner-fold')
                                with ui.row().classes('w-full items-center flex-nowrap').style('gap: 4px;'):
                                    ui.label(f'#{p.panel_number}').classes('text-xs text-gray-500')
                                    ui.icon({'landscape': 'crop_landscape', 'portrait': 'crop_portrait',
                                             'square': 'crop_square'}.get(p.aspect.value, 'crop_landscape')) \
                                        .classes('text-xs text-gray-500')
                                    ui.space()
                                    ui.icon('edit').classes(
                                        'text-xs ' + ('text-green-700' if p.beat else 'text-gray-400')) \
                                        .tooltip('penciled' if p.beat else 'unwritten')
                                    ui.icon('layers').classes(
                                        'text-xs ' + ('text-green-700' if p.figure_images else 'text-gray-400')) \
                                        .tooltip(f'{len(p.figure_images)} acetate(s) on the table'
                                                 if p.figure_images else 'bare board')
                                    ui.icon('brush').classes(
                                        'text-xs ' + ('text-green-700' if done else 'text-gray-400')) \
                                        .tooltip('inked' if done else 'not inked yet')
                                if lens == 'prints' or (lens == 'roughs' and done):
                                    if done:
                                        ui.image(source=p.image).props('fit=cover').style('height: 84px;')
                                    else:
                                        with ui.element('div').style(
                                                'height: 84px; border: 2px dashed #bbb; border-radius: 4px; '
                                                'display: flex; align-items: center; justify-content: center;'):
                                            ui.label('unrendered').classes('text-xs text-gray-500')
                                elif lens == 'roughs':
                                    with ui.column().classes('w-full items-center justify-center').style('height: 84px; gap: 2px;'):
                                        if p.figure_images:
                                            ui.label(f'{len(p.figure_images)} acetate(s)').classes('text-sm')
                                            ui.label('on the table').classes('text-xs text-gray-500')
                                        else:
                                            ui.label('bare board').classes('text-sm text-gray-500')
                                            ui.label('walk in and build it').classes('text-xs text-gray-400')
                                else:
                                    txt = (p.beat or '').strip()
                                    with ui.element('div').classes('beat-card__paper').style('height: 84px;'):
                                        if txt:
                                            ui.label(txt).classes('beat-card__text')
                                        else:
                                            ui.label('unwritten — click the pencil').classes(
                                                'text-xs text-gray-400 italic')
                                with ui.row().classes('w-full items-center flex-nowrap').style('gap: 4px; min-height: 20px;'):
                                    ui.label(p.name or '').classes('text-xs') \
                                        .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;')
                                    if not (p.beat or '').strip():
                                        ui.button(icon='edit').props('flat round dense size=xs') \
                                            .tooltip('Pencil this beat — I\'ll draft it from the scene') \
                                            .on('click.stop', lambda _, s=sc, p=p: post_user_message(
                                                state, f"Write the beat text for panel {p.panel_number} "
                                                       f"of scene '{s.name}', from the scene's story."))
                                    elif not done and lens == 'prints':
                                        ui.button(icon='brush').props('flat round dense size=xs') \
                                            .tooltip('Ink it — render this panel') \
                                            .on('click.stop', lambda _, s=sc, p=p: post_user_message(
                                                state, f"Render panel {p.panel_number} of scene '{s.name}'."))
                                    if p.panel_id in placed_on:
                                        ui.chip(f'p{placed_on[p.panel_id]}', icon='menu_book') \
                                            .props('dense outline clickable size=sm') \
                                            .tooltip(f'Printed on page {placed_on[p.panel_id]} — take the page in hand') \
                                            .on('click.stop', lambda _, p=p: edit_page(
                                                state, series_id, issue_id,
                                                next((pg.page_id for pg in pages_all
                                                      if any(r.panel_id == p.panel_id for row in pg.rows for r in row)), None)))
                            card.on('click', lambda _, s=sc, p=p: open_panel(
                                state, series_id, issue_id, s.scene_id, p.panel_id))
                            card.tooltip('Open this beat on its light table')
                        with ui.card().classes('soft-card beat-card ghost-card p-1 cursor-pointer items-center justify-center') as gcard:
                            ui.label('+ beat').classes('text-sm text-gray-500')
                            gcard.tooltip('Another beat in this scene')
                            gcard.on('click', lambda _, s=sc: post_user_message(
                                state, f"Add another panel to scene '{s.name}'."))

        # ---- THE PRESSROOM ------------------------------------------------
        if altitude == 'prints' or unplaced or dangling or not pages_all:
            pressroom(state, series_id, issue_id)
        else:
            with ui.row().classes('arc-strip w-full items-center').style('gap: 8px;') as pr:
                ui.icon('auto_awesome_mosaic').classes('text-lg')
                ui.label(f'The pressroom — {len(pages_all)} page(s), every panel placed') \
                    .classes('text-xs')
                pr.tooltip('Open the pressroom — stitching and the unplaced tray')
                pr.on('click', lambda _: set_altitude('prints'))
