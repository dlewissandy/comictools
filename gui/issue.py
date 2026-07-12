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

COVER_ORDER = ["front", "inside-front", "inside-back", "back"]
ASPECT_CYCLE = {"landscape": "portrait", "portrait": "square", "square": "landscape"}
ASPECT_ICON = {"landscape": "crop_landscape", "portrait": "crop_portrait", "square": "crop_square"}


def _sizes_for(aspect: str) -> list[str]:
    return ["1x", "2x", "3x"] if aspect == "square" else ["1x", "2x"]


def _norm_size(size, aspect: str) -> str:
    """A panel's size as the multiplier it EFFECTIVELY packs at — legacy
    names ('regular', 'large', 'splash', 'small') read as their multiplier,
    clamped to what the aspect offers."""
    from helpers.stitcher import AR, size_mult
    return f"{size_mult(size, AR.get(aspect, 1.5))}x"


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
    export_dir = os.path.join("data", "series", series_id, "issues", issue_id, "exports")

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
        table_receipt(state, text)
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

    # ---- shared text editor: save directly, or hand it to the coauthor --
    def edit_text_dialog(title, initial, on_save, develop_msg):
        with ui.dialog() as dlg, ui.card().classes('soft-card') \
                .style('min-width: 560px; max-width: 820px;'):
            ui.label(title).classes('caption-box caption-box-sm')
            ta = ui.textarea(value=initial or '').classes('w-full q-mt-sm') \
                .props('autogrow outlined input-style="font-size: 0.85rem"')
            with ui.row().classes('w-full items-center q-mt-sm').style('gap: 8px;'):
                ui.button('Save', icon='save').props('unelevated dense no-caps') \
                    .on('click', lambda _: (dlg.close(), on_save(ta.value)))
                ui.chip('work on it with me', icon='forum').props('dense outline clickable') \
                    .tooltip("Hand it to me in the conversation — we'll edit it together") \
                    .on('click', lambda _: (dlg.close(), post_user_message(state, develop_msg)))
                ui.space()
                ui.button('Never mind', icon='close').props('flat dense no-caps') \
                    .on('click', lambda _: dlg.close())
        dlg.open()

    # ---- mutations -------------------------------------------------------
    def _repack_prints(panel_id):
        from helpers.stitcher import repack_page
        for pm in storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id}):
            if pm.cells and any(r.panel_id == panel_id for row in pm.rows for r in row):
                repack_page(storage, pm)
                storage.update_object(pm)

    def cycle_aspect(scene_id, panel_id):
        p = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                        "scene_id": scene_id, "panel_id": panel_id})
        if p is None:
            return
        p.aspect = FrameLayout(ASPECT_CYCLE[p.aspect.value])
        # normalize the size to the multiplier it packs at under the NEW
        # aspect (legacy 'regular' stays 1x; a square's 3x clamps to 2x)
        p.size = _norm_size(getattr(p, 'size', None), p.aspect.value)
        storage.update_object(p)
        _repack_prints(panel_id)
        receipt(f"🔲 turned the panel {p.aspect.value} — the book reflowed around it")

    def cycle_size(scene_id, panel_id):
        p = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                        "scene_id": scene_id, "panel_id": panel_id})
        if p is None:
            return
        sizes = _sizes_for(p.aspect.value)
        cur = _norm_size(getattr(p, 'size', None), p.aspect.value)
        p.size = sizes[(sizes.index(cur) + 1) % len(sizes)]
        storage.update_object(p)
        _repack_prints(panel_id)
        receipt(f"🔲 sized the panel {p.size} — the book reflowed around it")

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
        # step through the REAL anchor spots: the front of the book, then
        # each existing scene — never a number that matches nothing
        anchors = [0] + sorted(s.scene_number for s in scenes_all)
        cur = fresh.after_scene_number if fresh.after_scene_number in anchors else 0
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
            ui.menu_item('Delete the scene…',
                         on_click=lambda _, s=sc: post_user_message(
                             state, f"I would like to delete scene '{s.name}'."))

    def tile(scene_id, panel_id, x, y, w, h, grid_h=10.0, cap_scene=None):
        p = panel_of.get(panel_id)
        live_h = TRIM_H - 2 * MY
        box = (f'left: {(MX + x) / TRIM_W * 100:.2f}%; '
               f'top: {(MY + y / grid_h * live_h) / TRIM_H * 100:.2f}%; '
               f'width: {w / TRIM_W * 100:.2f}%; '
               f'height: {(h / grid_h * live_h) / TRIM_H * 100:.2f}%;')
        t = ui.element('div').classes('tile').style(box)
        t._props['data-banchor'] = f'panel-{panel_id}'
        with t:
            if p is None:
                ui.label('missing panel').classes('tile-beat text-xs text-gray-400')
            elif p.image and os.path.exists(p.image):
                ui.image(source=p.image).props('fit=cover').classes('absolute inset-0 w-full h-full')
            else:
                with ui.element('div').classes('tile-beat' + (' tile-beat--capped' if cap_scene else '')):
                    txt = (p.beat or '').strip()
                    ui.label(txt if txt else 'unwritten panel').classes(
                        'tile-beat__text' + ('' if txt else ' italic opacity-60'))
            if cap_scene is not None:
                cap = ui.label(f'{cap_scene.scene_number} · {cap_scene.name}'.upper()).classes('tile-cap')
                with cap:
                    scene_menu(cap_scene)
                cap.on('click.stop', lambda _: None)
            if p is not None:
                size = _norm_size(getattr(p, 'size', None), p.aspect.value)
                with ui.row().classes('tile-tools items-center flex-nowrap'):
                    ui.button(icon='chevron_left').props('flat round dense size=xs') \
                        .tooltip('Earlier in the scene') \
                        .on('click.stop', lambda _, s=scene_id, pid=panel_id: move_beat(s, pid, -1))
                    ui.button(icon='edit').props('flat round dense size=xs') \
                        .tooltip('Pencil the panel — edit its script') \
                        .on('click.stop', lambda _, s=scene_id, p=p: edit_text_dialog(
                            f'Panel {p.panel_number} — {p.name}', p.beat,
                            lambda v, s=s, pid=p.panel_id: save_beat_text(s, pid, v),
                            f"Let's work on the script for panel {p.panel_number} "
                            f"of this scene together."))
                    ui.button(icon=ASPECT_ICON[p.aspect.value]).props('flat round dense size=xs') \
                        .tooltip(f'{p.aspect.value} — click to turn the panel') \
                        .on('click.stop', lambda _, s=scene_id, pid=panel_id: cycle_aspect(s, pid))
                    sz = ui.element('div').classes('size-chip')
                    with sz:
                        ui.label(size)
                    sz.tooltip(f'{size} of {"/".join(_sizes_for(p.aspect.value))} — click to resize')
                    sz.on('click.stop', lambda _, s=scene_id, pid=panel_id: cycle_size(s, pid))
                    ui.button(icon='chevron_right').props('flat round dense size=xs') \
                        .tooltip('Later in the scene') \
                        .on('click.stop', lambda _, s=scene_id, pid=panel_id: move_beat(s, pid, 1))
                    ui.button(icon='close').props('flat round dense size=xs') \
                        .tooltip('Tear this panel out of the book…') \
                        .on('click.stop', lambda _, p=p: post_user_message(
                            state, f"I would like to delete panel {p.panel_number} "
                                   f"('{p.name}') of this scene."))
        if p is not None:
            t.tooltip(f"panel {p.panel_number}: {p.name or ''} — open its light table")
            t.on('click', lambda _, s=scene_id, pid=panel_id: open_scene_panel(s, pid))
        return t

    def cover_sheet(location, recto=False):
        c = cover_at.get(location)
        classes = 'book-page' + (' book-page--recto' if recto else '')
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
        elif location in ('front', 'back'):
            with ui.element('div').classes(classes + ' book-page--ghost') as sh:
                ui.label(f'+ {location} cover').classes('page-ghost-cta')
            sh.tooltip('Every book needs one')
            sh.on('click', lambda _, loc=location: post_user_message(
                state, f"I would like to create a {loc} cover for this issue."))
            return True
        return c is not None

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
                if text and wc < 80:
                    ui.chip('develop it with me', icon='forum').props('dense outline clickable size=sm') \
                        .tooltip("It's thin — I'll interview you and we'll build it out") \
                        .on('click', lambda _, sp=spoken: post_user_message(
                            state, f"{sp.capitalize()} is too thin to break down — "
                                   f"interview me and help me develop it."))
                elif text:
                    ui.chip('break into scenes', icon='view_agenda').props('dense outline clickable size=sm') \
                        .on('click', lambda _, sp=spoken: post_user_message(
                            state, f"Break {sp} into scenes."))
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

    def insert_sheet(ins):
        rendered = ins.image and os.path.exists(ins.image)
        has_text = bool((ins.description or '').strip())
        classes = 'book-page'
        if not rendered:
            classes += ' book-page--script' if has_text else ' book-page--ghost book-page--insert'
        with ui.element('div').classes(classes + ' cursor-pointer') as sh:
            if rendered:
                ui.image(source=ins.image).props('fit=cover').classes('absolute inset-0 w-full h-full')
            elif has_text:
                # a written page (the mailbag's letters, an ad's copy) reads
                # as manuscript until it's inked
                with ui.element('div').classes('script-body'):
                    ui.markdown(ins.description).classes('script-text')
            else:
                ui.icon({'poster': 'wallpaper', 'ad': 'storefront', 'pin-up': 'brush',
                         'mailbag': 'mail', 'title-page': 'title'}.get(ins.kind, 'wallpaper')) \
                    .classes('text-4xl').style('opacity: .5;')
                ui.label(ins.name).classes('page-ghost-cta')
            ui.label(f'{ins.kind} · {ins.name}'.upper()).classes('page-cap')
            foot = ui.row().classes('script-foot insert-foot items-center flex-nowrap').style('gap: 2px;')
            foot.on('click.stop', lambda _: None)   # the foot's own clicks stay in the foot
            with foot:
                footer_btn('chevron_left', 'Earlier in the book (previous scene)',
                           lambda _, i=ins: move_insert(i, -1))
                footer_btn('chevron_right', 'Later in the book (next scene)',
                           lambda _, i=ins: move_insert(i, 1))
                footer_btn('edit', 'Write the page — its words and what it shows',
                           lambda _, i=ins: edit_text_dialog(
                               f'{i.kind} — {i.name}', i.description,
                               lambda v, iid=i.insert_id: save_insert_description(iid, v),
                               f"Let's work on the '{i.name}' insert together."))
                if not rendered:
                    footer_btn('brush', 'Ink it — render the page as full art',
                               lambda _, i=ins: post_user_message(
                                   state, f"Render the '{i.name}' insert."))
                ui.space()
                footer_btn('close', 'Tear this insert out…',
                           lambda _, i=ins: post_user_message(
                               state, f"I would like to delete the insert '{i.name}'."))
        # the page IS a board: click it to open its light table
        sh.tooltip(f"The {ins.kind} — open it on the light table")
        sh.on('click', lambda _, i=ins: goto(SelectedKind.INSERT, i.insert_id, i.name,
                                             anchor=f'insert-{i.insert_id}'))
        sh._props['data-banchor'] = f'insert-{ins.insert_id}'

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
                elif text and wc < 40:
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
                ui.space()
                footer_btn('close', 'Tear this scene out…',
                           lambda _, s=sc: post_user_message(
                               state, f"I would like to delete scene '{s.name}'."))
            if folio is not None:
                ui.label(str(folio)).classes('page-folio')
        sh._props['data-banchor'] = f'scene-{sc.scene_id}'

    def slip_sheet(scs):
        """MANUSCRIPT SLIPS: a run of bare scenes clipped to one sheet as
        working paper — each slip carries its own cap, words and tools."""
        with ui.element('div').classes('book-page book-page--script book-page--slips'):
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
                        if text and wc >= 40:
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

    with details:
        # ---- the masthead stays put over the table ------------------------
        with ui.row().classes('book-masthead w-full flex-nowrap items-center').style('gap: 12px;'):
            header(f"ISSUE {issue.issue_number}: {issue.name}", 0)
            from gui.light_table import style_swatch
            style_swatch(state, issue, shared_with='the whole issue')
            # THE DETAIL DIAL: read the book at script, scene, or panel altitude
            with ui.row().classes('items-center flex-nowrap').style('gap: 4px;'):
                for key, label, hint in (('stories', 'SCRIPT', 'the written script'),
                                         ('scenes', 'SCENES', 'scene manuscript pages'),
                                         ('beats', 'PANELS', 'panels laid out on the pages')):
                    chip = ui.element('div').classes('dial-chip' + (' dial-chip--on' if detail == key else ''))
                    chip.mark(f'detail-{key}')
                    with chip:
                        ui.label(label)
                    chip.tooltip(f'Read the book as {hint}')
                    chip.on('click', lambda _, k=key: set_detail(k))
            ui.space()
            # THE LEDGER BADGE: the one production truth, worn on the
            # masthead — click it and the book opens to the colophon
            badge = ui.chip(ledger.summary(),
                            icon='verified' if ledger.complete else 'fact_check') \
                .props('dense outline clickable size=sm')
            badge.tooltip('  ·  '.join(l.text for l in ledger.todos)
                          or 'Every board inked, every panel placed — bind it')
            badge.on('click', lambda _: (remember_spot('colophon'), state.refresh_details()))
            ui.button('Read', icon='menu_book').props('rounded') \
                .tooltip('Read the issue front to back') \
                .on('click', lambda _: ui.run_javascript(
                    f"window.open('/series/{series_id}/issue/{issue_id}/read', '_blank');"))
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current issue."))

        # ---- THE OPEN BOOK ------------------------------------------------
        # THE BOOK sizes itself to the bookroom (the details pane is a CSS
        # container), so a narrow pane stacks single pages instead of clipping
        with ui.element('div').classes('book w-full'):
            cover_sheet('front', recto=True)
            cover_sheet('inside-front')

            # THE STORIES: the issue's own script, then the backups, in order.
            # Once a story has been expanded into scenes it steps back — the
            # scenes ARE the story now; the STORIES dial reads it any time.
            stories = ([None] if issue.story or not stories_all else []) + stories_all
            if detail == 'stories' or not scenes_all:
                for i, st in enumerate(stories):
                    # ‹ › move only among the REAL stories — the issue's own
                    # script always opens the book
                    is_first = st is None or not stories_all or st.story_id == stories_all[0].story_id
                    story_sheet(st, first=bool(is_first), last=(i == len(stories) - 1))

            inserts_by_anchor = {}
            for ins in inserts_all:
                inserts_by_anchor.setdefault(ins.after_scene_number, []).append(ins)
            for ins in inserts_by_anchor.get(0, []):
                insert_sheet(ins)

            if detail == 'scenes':
                # every scene as a manuscript page, in order, inserts slotted in
                for sc in scenes_all:
                    scene_sheet(sc)
                    for ins in inserts_by_anchor.get(sc.scene_number, []):
                        insert_sheet(ins)
            elif detail == 'beats':
                # THE BOOK FLOWS CONTINUOUSLY: beats pack across page turns the
                # way text reflows across lines — turning, resizing, or moving
                # a panel carries neighbors onto the next or previous page.
                # Bare scenes and inserts hold their place as full pages.
                from helpers.stitcher import pack_bands, paginate, justify, AR
                segments, run = [], []

                def flush():
                    nonlocal run
                    if run:
                        segments.append(('flow', run))
                        run = []
                for sc in scenes_all:
                    panels = panels_by_scene[sc.scene_id]
                    if panels:
                        run += [((sc.scene_id, p.panel_id), AR.get(p.aspect.value, 1.5),
                                 getattr(p, 'size', None) or '1x') for p in panels]
                    else:
                        flush()
                        segments.append(('manuscript', sc))
                    for ins in inserts_by_anchor.get(sc.scene_number, []):
                        flush()
                        segments.append(('insert', ins))
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
                    else:
                        flush_slips()
                        packed.append((kind, seg))
                flush_slips()
                segments = packed

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
                            with ui.element('div').classes('book-page') as sheet:
                                for key, x, y, w, h in cells:
                                    tile(key[0], key[1], x, y, w, h, grid_h,
                                         cap_scene=first_tiles.get(key[1]))
                                ui.label(str(folio)).classes('page-folio')
                            sheet._props['data-banchor'] = f'flow-{folio}'
                    elif kind == 'slips':
                        # bare scenes hold their place but don't PRINT —
                        # no folio, so screen and book agree on page numbers
                        slip_sheet(seg)
                    else:
                        insert_sheet(seg)

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
                    # THE CREDITS, SET IN TYPE: the colophon prints like a
                    # real indicia block — every line is still a pencil
                    with ui.element('div').classes('colophon-credits q-mt-md'):
                        for role, val in (("writer", issue.writer),
                                          ("artist", issue.artist),
                                          ("colorist", issue.colorist),
                                          ("creative minds", issue.creative_minds),
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
                        for fname, label in ((f"{issue_id}.pdf", '⤓ PDF'), (f"{issue_id}.cbz", '⤓ CBZ')):
                            path = os.path.join(export_dir, fname)
                            if os.path.exists(path):
                                ui.chip(label, icon='download').props('dense outline clickable') \
                                    .on('click', lambda _, u='/' + path.replace(os.sep, '/'):
                                        ui.run_javascript(f"window.open('{u}', '_blank');"))
                        ui.chip('bind it', icon='menu_book').props('dense outline clickable') \
                            .tooltip("I'll bind the book and hand you the download"
                                     if ledger.complete else
                                     f"I'll bind the book as it stands — {ledger.summary()}, "
                                     f"so placeholders will print") \
                            .on('click', lambda _: post_user_message(state, "Export the issue as a PDF."))
                        ui.chip('+ insert', icon='add_photo_alternate').props('dense outline clickable') \
                            .on('click', lambda _: post_user_message(
                                state, "Add a full-page insert to this issue — ask me what "
                                       "kind and where it goes."))
                # THE PRODUCTION LEDGER, set in the colophon's small print —
                # every line is a door to the first thing it counts
                def ledger_door(line):
                    if line.detail:
                        state._book_detail[issue_id] = line.detail
                    if line.anchor:
                        remember_spot(line.anchor)
                    state.refresh_details()
                with ui.column().classes('q-mt-sm w-full').style('gap: 0;'):
                    for ln in ledger.lines:
                        row = ui.row().classes(
                            'items-center page-small-print w-full'
                            + ('' if ln.ok else ' cursor-pointer')).style('gap: 6px; flex-wrap: nowrap; overflow: hidden;')
                        with row:
                            ui.icon('check' if ln.ok else 'radio_button_unchecked') \
                                .style('font-size: 12px;' + ('' if ln.ok else ' opacity: .7;'))
                            ui.label(ln.text)
                        if not ln.ok and (ln.anchor or ln.detail):
                            row.tooltip('Open the book to it')
                            row.on('click', lambda _, l=ln: ledger_door(l))

        # THE BOOK REMEMBERS YOUR SPOT: walking into a panel and back lands
        # you on the page you left.  The spot is spent once used — editing
        # in place must never scroll-jack back to an old position.
        anchor = state._book_anchor.pop(issue_id, None)
        if anchor:
            ui.timer(0.4, lambda a=anchor: ui.run_javascript(
                f"document.querySelector('[data-banchor=\"{a}\"]')"
                f"?.scrollIntoView({{block: 'center'}});"), once=True)
