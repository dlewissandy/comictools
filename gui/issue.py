"""
THE OPEN BOOK: the issue view IS the comic.

Open an issue and the book lies on the table in side-by-side spreads —
covers are pages, every STORY is a manuscript page (comics run features
and backups), scenes hold their place as manuscript pages until their
beats flow as live tiles across the page turns, FULL-PAGE INSERTS
(posters, ads, the mailbag) slot in wherever they're anchored, and the
book closes with the back cover and a COLOPHON.

Everything is done ON the book: ‹ › reorder and ✕ on stories, scenes,
inserts and beats; ✏️ edits any text in place (or hands it to the
coauthor to work on together); a tile's aspect and size (1x/2x/3x) turn
right on the tile and the whole book reflows continuously.  The DETAIL
DIAL in the masthead reads the book at STORIES, SCENES, or BEATS
altitude; the masthead stays put and the book remembers your spot when
you walk into a panel and back.
"""
import os

from loguru import logger
from nicegui import ui

from schema import (ComicStyle, Issue, Cover, Insert, Panel, SceneModel, Page,
                    Story, FrameLayout)
from gui.elements import header, crud_button, CrudButtonKind
from gui.state import APPState
from gui.messaging import post_user_message
from gui.selection import SelectionItem, SelectedKind


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

    # ---- view state: detail dial + remembered spot ----------------------
    if not hasattr(state, '_book_detail'):
        state._book_detail = {}
    if not hasattr(state, '_book_anchor'):
        state._book_anchor = {}
    detail = state._book_detail.get(issue_id, 'beats')

    def set_detail(d):
        state._book_detail[issue_id] = d
        # a dial flip opens the book at its FRONT, not wherever the old
        # altitude happened to be scrolled — unless a door already chose a
        # destination (the 'N panels' chip anchors the scene's first panel)
        state._book_anchor.setdefault(issue_id, 'masthead-top')
        state.refresh_details()

    def remember_spot(anchor):
        state._book_anchor[issue_id] = anchor

    # ---- one read of the whole book -----------------------------------
    scenes_all = storage.read_all_objects(SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id},
                                          order_by="scene_number")
    panels_by_scene = {sc.scene_id: storage.read_all_objects(
        Panel, primary_key={"series_id": series_id, "issue_id": issue_id, "scene_id": sc.scene_id},
        order_by="panel_number") for sc in scenes_all}
    panel_of = {p.panel_id: p for ps in panels_by_scene.values() for p in ps}

    stories_all = storage.read_all_objects(Story, primary_key={"series_id": series_id, "issue_id": issue_id})
    stories_all.sort(key=lambda s: s.story_number)
    inserts_all = storage.read_all_objects(Insert, primary_key={"series_id": series_id, "issue_id": issue_id})
    inserts_all.sort(key=lambda i: (i.after_scene_number, i.insert_id))

    scene_by_id = {sc.scene_id: sc for sc in scenes_all}
    # THE CAST ROSTER, read once: a scene's cast/props strip (now living in
    # the book, not a page of its own) wears NAMES, not ids
    from schema import CharacterModel as _CharacterModel
    roster = {c.character_id: c for c in
              storage.read_all_objects(_CharacterModel, primary_key={"series_id": series_id})}
    covers_all = storage.read_all_objects(Cover, primary_key={"series_id": series_id, "issue_id": issue_id})
    cover_at = {}
    for c in covers_all:
        cover_at.setdefault(c.location.value, c)

    # THE LAYOUT IS REMEMBERED: quietly persist the stitched pagination so
    # the print, the page chips, and the book never drift apart — BEFORE
    # reading the coverage truth the colophon prints
    try:
        from helpers.stitcher import remember_stitch
        remember_stitch(storage, series_id, issue_id)
    except Exception as ex:
        logger.warning(f"remember_stitch skipped: {ex}")
    # ONE PRODUCTION LEDGER: the single truth the masthead badge, the
    # colophon and the Editor all quote — computed once per paint
    from helpers.ledger import issue_ledger
    ledger = issue_ledger(storage, series_id, issue_id)
    # exports land under the HOUSE's own root — the root 'data' sees
    # nothing under mount-all, and the colophon's download chips must appear
    export_dir = os.path.join(str(storage.base_path), "series", series_id, "issues", issue_id, "exports")

    def open_panel(state, series_id, issue_id, scene_id, panel_id):
        """Walk from the book into a panel's light table."""
        sc = storage.read_object(SceneModel, {"series_id": series_id, "issue_id": issue_id,
                                              "scene_id": scene_id})
        p = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                        "scene_id": scene_id, "panel_id": panel_id})
        base = state.selection
        # the issue anchors the chain — trim anything deeper before descending
        idx = next((i for i, s in enumerate(base) if s.kind.value == 'issue'), None)
        if idx is not None:
            base = base[:idx + 1]
        state.change_selection(new=[*base,
            SelectionItem(name=(sc.name if sc else scene_id), id=scene_id, kind=SelectedKind.SCENE),
            SelectionItem(name=(p.name if p else panel_id), id=panel_id, kind=SelectedKind.PANEL)])

    from gui.light_table import table_receipt

    def receipt(text):
        table_receipt(state, text, bench='the open book')
        state.refresh_details()

    def goto(kind, id_, name, anchor=None):
        if anchor:
            remember_spot(anchor)
        idx = next((i for i, s in enumerate(state.selection) if s.kind.value == 'issue'), None)
        base = state.selection[:idx + 1] if idx is not None else state.selection
        state.change_selection(new=[*base, SelectionItem(name=name, id=id_, kind=kind)])

    def open_scene_panel(scene_id, panel_id):
        remember_spot(f'panel-{panel_id}')
        open_panel(state, series_id, issue_id, scene_id, panel_id)

    # ---- shared text editor: THE CONVERSATION IS THE MODAL --------------
    def edit_text_dialog(title, initial, on_save, develop_msg):
        # The words land in the conversation box, prefilled: Enter saves
        # DIRECTLY (one-shot intercept, no agent turn), Shift+Enter breaks
        # a line, an erased prefix stands down — and typing something else
        # entirely simply talks to the Editor (the old 'work on it with
        # me' door, without the detour; develop_msg kept for callers).
        prefix = f"{title}: "
        state.user_input.value = prefix + (initial or '')
        if len(initial or '') > 400:
            # a manuscript needs room — the box opens tall for this edit
            state.user_input.classes('input-tall')

        def _save(text):
            if text is None:
                ui.notify(f'{title} unchanged — write the words after the prompt '
                          f'to rewrite it.', type='info')
                return
            on_save(text)
        state._input_intercept = (prefix, _save, None)
        try:
            state.user_input.run_method('focus')
        except Exception:
            pass
        ui.notify('Enter saves; Shift+Enter for a new line; clear the line to '
                  'change the subject instead.', type='info',
                  position='bottom', timeout=4000)

    # ---- mutations -------------------------------------------------------
    def move_beat(scene_id, panel_id, d):
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
        receipt(f"↔️ moved the panel {'earlier' if d < 0 else 'later'} — the book reflowed")

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
        receipt(f"↔️ moved **{sibs[i + d].name}** {'earlier' if d < 0 else 'later'} in the book")

    def move_story(story, d):
        sibs = sorted(storage.read_all_objects(Story, primary_key={
            "series_id": series_id, "issue_id": issue_id}), key=lambda s: s.story_number)
        i = next((j for j, s in enumerate(sibs) if s.story_id == story.story_id), None)
        if i is None or not (0 <= i + d < len(sibs)):
            return
        sibs[i], sibs[i + d] = sibs[i + d], sibs[i]
        for j, s in enumerate(sibs):
            if s.story_number != j + 1:
                s.story_number = j + 1
                storage.update_object(s)
        receipt(f"↔️ moved the story {'earlier' if d < 0 else 'later'} in the book")

    def move_insert(ins, d):
        fresh = storage.read_object(Insert, ins.primary_key)
        if fresh is None:
            return
        # step through the REAL anchor spots — and the STRIDE matches the
        # altitude the author stands at: on SCRIPTS a whole story at a
        # time (each story's last scene), on scenes/panels one scene
        detail = (getattr(state, '_book_detail', None) or {}).get(issue_id, 'beats')
        if detail == 'stories':
            _real = {st.story_id for st in stories_all}
            _by = {}
            for sc in scenes_all:
                _key = sc.story_id if sc.story_id in _real else None
                _by.setdefault(_key, []).append(sc.scene_number)
            anchors = sorted({0} | {max(v) for v in _by.values() if v})
        else:
            anchors = [0] + sorted(s.scene_number for s in scenes_all)
        cur = max([a for a in anchors if a <= fresh.after_scene_number], default=0)
        i = anchors.index(cur)
        if not (0 <= i + d < len(anchors)):
            return
        fresh.after_scene_number = anchors[i + d]
        storage.update_object(fresh)
        receipt(f"↔️ moved **{fresh.name}** after scene {fresh.after_scene_number}"
                if fresh.after_scene_number else f"↔️ moved **{fresh.name}** to the front of the book")

    def save_beat_text(scene_id, panel_id, value):
        p = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                        "scene_id": scene_id, "panel_id": panel_id})
        if p is None:
            return
        p.beat = value or ""
        storage.update_object(p)
        receipt("✏️ penciled the panel")

    def save_scene_text(scene_id, value):
        sc = storage.read_object(SceneModel, {"series_id": series_id, "issue_id": issue_id,
                                              "scene_id": scene_id})
        if sc is None:
            return
        sc.story = value or ""
        storage.update_object(sc)
        receipt("✏️ rewrote the scene")

    def save_story_text(story_id, value):
        if story_id is None:                     # the issue's own script
            fresh = storage.read_object(Issue, {"series_id": series_id, "issue_id": issue_id})
            fresh.story = value or None
            storage.update_object(fresh)
        else:
            st = storage.read_object(Story, {"series_id": series_id, "issue_id": issue_id,
                                             "story_id": story_id})
            if st is None:
                return
            st.text = value or ""
            storage.update_object(st)
        receipt("✏️ rewrote the story")

    # ---- the tile: a panel living on a page ------------------------------
    # the page trim is 6.625 x 10.1875in; the 6x10 grid is the live area and
    # the difference breathes as margins, exactly like the printed page
    TRIM_W, TRIM_H = 6.625, 10.1875
    MX, MY = (TRIM_W - 6.0) / 2, (TRIM_H - 10.0) / 2

    def scene_menu(sc):
        """Everything a scene needs, hanging off its caption box."""
        with ui.menu():
            ui.menu_item('Open the scene — cast, setting, story',
                         on_click=lambda _, s=sc: goto(SelectedKind.SCENE, s.scene_id, s.name,
                                                       anchor=f'scene-{s.scene_id}'))
            ui.menu_item('Move the scene earlier', on_click=lambda _, s=sc: move_scene(s, -1))
            ui.menu_item('Move the scene later', on_click=lambda _, s=sc: move_scene(s, 1))
            ui.menu_item('Add a panel to this scene',
                         on_click=lambda _, s=sc: post_user_message(
                             state, f"Add another panel to scene '{s.name}'."))
            from gui.elements import reveal_in_files, reveal_label, reveal_object_target
            ui.menu_item(f"{reveal_label()} — the scene's files",
                         on_click=lambda _, s=sc: reveal_in_files(
                             reveal_object_target(storage, s)))
            ui.menu_item('Delete the scene…',
                         on_click=lambda _, s=sc: post_user_message(
                             state, f"I would like to delete scene '{s.name}'."))

    def tile(scene_id, panel_id, x, y, w, h, grid_h=10.0, cap_scene=None, mode='beats'):
        p = panel_of.get(panel_id)
        live_h = TRIM_H - 2 * MY
        box = (f'left: {(MX + x) / TRIM_W * 100:.2f}%; '
               f'top: {(MY + y / grid_h * live_h) / TRIM_H * 100:.2f}%; '
               f'width: {w / TRIM_W * 100:.2f}%; '
               f'height: {(h / grid_h * live_h) / TRIM_H * 100:.2f}%;')
        t = ui.element('div').classes('tile').style(box)
        t._props['data-banchor'] = f'panel-{panel_id}'

        def _beat_text():
            with ui.element('div').classes('tile-beat' + (' tile-beat--capped' if cap_scene else '')):
                txt = (p.beat or '').strip()
                ui.label(txt if txt else 'unwritten panel').classes(
                    'tile-beat__text' + ('' if txt else ' italic opacity-60'))

        with t:
            if p is None:
                ui.label('missing panel').classes('tile-beat text-xs text-gray-400')
            elif mode == 'roughs':
                # ROUGHS: the composed light-table rough of any panel that has
                # one — shown even when the proof is already inked
                from helpers.rough_face import rough_face
                rough = rough_face(storage, p, scene_by_id.get(scene_id))
                if rough:
                    ui.image(source=rough).props('fit=cover').classes('absolute inset-0 w-full h-full')
                    ui.label('ROUGH').classes('tile-rough-tag')
                else:
                    _beat_text()
            elif mode == 'proofs':
                # PROOFS: the inked proof if there is one, else a PLACEHOLDER —
                # never the rough (that lives in the ROUGHS view)
                if p.image and os.path.exists(p.image):
                    ui.image(source=p.image).props('fit=cover').classes('absolute inset-0 w-full h-full')
                else:
                    with ui.element('div').classes('tile-placeholder'):
                        ui.icon('image_not_supported').classes('tile-placeholder__icon')
                        ui.label('no proof yet').classes('tile-placeholder__label')
            else:
                # BEATS: just the beat, the words of the moment
                _beat_text()
            if cap_scene is not None:
                cap = ui.label(f'{cap_scene.scene_number} · {cap_scene.name}'.upper()).classes('tile-cap')
                with cap:
                    scene_menu(cap_scene)
                cap.on('click.stop', lambda _: None)
            if p is not None:
                # THE PENCIL is context-aware AND non-destructive: "Rough it"
                # shows ONLY while the panel has no rough — the instant one
                # exists the pencil becomes "Proof it" (in every view), so a
                # click can never clobber a rough.  PROOFS proofs even with no
                # rough (a take from the beat).  Rebuilding a rough from scratch
                # is the guarded "Re-rough" in the menu below.  Both fire the
                # light table's OWN action (build_table_flow / ink) via the
                # book -> board hop — one code path, no copy that can drift.
                _has_rough = bool(p.figure_images)
                if _has_rough or mode == 'proofs':
                    _icon, _tip = 'brush', 'Proof it — render a take on the light table'
                    _act = 'proof'
                else:
                    _icon, _tip = 'draw', 'Rough it — pose the acetates from the script'
                    _act = 'rough'

                def _go_board(act, sc=scene_id, pid=panel_id):
                    state._board_autorun = (act, pid)
                    open_scene_panel(sc, pid)

                def _pencil(act=_act):
                    _go_board(act)

                def _rerough(sc=scene_id, pid=panel_id, pnum=(p.panel_number if p else '?')):
                    # DESTRUCTIVE: rebuilding from the script re-poses the cast
                    # and re-lays the acetates — confirm before it happens.
                    from gui.elements import studio_dialog
                    with studio_dialog('Re-rough this panel?', min_w=360, max_w=460) as dlg:
                        ui.label(f'Panel {pnum} already has a rough.  Rebuilding from the '
                                 'script re-poses the cast and re-lays the acetates from the '
                                 'brief — anything you hand-arranged on this board is redrawn.') \
                            .classes('text-sm q-mt-sm')
                        with ui.row().classes('w-full justify-end q-mt-sm').style('gap: 8px;'):
                            ui.button('Keep the rough', icon='close').props('flat dense no-caps') \
                                .on('click', lambda _: dlg.close())
                            ui.button('Rebuild from script', icon='draw') \
                                .props('unelevated dense no-caps color=negative') \
                                .on('click', lambda _: (dlg.close(), _go_board('rough')))
                    dlg.open()

                with ui.row().classes('tile-tools items-center flex-nowrap'):
                    ui.button(icon=_icon).props('flat round dense size=xs') \
                        .tooltip(_tip).on('click.stop', lambda _, f=_pencil: f())
                    # EVERYTHING ELSE folds into ONE menu so the tools fit even a
                    # 2-unit-wide tile: shape, reorder, edit the script, tear it out.
                    more_btn = ui.button(icon='more_vert').props('flat round dense size=xs')
                    more_btn.tooltip('More — shape, reorder, edit the script, remove')
                    more_btn.on('click.stop', lambda *_: None)   # open the menu, not the panel
                    with more_btn:
                        with ui.menu().props('auto-close'):
                            # THE ONE SHAPE PICKER — the same control the
                            # panel's own page shows (gui/light_table.py)
                            from gui.light_table import shape_picker
                            shape_picker(state, storage, p, receipt=receipt)
                            ui.separator()
                            ui.menu_item('◂ Move earlier in the scene',
                                         on_click=lambda *_, s=scene_id, pid=panel_id:
                                         move_beat(s, pid, -1)).props('dense')
                            ui.menu_item('Move later in the scene ▸',
                                         on_click=lambda *_, s=scene_id, pid=panel_id:
                                         move_beat(s, pid, 1)).props('dense')
                            ui.menu_item('Edit the script…',
                                         on_click=lambda *_, s=scene_id, p=p: edit_text_dialog(
                                             f'Panel {p.panel_number} — {p.name}', p.beat,
                                             lambda v, s=s, pid=p.panel_id: save_beat_text(s, pid, v),
                                             f"Let's work on the script for panel {p.panel_number} "
                                             f"of this scene together.")).props('dense')
                            ui.separator()
                            if _has_rough:
                                ui.menu_item('Re-rough — rebuild from the script…',
                                             on_click=lambda *_, f=_rerough: f()).props('dense')
                            ui.menu_item('Tear this panel out of the book…',
                                         on_click=lambda *_, p=p: post_user_message(
                                             state, f"I would like to delete panel {p.panel_number} "
                                                    f"('{p.name}') of this scene.")).props('dense')
        if p is not None:
            t.tooltip(f"panel {p.panel_number}: {p.name or ''} — open its light table")
            t.on('click', lambda _, s=scene_id, pid=panel_id: open_scene_panel(s, pid))
        return t

    def cover_sheet(location):
        # AN INSIDE SLOT IS A FULL-PAGE SURFACE: a located insert (an ad,
        # the mailbag) prints here and beats cover art — its sheet renders
        # in place of the cover board
        if location in ('inside-front', 'inside-back'):
            _loc_ins = next((i for i in inserts_all
                             if getattr(i, 'location', None) == location), None)
            if _loc_ins is not None:
                _el = insert_sheet(_loc_ins)
                if _el is not None and location == 'inside-back':
                    _el.classes('book-col-1')
                return _el
        c = cover_at.get(location)
        # THE AUTHOR'S IMPOSITION: front+inside-front open the book as a
        # pair; inside-back+back close it — inside-back pins to column 1
        # so the final pair holds no matter the interior's parity (an odd
        # book leaves one quiet blank slot, like a real print run)
        classes = 'book-page' + (' book-col-1' if location == 'inside-back' else '')
        if c is not None:
            with ui.element('div').classes(classes + ('' if (c.image and os.path.exists(c.image))
                                                      else ' book-page--ghost')) as sh:
                if c.image and os.path.exists(c.image):
                    ui.image(source=c.image).props('fit=cover').classes('absolute inset-0 w-full h-full')
                else:
                    ui.label('bare board — open its light table').classes('page-ghost-hint')
                ui.label(location.replace('-', ' ').upper()).classes('page-cap')
            sh._props['data-banchor'] = f'cover-{location}'
            sh.tooltip(f"The {location.replace('-', ' ')} cover — open its light table")
            sh.on('click', lambda _: goto(SelectedKind.COVER, c.cover_id, f"{location} cover",
                                          anchor=f'cover-{location}'))
            return sh
        else:
            # EVERY SLOT GETS A DOOR — the inside covers too (they were
            # invisible: no way anywhere to create one)
            faint = '' if location in ('front', 'back') else ' book-page--ghost-faint'
            with ui.element('div').classes(classes + ' book-page--ghost' + faint) as sh:
                ui.label(f'+ {location.replace("-", " ")} cover').classes('page-ghost-cta')
            # the production dashboard's cover doors aim here even before
            # the cover exists — a ghost sheet still answers its anchor
            sh._props['data-banchor'] = f'cover-{location}'
            if location in ('front', 'back'):
                sh.tooltip('Every book needs one')
                sh.on('click', lambda _, loc=location: post_user_message(
                    state, f"I would like to create a {loc} cover for this issue."))
                return sh
            else:
                # AN INSIDE SLOT offers both of its real lives: cover art,
                # or a full-page insert (an ad, the mailbag) living there
                sh.tooltip('The indicia prints here unless you fill the slot'
                           if location == 'inside-front'
                           else 'The classic home for an ad or the mailbag')
                with sh:
                    with ui.menu().props('auto-close'):
                        ui.menu_item('Cover art here',
                                     on_click=lambda *_, loc=location: post_user_message(
                                         state, f"I would like to create a {loc} "
                                                f"cover for this issue.")).props('dense')
                        ui.separator()
                        for k, lbl in _INSERT_KINDS:
                            ui.menu_item(f'{lbl} here',
                                         on_click=lambda *_, k=k, loc=location:
                                         _make_insert(k, location=loc)).props('dense')
            return sh

    def footer_btn(icon, tip, handler):
        ui.button(icon=icon).props('flat round dense size=sm').tooltip(tip) \
            .on('click', handler)

    def story_sheet(story, first, last):
        """A story as a manuscript page.  story=None is the issue's own
        script (the legacy single story)."""
        sid = story.story_id if story else None
        name = story.name if story else 'THE SCRIPT'
        # the sheet cap says THE SCRIPT; messages to the Editor must name
        # the thing unambiguously — there is no story OBJECT called that
        spoken = f"the story '{story.name}'" if story else "this issue's own story (the issue script)"
        text = (story.text if story else issue.story) or ''
        wc = len(text.split())
        long_read = wc > 200
        with ui.element('div').classes('book-page book-page--script') as sh:
            ui.label(name.upper()).classes('page-cap')
            # THE BYLINE: each feature carries its own creative team.  The
            # issue's own script falls back to the issue-wide writer/artist.
            _w = (story.writer if story else None) or (issue.writer if not story else None)
            _a = (story.artist if story else None) or (issue.artist if not story else None)
            _l = (story.letterer if story else None)
            _parts = [('by', _w), ('art', _a), ('letters', _l)]
            byline = ui.row().classes('script-byline items-baseline flex-nowrap').style('gap: 6px;')
            with byline:
                if any(v for _r, v in _parts):
                    for role, val in _parts:
                        if val:
                            ui.label(f'{role} {val}')
                else:
                    ui.label('by — · art — · letters —').classes('unset')
            byline.tooltip('Set this story’s writer, artist and letterer')
            byline.on('click', lambda _, sp=spoken: post_user_message(
                state, f"I would like to set the writer, artist and letterer credits for {sp}."))
            with ui.element('div').classes('script-body' + (' script-clamp' if long_read else '')):
                if text:
                    ui.markdown(text).classes('script-text')
                else:
                    ui.label('This story has no words yet.').classes('page-ghost-hint q-mt-lg')
            if long_read:
                # the page never scrolls — the text fades like a real proof
                # and the door opens the whole manuscript
                ui.chip('continues — open to read', icon='auto_stories') \
                    .props('dense outline clickable size=sm').classes('script-continues') \
                    .on('click', lambda _, sid=sid, name=name, text=text, sp=spoken: edit_text_dialog(
                        name, text,
                        lambda v, sid=sid: save_story_text(sid, v),
                        f"Let's work on {sp} together — read it back "
                        f"to me and we'll edit it."))
            with ui.row().classes('script-foot items-center flex-nowrap').style('gap: 2px;'):
                if story is not None:
                    if not first:
                        footer_btn('chevron_left', 'Earlier in the book',
                                   lambda _, s=story: move_story(s, -1))
                    if not last:
                        footer_btn('chevron_right', 'Later in the book',
                                   lambda _, s=story: move_story(s, 1))
                footer_btn('edit', 'Rewrite the story',
                           lambda _, sid=sid, name=name, text=text, sp=spoken: edit_text_dialog(
                               name, text,
                               lambda v, sid=sid: save_story_text(sid, v),
                               f"Let's work on {sp} together — read it back "
                               f"to me and we'll edit it."))
                from gui.elements import reveal_in_files as _reveal, reveal_label as _rlabel, \
                    reveal_object_target as _rtarget
                footer_btn('folder_open', f'{_rlabel()} — the manuscript on disk',
                           lambda _, o=(story if story is not None else issue):
                           _reveal(_rtarget(storage, o)))
                if text and wc < 80:
                    ui.chip('develop it with me', icon='forum').props('dense outline clickable size=sm') \
                        .tooltip("It's thin — I'll interview you and we'll build it out") \
                        .on('click', lambda _, sp=spoken: post_user_message(
                            state, f"{sp.capitalize()} is too thin to break down — "
                                   f"interview me and help me develop it."))
                elif text and scenes_all:
                    # RE-BREAKING WITH SCENES ON THE BOOK is a merge, not a
                    # mint — the naive chip would double the book
                    ui.chip('re-break: update the scenes', icon='published_with_changes') \
                        .props('dense outline clickable size=sm') \
                        .tooltip(f"The book already has {len(scenes_all)} scenes — I'll read them "
                                 f"first and update in place (or replace, with your approval), "
                                 f"never mint duplicates") \
                        .on('click', lambda _, sp=spoken, sid=sid: post_user_message(
                            state, f"The script changed.  Read the existing scenes first, then "
                                   f"update {sp}'s breakdown IN PLACE to match — merge or "
                                   f"replace with my approval, never duplicate scenes."
                                   + (f"  Its scenes file under story_id '{sid}'." if sid else "")))
                elif text:
                    # file every new scene under THIS story so the dashboard's
                    # story→scene breakdown is right (the issue's own script
                    # needs no story_id — scenes default to it)
                    _file = f"  File every scene under story_id '{sid}'." if sid else ""
                    ui.chip('break into scenes', icon='view_agenda').props('dense outline clickable size=sm') \
                        .on('click', lambda _, sp=spoken, f=_file: post_user_message(
                            state, f"Break {sp} into scenes.{f}"))
                else:
                    ui.chip('write it with me', icon='forum').props('dense outline clickable size=sm') \
                        .on('click', lambda _: post_user_message(state, "Help me write the story for this issue."))
                ui.space()
                if story is not None:
                    footer_btn('close', 'Tear this story out…',
                               lambda _, s=story: post_user_message(
                                   state, f"I would like to delete the story '{s.name}'."))
                if last:
                    ui.chip('+ story', icon='add').props('dense outline clickable size=sm') \
                        .tooltip('Comics run backups — add another story') \
                        .on('click', lambda _: post_user_message(state, "Add another story to this issue."))
                    ui.chip('+ insert', icon='add_photo_alternate').props('dense outline clickable size=sm') \
                        .tooltip('A full-page insert: poster, ad, pin-up, the mailbag') \
                        .on('click', lambda _: post_user_message(
                            state, "Add a full-page insert to this issue — ask me what "
                                   "kind and where it goes."))
        sh._props['data-banchor'] = f'story-{sid or "script"}'

    def save_insert_description(insert_id, value):
        fresh = storage.read_object(Insert, {"series_id": series_id, "issue_id": issue_id,
                                             "insert_id": insert_id})
        if fresh is None:
            return
        fresh.description = value or ""
        storage.update_object(fresh)
        receipt("✏️ described the insert")

    _INSERT_KINDS = [('poster', 'A poster'), ('ad', 'An ad'),
                     ('pin-up', 'A pin-up'), ('mailbag', 'The mailbag')]
    _KIND_NAMES = {'poster': 'Poster', 'ad': 'Ad page',
                   'pin-up': 'Pin-up', 'mailbag': 'The Mailbag',
                   'page': 'Full page'}

    def _make_insert(kind: str, after_n: int = 0, location: str | None = None):
        # STAY PUT: the page appears in place — compose it when you like
        from uuid import uuid4
        ins = Insert(insert_id=f"{kind}-{uuid4().hex[:6]}", issue_id=issue_id,
                     series_id=series_id, kind=kind,
                     name=_KIND_NAMES.get(kind, kind.title()),
                     after_scene_number=after_n, location=location)
        storage.create_object(data=ins)
        where = (f"on the {location.replace('-', ' ')}" if location
                 else f"after scene {after_n}" if after_n else "at the front of the book")
        receipt(f"📄 laid a bare {kind} page {where} — click it to compose")
        state.refresh_details()

    def insert_door(after_n: int, host=None):
        """THE PAGE TURN'S DOOR (full pages belong to inserts, never the
        panel flow).  It rides ON the preceding sheet — a small transparent
        + at the page's bottom edge — so the grid never sees it and the
        two-up pairing cannot shift (the seam-div approach broke pairing
        twice: first as a cell, then as a full row)."""
        if host is None:
            return
        with host:
            bar = ui.element('div').classes('book-turn-bar')
            bar.tooltip('Add a full page here — it appears as a dotted '
                        'placeholder: drop art on it, or click it to compose')
            bar.on('click.stop', lambda _, n=after_n: _make_insert('page', after_n=n))

    def insert_sheet(ins):
        rendered = ins.image and os.path.exists(ins.image)
        has_text = bool((ins.description or '').strip())
        classes = 'book-page'
        if not rendered:
            classes += ' book-page--script' if has_text else ' book-page--ghost book-page--insert'
        with ui.element('div').classes(classes + ' cursor-pointer insert-drop-sheet') as sh:
            def _drop_art(e, i=ins):
                fresh = storage.read_object(Insert, i.primary_key)
                if fresh is None:
                    return
                locator = storage.upload_image(obj=fresh, name=e.name,
                                               data=e.content, mime_type=e.type)
                fresh.image = locator
                storage.update_object(fresh)
                receipt(f"🖼 dropped art onto **{fresh.name}** — the page wears it")
                state.refresh_details()
            ui.upload(on_upload=_drop_art, auto_upload=True, max_files=1) \
                .style('display: none;')
            if rendered:
                # the page wears the art WHOLE, its own shape kept — the same
                # scale-to-fit the binder prints (helpers.binder._fit_page), so
                # the sheet here is the sheet you read
                ui.image(source=ins.image).props('fit=contain').classes('absolute inset-0 w-full h-full')
            elif has_text:
                # a written page (the mailbag's letters, an ad's copy) reads
                # as manuscript until it's inked
                with ui.element('div').classes('script-body'):
                    ui.markdown(ins.description).classes('script-text')
            else:
                ui.icon({'poster': 'wallpaper', 'ad': 'storefront', 'pin-up': 'brush',
                         'mailbag': 'mail', 'title-page': 'title',
                         'page': 'note_add'}.get(ins.kind, 'wallpaper')) \
                    .classes('text-4xl').style('opacity: .5;')
                ui.label(ins.name).classes('page-ghost-cta')
            ui.label(f'{ins.kind} · {ins.name}'.upper()).classes('page-cap')
            foot = ui.row().classes('script-foot insert-foot items-center flex-nowrap').style('gap: 2px;')
            foot.on('click.stop', lambda _: None)   # the foot's own clicks stay in the foot
            with foot:
                if getattr(ins, 'location', None):
                    # a LOCATED page lives on a cover slot — scene arrows
                    # mean nothing here; one door back to the page turns
                    def _eject(i=ins):
                        fresh = storage.read_object(Insert, i.primary_key)
                        if fresh is None:
                            return
                        fresh.location = None
                        fresh.after_scene_number = 0
                        storage.update_object(fresh)
                        receipt(f"↔️ moved **{fresh.name}** off the cover slot — "
                                f"it rides the page turns now")
                        state.refresh_details()
                    footer_btn('logout', 'Move it off this cover slot — back to the page turns',
                               lambda _, i=ins: _eject(i))
                else:
                    footer_btn('chevron_left', 'Earlier in the book (previous scene)',
                               lambda _, i=ins: move_insert(i, -1))
                    footer_btn('chevron_right', 'Later in the book (next scene)',
                               lambda _, i=ins: move_insert(i, 1))
                footer_btn('edit', 'Edit this page on the lightboard',
                           lambda _, i=ins: goto(SelectedKind.INSERT, i.insert_id,
                                                 i.name, anchor=f'insert-{i.insert_id}'))
                footer_btn('notes', 'Write the page — its words and what it shows',
                           lambda _, i=ins: edit_text_dialog(
                               f'{i.kind} — {i.name}', i.description,
                               lambda v, iid=i.insert_id: save_insert_description(iid, v),
                               f"Let's work on the '{i.name}' insert together."))
                if not rendered:
                    def _ink_page(i=ins):
                        # the page proofs through the QUEUE like every board
                        from agentic.tools.imaging import generate_insert_art_body
                        from helpers.render_queue import enqueue_renders
                        enqueue_renders(state, [(
                            f"inking the '{i.name}' page",
                            lambda _i=i: generate_insert_art_body(
                                state, series_id, issue_id, _i.insert_id),
                            lambda _r: state.refresh_details(),
                        )], role='the Production Artist')
                    footer_btn('brush', 'Ink it — render the page as full art (rides the queue)',
                               lambda _, i=ins: _ink_page(i))
                ui.space()
                def _strike_insert(i=ins):
                    from gui.strike import strike
                    from agentic.tools.deleter import delete_insert as _del_ins
                    return strike(state, _del_ins,
                                  {"series_id": series_id, "issue_id": issue_id,
                                   "insert_id": i.insert_id},
                                  f"the '{i.name}' {i.kind}")
                footer_btn('close', 'Tear this page out (it waits in the wastebasket)',
                           lambda _, i=ins: _strike_insert(i))
        # the page IS a board: click it to open its light table
        sh.tooltip(f"The {ins.kind} — open it on the light table")
        sh.on('click', lambda _, i=ins: goto(SelectedKind.INSERT, i.insert_id, i.name,
                                             anchor=f'insert-{i.insert_id}'))
        sh._props['data-banchor'] = f'insert-{ins.insert_id}'
        return sh

    def scene_production_strip(sc):
        """The scene's production line — setting, cast, props — editable right
        on its manuscript page.  (This used to be the scene's own page; the
        scene lives in the book now, so its production rides here.)"""
        from schema import Setting, CharacterVariant, PropAsset, CharacterModel, CharacterRef
        from gui.elements import removable_chips_inline
        panels = panels_by_scene.get(sc.scene_id, [])
        setting_obj = storage.read_object(cls=Setting, primary_key={
            "series_id": series_id, "setting_id": sc.setting_id}) if sc.setting_id else None

        def _series_base():
            idx = next((i for i, s in enumerate(state.selection)
                        if s.kind.value == 'series'), None)
            return state.selection[:idx + 1] if idx is not None else state.selection

        def _visit_character(key):
            cid = key.split('/', 1)[0]
            ch = roster.get(cid)
            state.change_selection(new=[*_series_base(),
                SelectionItem(name=(ch.name if ch else cid), id=cid, kind=SelectedKind.CHARACTER)])

        def _visit_setting(_key):
            state.change_selection(new=[*_series_base(),
                SelectionItem(name=setting_obj.name, id=setting_obj.setting_id,
                              kind=SelectedKind.SETTING)])

        def _save():
            storage.update_object(data=sc)

        def _remove_setting(_key):
            sc.setting_id = None; _save()

        def _remove_cast(key):
            sc.cast = [c for c in sc.cast if f"{c.character_id}/{c.variant_id}" != key]
            _save()

        def _todo(label, fix_message):
            chip = ui.chip(label, icon='radio_button_unchecked', color='orange').props('dense clickable')
            chip.tooltip("Click and I'll get started")
            chip.on('click', lambda _, m=fix_message: post_user_message(state, m))

        def pick_setting():
            from gui.elements import studio_dialog
            with studio_dialog('Set the scene', min_w=480, max_w=720) as dlg:
                with ui.row().classes('w-full q-mt-sm').style('gap: 8px;'):
                    for s in storage.read_all_objects(Setting, primary_key={"series_id": series_id}, order_by="name"):
                        img = next((i for i in (s.images or {}).values() if i and os.path.exists(i)), None)
                        with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 150px;') as card:
                            if img:
                                ui.image(source=img).style('height: 80px;').props('fit=cover')
                            ui.label(s.name.title()).classes('text-xs text-center w-full')

                        def choose(s=s):
                            sc.setting_id = s.setting_id
                            storage.update_object(sc)
                            receipt(f"🏔 set the scene in **{s.name}**")
                            dlg.close(); state.refresh_details()
                        card.on('click', lambda _, s=s: choose(s))
                ui.button('A brand-new setting instead…', icon='add') \
                    .props('flat dense no-caps').classes('q-mt-sm') \
                    .on('click', lambda _: (dlg.close(), post_user_message(
                        state, f"I would like to create a new setting for scene '{sc.name}'.")))
            dlg.open()

        def _cast_label(c):
            nm = roster[c.character_id].name if c.character_id in roster else c.character_id
            if (c.variant_id or "base") == "base":
                return nm
            v = storage.read_object(CharacterVariant, {
                "series_id": series_id, "character_id": c.character_id, "variant_id": c.variant_id})
            return f"{nm} · {(v.name if v is not None and v.name else c.variant_id)}"

        def pick_cast():
            # CAST FROM THE ASSET SELECTOR: pick the character AND the wardrobe
            # (variant) they wear here — this is the cast the render uses, so no
            # variant is ever guessed.
            already = {(c.character_id, c.variant_id) for c in (sc.cast or [])}
            from gui.elements import studio_dialog
            with studio_dialog('Cast a character in this scene', min_w=480, max_w=760) as dlg:
                ui.label('Pick the character AND the wardrobe (variant) they wear here — '
                         'the render dresses them exactly as cast.') \
                    .classes('text-xs text-gray-500 q-mt-xs')
                any_left = False
                with ui.row().classes('w-full q-mt-sm').style('gap: 8px; flex-wrap: wrap;'):
                    for ch in storage.read_all_objects(CharacterModel,
                                                       primary_key={"series_id": series_id}, order_by="name"):
                        for v in storage.read_all_objects(CharacterVariant,
                                                          primary_key={"series_id": series_id,
                                                                       "character_id": ch.character_id}):
                            if (ch.character_id, v.id) in already:
                                continue
                            any_left = True
                            img = storage.find_variant_image(series_id=series_id,
                                                             character_id=ch.character_id, variant_id=v.id)
                            vname = getattr(v, 'name', None) or v.id
                            with ui.card().classes('soft-card p-1 cursor-pointer').style('width: 130px;') as card:
                                if img and os.path.exists(img):
                                    ui.image(source=img).style('height: 70px;').props('fit=contain')
                                ui.label(f"{ch.name.title()} · {vname}").classes('text-xs text-center w-full')

                            def choose(ch=ch, v=v, vname=vname):
                                fs = storage.read_object(type(sc), sc.primary_key) or sc
                                fs.cast = (fs.cast or []) + [CharacterRef(
                                    series_id=series_id, character_id=ch.character_id, variant_id=v.id)]
                                storage.update_object(fs)
                                receipt(f"🎭 cast **{ch.name}** ({vname}) in the scene")
                                dlg.close(); state.refresh_details()
                            card.on('click', lambda _, ch=ch, v=v, vname=vname: choose(ch, v, vname))
                if not any_left:
                    ui.label('Every wardrobe is already cast in this scene.') \
                        .classes('text-sm text-gray-500 q-mt-sm')
                ui.button('A brand-new character or look instead…', icon='add') \
                    .props('flat dense no-caps').classes('q-mt-sm') \
                    .on('click', lambda _: (dlg.close(), post_user_message(
                        state, f"I would like to cast a new character (or a new wardrobe) "
                               f"for scene '{sc.name}'.")))
            dlg.open()

        with ui.row().classes('scene-prod w-full items-center').style('gap: 6px; flex-wrap: wrap;'):
            ui.label('Production').classes('comic-label-sm')
            if not sc.setting_id:
                chip = ui.chip('setting', icon='location_on', color='orange').props('dense clickable')
                chip.tooltip('Pick where this scene is set — one click')
                chip.on('click', lambda _: pick_setting())
            # CAST: pick characters + wardrobe right here (amber until someone's
            # cast) — the render uses exactly this cast.
            _cast_chip = ui.chip('cast' if not sc.cast else '+ cast', icon='person_add',
                                 color='orange' if not sc.cast else None).props('dense clickable')
            _cast_chip.tooltip('Cast a character in this scene — pick their wardrobe')
            _cast_chip.on('click', lambda _: pick_cast())
            if not panels:
                _todo('panels', f"Break scene '{sc.name}' into panels.")
            if setting_obj:
                removable_chips_inline(state, [(setting_obj.setting_id, setting_obj.name)],
                                       _remove_setting, icon='location_on', visit=_visit_setting)
            removable_chips_inline(state,
                [(f"{c.character_id}/{c.variant_id}", _cast_label(c)) for c in (sc.cast or [])],
                _remove_cast, icon='theater_comedy', visit=_visit_character)

    def scene_sheet(sc, folio=None):
        """A scene holding its place as a manuscript page."""
        panels = panels_by_scene[sc.scene_id]
        text = sc.story or ''
        wc = len(text.split())
        with ui.element('div').classes('book-page book-page--script') as sh:
            cap = ui.label(f'{sc.scene_number} · {sc.name}'.upper()).classes('page-cap')
            with cap:
                scene_menu(sc)
            cap.on('click.stop', lambda _: None)
            long_read = wc > 200
            with ui.element('div').classes('script-body' + (' script-clamp' if long_read else '')):
                if text:
                    ui.markdown(text).classes('script-text')
                else:
                    ui.label('Nothing written for this scene yet.').classes('page-ghost-hint q-mt-lg')
            if long_read:
                ui.chip('continues — open to read', icon='auto_stories') \
                    .props('dense outline clickable size=sm').classes('script-continues') \
                    .on('click', lambda _, s=sc: edit_text_dialog(
                        f'Scene {s.scene_number} — {s.name}', s.story,
                        lambda v, sid=s.scene_id: save_scene_text(sid, v),
                        f"Let's work on scene '{s.name}' together — read it back to "
                        f"me and we'll develop it."))
            # THE SCENE'S PRODUCTION LINE, right on its page — setting, cast,
            # props (no separate scene page anymore)
            scene_production_strip(sc)
            with ui.row().classes('script-foot items-center flex-nowrap').style('gap: 2px;'):
                footer_btn('chevron_left', 'Earlier in the book', lambda _, s=sc: move_scene(s, -1))
                footer_btn('chevron_right', 'Later in the book', lambda _, s=sc: move_scene(s, 1))
                footer_btn('edit', 'Rewrite the scene',
                           lambda _, s=sc: edit_text_dialog(
                               f'Scene {s.scene_number} — {s.name}', s.story,
                               lambda v, sid=s.scene_id: save_scene_text(sid, v),
                               f"Let's work on scene '{s.name}' together — read it back to "
                               f"me and we'll develop it."))
                if panels:
                    # at panels detail this scene lives as tiles — anchor on
                    # its first panel, which always exists there
                    ui.chip(f'{len(panels)} panels', icon='grid_on').props('dense outline clickable size=sm') \
                        .tooltip('See the panels on the page') \
                        .on('click', lambda _, ps=panels: (remember_spot(f'panel-{ps[0].panel_id}'),
                                                           set_detail('beats')))
                elif text and wc < 25:
                    ui.chip('develop it with me', icon='forum').props('dense outline clickable size=sm') \
                        .tooltip("It's thin — I'll interview you and we'll build it out") \
                        .on('click', lambda _, s=sc: post_user_message(
                            state, f"Scene '{s.name}' is too thin to panelize — interview me "
                                   f"and help me develop it."))
                else:
                    ui.chip('break it into panels', icon='grid_on').props('dense outline clickable size=sm') \
                        .tooltip("I'll break this scene into panels — they flow onto these pages") \
                        .on('click', lambda _, s=sc: post_user_message(
                            state, f"Break scene '{s.name}' into panels."))
                # THE SCENE'S STYLE, on its card: the swatch every panel here
                # prints in — click to swap it
                from gui.light_table import style_swatch as _scene_style_swatch
                _scene_style_swatch(state, sc)
                ui.space()
                footer_btn('close', 'Tear this scene out…',
                           lambda _, s=sc: post_user_message(
                               state, f"I would like to delete scene '{s.name}'."))
            if folio is not None:
                ui.label(str(folio)).classes('page-folio')
        sh._props['data-banchor'] = f'scene-{sc.scene_id}'
        return sh
    def slip_sheet(scs):
        """MANUSCRIPT SLIPS: a run of bare scenes clipped to one sheet as
        working paper — each slip carries its own cap, words and tools."""
        with ui.element('div').classes('book-page book-page--script book-page--slips') as sh:
            for sc in scs:
                text = sc.story or ''
                wc = len(text.split())
                slip = ui.element('div').classes('page-slip')
                slip._props['data-banchor'] = f'scene-{sc.scene_id}'
                with slip:
                    cap = ui.label(f'{sc.scene_number} · {sc.name}'.upper()).classes('page-cap')
                    with cap:
                        scene_menu(sc)
                    cap.on('click.stop', lambda _: None)
                    with ui.element('div').classes('slip-body'):
                        if text:
                            ui.markdown(text).classes('script-text')
                        else:
                            ui.label('Nothing written for this scene yet.') \
                                .classes('page-ghost-hint')
                    if wc > 60:
                        # a slip is a third of a page — every fade gets a door
                        ui.chip('continues — open to read', icon='auto_stories') \
                            .props('dense outline clickable size=sm').classes('script-continues') \
                            .on('click', lambda _, s=sc: edit_text_dialog(
                                f'Scene {s.scene_number} — {s.name}', s.story,
                                lambda v, sid=s.scene_id: save_scene_text(sid, v),
                                f"Let's work on scene '{s.name}' together — read it "
                                f"back to me and we'll develop it."))
                    with ui.row().classes('script-foot items-center flex-nowrap').style('gap: 2px;'):
                        footer_btn('edit', 'Rewrite the scene',
                                   lambda _, s=sc: edit_text_dialog(
                                       f'Scene {s.scene_number} — {s.name}', s.story,
                                       lambda v, sid=s.scene_id: save_scene_text(sid, v),
                                       f"Let's work on scene '{s.name}' together — read it "
                                       f"back to me and we'll develop it."))
                        if text and wc >= 25:
                            ui.chip('break it into panels', icon='grid_on') \
                                .props('dense outline clickable size=sm') \
                                .on('click', lambda _, s=sc: post_user_message(
                                    state, f"Break scene '{s.name}' into panels."))
                        else:
                            ui.chip('develop it with me', icon='forum') \
                                .props('dense outline clickable size=sm') \
                                .tooltip("It's thin — I'll interview you and we'll build it out") \
                                .on('click', lambda _, s=sc: post_user_message(
                                    state, f"Scene '{s.name}' is too thin to panelize — "
                                           f"interview me and help me develop it."))
                        ui.space()
                        footer_btn('close', 'Tear this scene out…',
                                   lambda _, s=sc: post_user_message(
                                       state, f"I would like to delete scene '{s.name}'."))
        return sh
    def open_layout_dialog(ordered_panel_ids):
        """THE LAYOUT SWATCH BOOK: every exact-fill layout for this page's
        panel count, as printer's swatches — pick one and the panels take
        its shapes in reading order (the book reflows around them)."""
        from helpers.tilings import swatches_for, PIECE_PANEL, W as TW, H as TH
        panels = [panel_of[pid] for pid in ordered_panel_ids if pid in panel_of]
        n = len(panels)
        swatches = swatches_for(n)
        from gui.elements import studio_dialog
        with studio_dialog(f'THE SWATCH BOOK — {n}-PANEL PAGES', min_w=560, max_w=860) as dlg:
            if not swatches:
                ui.label(f"No exact-fill layout tiles a page with {n} panels — "
                         f"exact fills exist for 4 to 15.  Add or remove a panel, "
                         f"or let the book keep flowing.").classes('text-sm q-mt-sm')
            else:
                ui.label(f"{len(swatches)} layouts fill the page exactly.  Pick one — "
                         f"these panels take its shapes in reading order and the "
                         f"book reflows.").classes('text-sm q-mt-sm')

            def apply(tiling):
                # THE PINNED PAGE: the picked swatch is written VERBATIM as
                # the page's cells and pinned — the stitcher reflows the
                # rest of the book around it, never through it
                from helpers.stitcher import pin_page_layout
                pin_page_layout(storage, series_id, issue_id, panels, tiling['pieces'])
                dlg.close()
                receipt(f"📌 pinned this page to a swatch layout — {n} panels hold "
                        f"exactly these shapes; the book flows around them")

            with ui.row().classes('q-mt-sm').style('gap: 10px; flex-wrap: wrap; '
                                                   'max-height: 60vh; overflow-y: auto;'):
                for sw in swatches:
                    card = ui.element('div').classes('layout-swatch')
                    with card:
                        for x, y, w, h in sw['pieces']:
                            ui.element('div').classes('layout-swatch__piece').style(
                                f'left: {x / TW * 100:.1f}%; top: {y / TH * 100:.1f}%; '
                                f'width: {w / TW * 100:.1f}%; height: {h / TH * 100:.1f}%;')
                    card.tooltip('Shape the page to this layout')
                    card.on('click', lambda _, sw=sw: apply(sw))
        dlg.open()

    def open_layout_feel():
        # THE LAYOUT KNOBS: steer the auto-flow's feel for the whole book.  Each
        # dial persists as you release it; 'Reflow' re-stitches with the new feel.
        from schema import Issue as _Issue
        fresh = storage.read_object(_Issue, {"series_id": series_id, "issue_id": issue_id}) or issue
        lf = fresh.layout_feel
        from gui.elements import studio_dialog
        with studio_dialog('Layout feel — the whole book', min_w=440) as dlg:
            ui.label('Steers how the auto-flow lays out unlocked panels.  '
                     'Locked panels always keep their shape.') \
                .classes('text-xs text-gray-500 q-mb-sm')

            # LAYOUT BY SCENE ↔ CONTINUOUS: whether a scene may share a page with
            # the next, or each scene flows into its own pages.
            def _set_by_scene(e):
                fi = storage.read_object(_Issue, {"series_id": series_id,
                                                  "issue_id": issue_id}) or fresh
                fi.layout_by_scene = bool(e.value)
                storage.update_object(fi)
            with ui.row().classes('w-full items-center q-mb-sm').style('gap: 8px;'):
                ui.switch('Layout by scene', value=bool(getattr(fresh, 'layout_by_scene', False)),
                          on_change=_set_by_scene).props('dense')
                ui.label('— each scene flows into its own pages (off = continuous across scenes)') \
                    .classes('text-xs text-gray-500')

            def knob(name, left, right):
                with ui.row().classes('w-full items-center flex-nowrap').style('gap: 8px;'):
                    ui.label(left).classes('text-xs text-gray-500') \
                        .style('width: 88px; text-align: right;')
                    sl = ui.slider(min=-1, max=1, step=0.1, value=getattr(lf, name)) \
                        .props('label-always snap').classes('col')

                    def _set(e, name=name):
                        fi = storage.read_object(_Issue, {"series_id": series_id,
                                                          "issue_id": issue_id}) or fresh
                        setattr(fi.layout_feel, name, round(float(e.args), 2))
                        storage.update_object(fi)
                    sl.on('change', _set)
                    ui.label(right).classes('text-xs text-gray-500').style('width: 88px;')

            knob('density', 'few big', 'many small')
            knob('verticality', 'wide', 'tall')
            knob('irregularity', 'grid', 'dynamic')
            knob('variety', 'calm', 'restless')
            with ui.row().classes('w-full justify-end q-mt-md').style('gap: 8px;'):
                ui.button('Close', icon='close').props('flat no-caps') \
                    .on('click', lambda _: dlg.close())
                ui.button('Reflow the book', icon='auto_awesome').props('unelevated no-caps') \
                    .on('click', lambda _: (dlg.close(), state.refresh_details()))
        dlg.open()

    with details:
        # ---- the masthead stays put over the table ------------------------
        # THE TITLE RULES THE MASTHEAD: the issue's name reads on its own
        # line, ABOVE the swatch and the dial — like a real masthead
        with ui.column().classes('book-masthead w-full').style('gap: 4px;') as _mast:
            _mast._props['data-banchor'] = 'masthead-top' 
            header(f"ISSUE {issue.issue_number}: {issue.name}", 0)
            with ui.row().classes('w-full flex-nowrap items-center').style('gap: 12px;'):
                from gui.light_table import style_swatch
                style_swatch(state, issue, shared_with='the whole issue')
                # THE DETAIL DIAL: read the book at five altitudes — scripts,
                # scenes, beats (the text), roughs (the composed pencils), proofs
                # (the bound book).  The production truth lives on the colophon now.
                with ui.row().classes('items-center flex-nowrap').style('gap: 4px;'):
                    for key, label, hint in (('stories', 'SCRIPTS', 'the written scripts'),
                                             ('scenes', 'SCENES', 'scene manuscript pages'),
                                             ('beats', 'BEATS', 'the beat of every panel, laid out'),
                                             ('roughs', 'ROUGHS', 'the composed rough of every panel that has one'),
                                             ('proofs', 'PROOFS', 'the inked panels; the rest as placeholders')):
                        chip = ui.element('div').classes('dial-chip' + (' dial-chip--on' if detail == key else ''))
                        chip.mark(f'detail-{key}')
                        with chip:
                            ui.label(label)
                        chip.tooltip(f'Read the book as {hint}')
                        chip.on('click', lambda _, k=key: set_detail(k))
                ui.space()
                ui.button(icon='tune').props('flat round dense') \
                    .tooltip('Layout feel — density, verticality, irregularity, variety') \
                    .on('click', lambda _: open_layout_feel())
                ui.button('Read', icon='menu_book').props('rounded') \
                    .tooltip('Read the issue front to back') \
                    .on('click', lambda _: ui.run_javascript(
                        f"window.open('/series/{series_id}/issue/{issue_id}/read', '_blank');"))
                crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current issue."))

        # ---- THE OPEN BOOK ------------------------------------------------
        # THE BOOK sizes itself to the bookroom (the details pane is a CSS
        # container), so a narrow pane stacks single pages instead of clipping
        with ui.element('div').classes('book w-full'):
            # THE ADVISORY BANNER: when a lock config can't tile, the flow falls
            # back to bands so the book still binds — say so, non-blocking, with
            # the reason and the fix.
            try:
                from helpers.stitcher import layout_note
                _lnote = layout_note(series_id, issue_id)
            except Exception:
                _lnote = None
            if _lnote:
                with ui.element('div').style(
                        'margin: 0 auto 12px; max-width: 640px; padding: 8px 14px; '
                        'border-radius: 8px; display: flex; gap: 8px; align-items: center; '
                        'font-size: 13px; background: rgba(230,160,30,.14); '
                        'border: 1px solid rgba(230,160,30,.5);'):
                    ui.icon('report_problem').style('color: #b8860b;')
                    ui.label(f"Couldn't make an exact-fill layout — {_lnote}  "
                             f"Showing a flowed layout meanwhile; release a lock or move a "
                             f"panel to fix it.")
            # PROOFS is a per-panel altitude now (not the bound reading room):
            # its tiles show the inked proof or a placeholder, and click opens
            # the light board — just like BEATS and ROUGHS.  The bound spreads
            # live behind the 'Read' button.
            cover_sheet('front')
            _if_sheet = cover_sheet('inside-front')

            # THE STORIES: the issue's own script, then the backups, in order.
            # Once a story has been expanded into scenes it steps back — the
            # scenes ARE the story now; the STORIES dial reads it any time.
            # the issue's own script sheet also opens the book when UNFILED
            # scenes shelter under it — the dashboard emits its row then, and
            # a door must never point at a sheet that isn't printed
            _real_story_ids = {st.story_id for st in stories_all}
            _unfiled = any(sc.story_id not in _real_story_ids for sc in scenes_all)
            stories = ([None] if issue.story or _unfiled or not stories_all else []) + stories_all
            if detail == 'stories' or not scenes_all:
                for i, st in enumerate(stories):
                    # ‹ › move only among the REAL stories — the issue's own
                    # script always opens the book
                    is_first = st is None or not stories_all or st.story_id == stories_all[0].story_id
                    story_sheet(st, first=bool(is_first), last=(i == len(stories) - 1))

            # located inserts (inside-front / inside-back) print on their
            # cover slot, never at a page turn
            inserts_by_anchor = {}
            for ins in inserts_all:
                if getattr(ins, 'location', None):
                    continue
                inserts_by_anchor.setdefault(ins.after_scene_number, []).append(ins)
            _door_host = _if_sheet if hasattr(_if_sheet, 'classes') else None
            for ins in inserts_by_anchor.get(0, []):
                _door_host = insert_sheet(ins)
            insert_door(0, host=_door_host)

            if detail == 'scenes':
                # every scene as a manuscript page, in order, inserts slotted in
                for sc in scenes_all:
                    _h = scene_sheet(sc)
                    for ins in inserts_by_anchor.get(sc.scene_number, []):
                        _h = insert_sheet(ins)
                    insert_door(sc.scene_number, host=_h)
            elif detail in ('beats', 'roughs', 'proofs'):
                # THE BOOK FLOWS CONTINUOUSLY: beats pack across page turns the
                # way text reflows across lines — turning, resizing, or moving
                # a panel carries neighbors onto the next or previous page.
                # Bare scenes and inserts hold their place as full pages.  The
                # SAME layout serves both altitudes — BEATS fills each tile with
                # the beat's words, ROUGHS with the composed pencils.
                from helpers.stitcher import flow_run, AR, resolve_layout_feel
                _by_scene = bool(getattr(issue, 'layout_by_scene', False))
                segments, run = [], []

                def flush():
                    nonlocal run
                    if run:
                        segments.append(('flow', run))
                        run = []
                for sc in scenes_all:
                    panels = panels_by_scene[sc.scene_id]
                    if panels:
                        # (key, AR float, size, aspect NAME, locked, feel) —
                        # flow_run reads [3:]; the feel steers the exact-fill flow
                        feel = resolve_layout_feel(issue, sc)
                        run += [((sc.scene_id, p.panel_id), AR.get(p.aspect.value, 1.5),
                                 getattr(p, 'size', None) or '1x',
                                 p.aspect.value, bool(getattr(p, 'shape_locked', False)), feel)
                                for p in panels]
                        if _by_scene:
                            flush()   # each scene flows into its OWN pages
                    else:
                        flush()
                        segments.append(('manuscript', sc))
                    for ins in inserts_by_anchor.get(sc.scene_number, []):
                        flush()
                        segments.append(('insert', ins))
                    # THE DOOR ONLY AT A SEAM: panels flow continuously
                    # across scenes, so a mid-run boundary is not a page
                    # turn — the slip appears where the book already
                    # breaks (after a bare scene or an existing insert),
                    # and placing an insert CREATES the seam
                    if not run:
                        segments.append(('turn-door', sc.scene_number))
                flush()

                # MANUSCRIPT SLIPS: at panels altitude, a run of bare scenes
                # packs 2–3 slips to a sheet — working paper clipped into the
                # book, not seventeen full pages of it.  (At SCENES detail
                # every scene still gets its own manuscript page.)
                packed, slips = [], []

                def flush_slips():
                    nonlocal slips
                    while slips:
                        take, wc = [], 0
                        while slips and len(take) < 3:
                            w = len((slips[0].story or '').split())
                            if take and len(take) >= 2 and wc + w > 120:
                                break
                            take.append(slips.pop(0))
                            wc += w
                        packed.append(('slips', take))
                for kind, seg in segments:
                    if kind == 'manuscript':
                        slips.append(seg)
                    elif kind == 'turn-door' and slips:
                        continue   # doors fold into a running slip wall
                    else:
                        flush_slips()
                        packed.append((kind, seg))
                flush_slips()
                segments = packed

                first_tiles = {ps[0].panel_id: sc for sc in scenes_all
                               for ps in [panels_by_scene[sc.scene_id]] if ps}
                folio = 0
                from helpers.stitcher import alive_pins, flow_with_pins
                pins = alive_pins(storage, series_id, issue_id)
                pins_emitted = set()

                def release_pin(pm):
                    from helpers.stitcher import unpin_page
                    unpin_page(storage, pm)
                    receipt("📌 released the pin — the page rejoins the flow")

                def flow_sheet(cells, grid_h, pinned_pm=None):
                    nonlocal folio
                    folio += 1
                    with ui.element('div').classes('book-page') as sheet:
                        for key, x, y, w, h in cells:
                            tile(key[0], key[1], x, y, w, h, grid_h,
                                 cap_scene=first_tiles.get(key[1]), mode=detail)
                        ui.label(str(folio)).classes('page-folio')
                        ordered = [k[1] for k, x, y, _w, _h in sorted(
                            ((k, x, y, w2, h2) for k, x, y, w2, h2 in cells),
                            key=lambda c: (c[2], c[1]))]
                        with ui.row().classes('page-tools items-center'):
                            if pinned_pm is not None:
                                # THE PIN, visible and releasable right here
                                ui.button(icon='push_pin') \
                                    .props('flat round dense size=xs') \
                                    .tooltip('This page holds its swatch layout — '
                                             'click to release the pin and let it reflow') \
                                    .on('click.stop', lambda _, pm=pinned_pm: release_pin(pm))
                            ui.button(icon='dashboard_customize') \
                                .props('flat round dense size=xs') \
                                .tooltip('The swatch book — exact-fill layouts for this page') \
                                .on('click.stop', lambda _, o=ordered: open_layout_dialog(o))
                    sheet._props['data-banchor'] = f'flow-{folio}'

                for kind, seg in segments:
                    if kind == 'flow':
                        # PINNED PAGES hold their exact cells; the rest of
                        # the run flows around them — screen and print agree
                        for pkind, part in flow_with_pins(seg, pins, pins_emitted):
                            if pkind == 'pinned':
                                flow_sheet([((c.scene_id, c.panel_id), c.x, c.y, c.w, c.h)
                                            for c in part.cells],
                                           max(10.0, max(c.y + c.h for c in part.cells)),
                                           pinned_pm=part)
                                continue
                            # THE ONE FLOW: exact-fill (band fallback) — the same
                            # helper the print binder uses, so screen and book agree
                            run_pages, _note = flow_run(part)
                            for cells, grid_h in run_pages:
                                flow_sheet(cells, grid_h)
                    elif kind == 'slips':
                        # bare scenes hold their place but don't PRINT —
                        # no folio, so screen and book agree on page numbers
                        _last_sheet = slip_sheet(seg)
                    elif kind == 'turn-door':
                        insert_door(seg, host=_last_sheet)
                    else:
                        _last_sheet = insert_sheet(seg)

            # inserts whose anchor no longer matches a scene must never
            # vanish out of reach — they wait at the back of the book
            valid_anchors = {0} | {sc.scene_number for sc in scenes_all}
            for ins in inserts_all:
                if ins.after_scene_number not in valid_anchors:
                    insert_sheet(ins)

            cover_sheet('inside-back')
            cover_sheet('back')

            # THE COLOPHON: credits, downloads, the production small print
            with ui.element('div').classes('book-page book-page--script') as colophon_sheet:
                colophon_sheet._props['data-banchor'] = 'colophon'
                ui.label('COLOPHON').classes('page-cap')
                with ui.element('div').classes('script-body'):
                    # THE ISSUE INDICIA: the book-wide credits.  An anthology
                    # runs each story with its OWN writer/artist/letterer (those
                    # print in the dashboard below, per story) — the issue keeps
                    # the masthead credits every feature shares.
                    with ui.element('div').classes('colophon-credits q-mt-md'):
                        for role, val in (("creative minds", issue.creative_minds),
                                          ("publication date", issue.publication_date),
                                          ("price", f"${issue.price:.2f}" if issue.price is not None else None)):
                            line = ui.row().classes('credit-line items-baseline flex-nowrap')
                            with line:
                                ui.label(role.upper()).classes('credit-role')
                                ui.label(str(val) if val else 'unset — pencil it in') \
                                    .classes('credit-name' + ('' if val else ' credit-name--unset'))
                            line.tooltip(f'Set the {role}')
                            line.on('click', lambda _, r=role: post_user_message(
                                state, f"I would like to edit the {r}."))
                    with ui.row().classes('q-mt-md items-center').style('gap: 6px; flex-wrap: wrap;'):
                        # ANY bound file counts, and a stale one SAYS so —
                        # never hand out yesterday's book unwarned
                        import glob as _glob
                        import json as _json
                        import time as _time
                        from helpers.binder import book_signature
                        _cur_sig = None
                        for ext, label in (('pdf', '⤓ PDF'), ('cbz', '⤓ CBZ')):
                            found = sorted(_glob.glob(os.path.join(export_dir, f'*.{ext}')),
                                           key=os.path.getmtime, reverse=True)
                            if not found:
                                continue
                            path = found[0]
                            stale, bound_at, unknown = False, None, False
                            try:
                                meta = _json.load(open(path + '.meta.json'))
                                bound_at = meta.get('bound_at')
                                if _cur_sig is None:
                                    _cur_sig = book_signature(storage, series_id, issue_id)
                                stale = meta.get('sig') != _cur_sig
                            except Exception:
                                unknown = True   # a bind without papers can't claim currency
                            when = (_time.strftime('%b %d, %H:%M', _time.localtime(bound_at)).replace(' 0', ' ')
                                    if bound_at else 'an earlier bind')
                            chip = ui.chip(label + (' · stale' if stale else (' · old bind' if unknown else '')),
                                           icon='download').props('dense outline clickable')
                            chip.tooltip(f"bound {when}" + (
                                " — BEFORE your latest changes; bind again for the current book"
                                if stale else (
                                " — bound before tonight's bookkeeping; bind again to be sure"
                                if unknown else " — this is the current book")))
                            chip.on('click', lambda _, u='/' + path.replace(os.sep, '/'):
                                    ui.run_javascript(f"window.open('{u}', '_blank');"))
                        ui.chip('bind it', icon='menu_book').props('dense outline clickable') \
                            .tooltip("I'll bind the book and hand you the download"
                                     if ledger.complete else
                                     f"I'll bind the book as it stands — {ledger.summary()}; "
                                     f"unprinted panels bind as roughs or named boards, "
                                     f"placeholder lettering stays off the page") \
                            .on('click', lambda _: post_user_message(state, "Export the issue as a PDF."))
                        ui.chip('+ insert', icon='add_photo_alternate').props('dense outline clickable') \
                            .on('click', lambda _: post_user_message(
                                state, "Add a full-page insert to this issue — ask me what "
                                       "kind and where it goes."))

                    # THE PRODUCTION DASHBOARD: the eight stages from script to
                    # bound book, then the story→scene breakdown.  Every stage
                    # and every row is a door into the open book.
                    from helpers.production import production_board
                    board = production_board(storage, series_id, issue_id)

                    def open_to(anchor=None, dial=None):
                        if dial:
                            state._book_detail[issue_id] = dial
                        if anchor:
                            remember_spot(anchor)
                        state.refresh_details()

                    ui.label('PRODUCTION').classes('prod-cap')
                    with ui.element('div').classes('prod-strip'):
                        for stg in board.stages:
                            done = stg.total > 0 and stg.done >= stg.total
                            cls = 'prod-stage'
                            if not stg.started:
                                cls += ' prod-stage--empty'
                            elif done:
                                cls += ' prod-stage--done'
                            can_door = stg.started and not done and (stg.anchor or stg.detail)
                            if can_door:
                                cls += ' prod-stage--door'
                            cell = ui.element('div').classes(cls)
                            with cell:
                                with ui.element('div').classes('prod-stage__lbl'):
                                    if done:
                                        ui.icon('check').style('font-size: 11px; color: #2e6e3c;')
                                    ui.label(stg.label)
                                with ui.element('div').classes('prod-stage__num'):
                                    ui.html(f"{stg.done}<small>/{stg.total}</small>")
                                pct = int(100 * stg.done / stg.total) if stg.total else 0
                                with ui.element('div').classes('prod-bar'):
                                    ui.element('div').classes(
                                        'prod-bar__fill' + (' prod-bar__fill--done' if done else '')) \
                                        .style(f'width: {pct}%;')
                            if can_door:
                                cell.tooltip('Open the book to the next one')
                                cell.on('click', lambda _, s=stg: open_to(s.anchor, s.detail))

                    # THE BREAKDOWN, story by story, scene by scene
                    def gauge(label, done, total):
                        if done >= total:
                            state_cls, body = 'prod-g--done', f'{done}/{total}'
                        elif done == 0:
                            state_cls, body = 'prod-g--part', f'0/{total}'
                        else:
                            state_cls, body = 'prod-g--part', f'{done}/{total}'
                        with ui.element('span').classes(f'prod-g {state_cls}'):
                            ui.label(label)
                            ui.label(body).classes('prod-g__v')

                    with ui.element('div').classes('prod-board'):
                        for story in board.stories:
                            hdr = ui.element('div').classes('prod-story cursor-pointer')
                            with hdr:
                                ui.label(story.name.title()).classes('prod-story__ttl')
                                bits = ['scripted' if story.scripted else 'no script yet']
                                if story.scripted:
                                    bits.append(f"{len(story.scenes)} scene"
                                                f"{'s' if len(story.scenes) != 1 else ''}"
                                                if story.scenes else 'no scenes yet')
                                ui.label(' · '.join(bits)).classes('prod-story__meta')
                                cred = ' · '.join(c for c in (story.writer, story.artist,
                                                              story.letterer) if c) \
                                    or 'writer · artist · letterer'
                                cl = ui.label(cred).classes('prod-story__credits')
                                cl.tooltip('Set this story’s writer, artist and letterer')
                                cl.on('click.stop', lambda _, n=story.name: post_user_message(
                                    state, f"I would like to set the writer, artist and letterer "
                                           f"credits for the story '{n}'."))
                            hdr.on('click', lambda _, a=story.anchor: open_to(a, 'stories'))
                            for sr in story.scenes:
                                row = ui.element('div').classes('prod-scene')
                                with row:
                                    with ui.element('div').classes('prod-scene__name'):
                                        ui.label(str(sr.scene_number)).classes('prod-scene__n')
                                        ui.label(sr.name).classes('prod-scene__t')
                                    with ui.element('div').classes('prod-gauges'):
                                        if not sr.has_beats:
                                            with ui.element('span').classes('prod-g prod-g--bare'):
                                                ui.label('no beats yet')
                                        else:
                                            gauge('laid', sr.laid, sr.panels)
                                            gauge('rough', sr.roughed, sr.panels)
                                            gauge('inked', sr.inked, sr.panels)
                                row.on('click', lambda _, a=sr.anchor: open_to(a, 'beats'))

                    # LOOSE ENDS the stages don't track — an unbroken story,
                    # drifted script, placeholder lettering, un-rendered inserts
                    # — kept as small print so nothing reaches print unwarned.
                    loose = [ln for ln in ledger.lines
                             if ln.key in ('breakdown', 'drift', 'letters', 'inserts') and not ln.ok]
                    if loose:
                        ui.label('LOOSE ENDS').classes('prod-cap')
                        with ui.column().classes('w-full').style('gap: 0;'):
                            for ln in loose:
                                r = ui.row().classes('items-center ledger-line w-full cursor-pointer') \
                                    .style('gap: 6px; flex-wrap: nowrap; overflow: hidden;')
                                with r:
                                    ui.icon('radio_button_unchecked').style('font-size: 12px; opacity: .7;')
                                    ui.label(ln.text)
                                r.tooltip('Open the book to it')
                                r.on('click', lambda _, l=ln: open_to(l.anchor, l.detail))

        # THE BOOK REMEMBERS YOUR SPOT: walking into a panel and back lands
        # you on the page you left.  The spot is spent once used — editing
        # in place must never scroll-jack back to an old position.
        anchor = state._book_anchor.pop(issue_id, None)
        if anchor == 'masthead-top':
            # the masthead is position:sticky — its rect is already pinned
            # to the pane's top edge, so scrollIntoView can't find the way
            # home; walk the bookroom itself back to the front
            ui.timer(0.4, lambda: ui.run_javascript(
                "document.querySelectorAll('.bookroom .q-scrollarea__container')"
                ".forEach(p => p.scrollTop = 0);"), once=True)
        elif anchor:
            ui.timer(0.4, lambda a=anchor: ui.run_javascript(
                f"document.querySelector('[data-banchor=\"{a}\"]')"
                f"?.scrollIntoView({{block: 'center'}});"), once=True)
