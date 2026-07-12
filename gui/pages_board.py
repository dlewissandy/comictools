"""
THE PAGES BOARD: the book's pages, visible and editable at last.

Pacing lives in the page turn — so the pages themselves are cards on the
issue view: each one a composed thumbnail of its real grid, reorderable,
with an UNPLACED tray so no panel can hide off the book.  Every change is
a one-click direct write with a receipt; layout_issue_pages remains the
bulk-propose path for the coauthor.
"""
import base64
import os
from io import BytesIO

from loguru import logger
from nicegui import ui

from schema import Page, Panel, PanelRef
from helpers.binder import _compose_page, page_coverage


def _pages(storage, series_id, issue_id):
    return storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id},
                                    order_by="page_number")


def _resolve_rows(storage, series_id, issue_id, pm):
    rows = []
    for row in pm.rows:
        paths = []
        for ref in row:
            p = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                            "scene_id": ref.scene_id, "panel_id": ref.panel_id})
            ok = p and p.image and os.path.exists(p.image)
            paths.append(p.image if ok else None)
        rows.append(paths)
    return rows


def _thumb(state, series_id, issue_id, pm) -> str:
    """A composed thumbnail of the page as a data URL, cached by content."""
    storage = state.storage
    cache = getattr(state, '_page_thumbs', None)
    if cache is None:
        cache = {}
        try:
            state._page_thumbs = cache
        except Exception:
            pass
    sig_parts = [repr(pm.rows)]
    rows = _resolve_rows(storage, series_id, issue_id, pm)
    for row in rows:
        for path in row:
            if path:
                try:
                    sig_parts.append(str(os.path.getmtime(path)))
                except OSError:
                    pass
    key = (pm.page_id, hash(tuple(sig_parts)))
    if key in cache:
        return cache[key]
    img = _compose_page(rows)
    img.thumbnail((330, 512))
    buf = BytesIO()
    img.convert('RGB').save(buf, 'JPEG', quality=70)
    url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    if len(cache) > 64:
        cache.clear()
    cache[key] = url
    return url


def _renumber(storage, pages):
    for i, pm in enumerate(sorted(pages, key=lambda p: p.page_number), start=1):
        if pm.page_number != i:
            pm.page_number = i
            storage.update_object(pm)


def _strip_ref(pages, panel_id):
    """Remove a panel from every page's rows (in memory); return changed pages."""
    changed = []
    for pm in pages:
        new_rows = [[r for r in row if r.panel_id != panel_id] for row in pm.rows]
        new_rows = [row for row in new_rows if row]
        if new_rows != pm.rows:
            pm.rows = new_rows
            changed.append(pm)
    return changed


def pages_board(state, series_id: str, issue_id: str):
    from gui.light_table import table_receipt
    from gui.elements import caption_action, CrudButtonKind as _CK
    storage = state.storage

    pages = _pages(storage, series_id, issue_id)
    _has, _placed, unplaced, dangling = page_coverage(storage, series_id, issue_id)

    def receipt(text):
        table_receipt(state, text)
        state.refresh_details()

    # ---- mutations (always on fresh reads) --------------------------------
    def new_page_at_end() -> Page:
        fresh = _pages(storage, series_id, issue_id)
        n = max((p.page_number for p in fresh), default=0) + 1
        pid = f"page-{n}"
        if any(p.page_id == pid for p in fresh):
            from uuid import uuid4
            pid = f"page-{n}-{uuid4().hex[:4]}"
        pm = Page(page_id=pid, issue_id=issue_id, series_id=series_id,
                  page_number=n, rows=[])
        storage.create_object(data=pm, overwrite=True)
        return pm

    def add_page():
        pm = new_page_at_end()
        receipt(f"📄 added page {pm.page_number} to the book")

    def nudge_page(page_id, d):
        fresh = sorted(_pages(storage, series_id, issue_id), key=lambda p: p.page_number)
        i = next((j for j, p in enumerate(fresh) if p.page_id == page_id), None)
        if i is None or not (0 <= i + d < len(fresh)):
            return
        fresh[i], fresh[i + d] = fresh[i + d], fresh[i]
        for j, p in enumerate(fresh):
            if p.page_number != j + 1:
                p.page_number = j + 1
                storage.update_object(p)
        receipt(f"↔️ moved a page {'earlier' if d < 0 else 'later'} in the book")

    def remove_page(page_id):
        fresh = _pages(storage, series_id, issue_id)
        pm = next((p for p in fresh if p.page_id == page_id), None)
        if pm is None:
            return
        saved_rows = [[PanelRef(scene_id=r.scene_id, panel_id=r.panel_id) for r in row]
                      for row in pm.rows]
        saved_number = pm.page_number
        n_panels = sum(len(r) for r in pm.rows)
        storage.delete_object(cls=Page, primary_key=pm.primary_key)
        _renumber(storage, [p for p in _pages(storage, series_id, issue_id)])

        def undo():
            back = Page(page_id=page_id, issue_id=issue_id, series_id=series_id,
                        page_number=saved_number, rows=saved_rows)
            storage.create_object(data=back, overwrite=True)
            _renumber(storage, _pages(storage, series_id, issue_id))
        table_receipt(state, f"🗑 tore page {saved_number} out of the book — "
                             f"its {n_panels} panel(s) are unplaced now", undo=undo)
        state.refresh_details()

    def place(scene_id, panel_id, page_id, row_idx, label):
        fresh = _pages(storage, series_id, issue_id)
        changed = set(id(p) for p in _strip_ref(fresh, panel_id))
        if page_id is None:
            target = new_page_at_end()
            fresh.append(target)
        else:
            target = next((p for p in fresh if p.page_id == page_id), None)
            if target is None:
                return
        ref = PanelRef(scene_id=scene_id, panel_id=panel_id)
        if row_idx is None or row_idx >= len(target.rows):
            target.rows.append([ref])
        else:
            target.rows[row_idx].append(ref)
        for p in fresh:
            if id(p) in changed or p is target:
                storage.update_object(p)
        receipt(f"📄 placed the panel on {label}")

    def unplace(panel_id):
        fresh = _pages(storage, series_id, issue_id)
        for p in _strip_ref(fresh, panel_id):
            storage.update_object(p)
        receipt("📄 took the panel off its page — it waits in the unplaced tray")

    def shift_in_row(page_id, row_idx, panel_id, d):
        fresh = _pages(storage, series_id, issue_id)
        pm = next((p for p in fresh if p.page_id == page_id), None)
        if pm is None or row_idx >= len(pm.rows):
            return
        row = pm.rows[row_idx]
        i = next((j for j, r in enumerate(row) if r.panel_id == panel_id), None)
        if i is None or not (0 <= i + d < len(row)):
            return
        row[i], row[i + d] = row[i + d], row[i]
        storage.update_object(pm)
        receipt("↔️ reordered panels within the row")

    def own_row(page_id, row_idx, panel_id):
        fresh = _pages(storage, series_id, issue_id)
        pm = next((p for p in fresh if p.page_id == page_id), None)
        if pm is None or row_idx >= len(pm.rows):
            return
        row = pm.rows[row_idx]
        ref = next((r for r in row if r.panel_id == panel_id), None)
        if ref is None or len(row) == 1:
            return
        row.remove(ref)
        pm.rows.insert(row_idx + 1, [ref])
        storage.update_object(pm)
        receipt("📄 gave the panel its own row")

    # ---- placement menu targets -------------------------------------------
    def placement_items(scene_id, panel_id):
        fresh = _pages(storage, series_id, issue_id)
        items = []
        for pm in sorted(fresh, key=lambda p: p.page_number):
            items.append((f"page {pm.page_number} — new row", pm.page_id, None))
            for ri, row in enumerate(pm.rows):
                if len(row) < 3 and not any(r.panel_id == panel_id for r in row):
                    items.append((f"page {pm.page_number}, row {ri + 1} "
                                  f"(beside {len(row)})", pm.page_id, ri))
        items.append(("a new page at the end", None, None))
        return items

    def place_menu(scene_id, panel_id):
        with ui.menu():
            for label, pid, ri in placement_items(scene_id, panel_id):
                ui.menu_item(label, on_click=lambda _, s=scene_id, p=panel_id,
                             g=pid, r=ri, l=label: place(s, p, g, r, l))

    # ---- the page editor dialog -------------------------------------------
    def edit_page(page_id):
        fresh = _pages(storage, series_id, issue_id)
        pm = next((p for p in fresh if p.page_id == page_id), None)
        if pm is None:
            return
        with ui.dialog() as dlg, ui.card().classes('soft-card') \
                .style('min-width: 560px; max-width: 860px;'):
            ui.label(f'Page {pm.page_number}').classes('caption-box caption-box-sm')
            ui.label('Rows read top to bottom; panels left to right.  '
                     'A single panel on a single row is a splash page.') \
                .classes('text-xs text-gray-500 q-mt-sm')
            for ri, row in enumerate(pm.rows):
                with ui.row().classes('w-full items-center q-mt-sm').style('gap: 8px;'):
                    ui.label(f'row {ri + 1}').classes('text-xs text-gray-500') \
                        .style('width: 44px;')
                    for ref in row:
                        p = storage.read_object(Panel, {
                            "series_id": series_id, "issue_id": issue_id,
                            "scene_id": ref.scene_id, "panel_id": ref.panel_id})
                        with ui.card().classes('soft-card p-1').style('width: 150px;'):
                            if p is not None and p.image and os.path.exists(p.image):
                                ui.image(source=p.image).style('height: 84px;').props('fit=cover')
                            nm = p.name if p is not None else f'missing {ref.panel_id[:8]}…'
                            ui.label(nm).classes('text-xs w-full') \
                                .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                            with ui.row().classes('w-full justify-center').style('gap: 0;'):
                                ui.button(icon='chevron_left').props('flat round dense size=xs') \
                                    .tooltip('Move left in the row') \
                                    .on('click', lambda _, r=ref, ri=ri: (dlg.close(),
                                        shift_in_row(page_id, ri, r.panel_id, -1)))
                                ui.button(icon='chevron_right').props('flat round dense size=xs') \
                                    .tooltip('Move right in the row') \
                                    .on('click', lambda _, r=ref, ri=ri: (dlg.close(),
                                        shift_in_row(page_id, ri, r.panel_id, 1)))
                                ui.button(icon='vertical_split').props('flat round dense size=xs') \
                                    .tooltip('Give it its own row below') \
                                    .on('click', lambda _, r=ref, ri=ri: (dlg.close(),
                                        own_row(page_id, ri, r.panel_id)))
                                mb = ui.button(icon='drive_file_move').props('flat round dense size=xs') \
                                    .tooltip('Move to another page / row')
                                with mb:
                                    place_menu(ref.scene_id, ref.panel_id)
                                ui.button(icon='close').props('flat round dense size=xs') \
                                    .tooltip('Take it off the page (to the unplaced tray)') \
                                    .on('click', lambda _, r=ref: (dlg.close(), unplace(r.panel_id)))
            if not pm.rows:
                ui.label('An empty page — place panels from the unplaced tray.') \
                    .classes('text-sm text-gray-500 q-mt-sm')
        dlg.open()

    # ---- render -------------------------------------------------------------
    with ui.row().classes('w-full items-center').style('gap: 10px;'):
        caption_action("Pages", _CK.CREATE, lambda _: add_page(), 3)
        if pages:
            ui.label(f"{len(pages)} page(s) — pacing lives in the page turn; "
                     f"click a page to rearrange it").classes('text-xs text-gray-500')
        if dangling:
            ui.chip(f'{len(dangling)} dangling ref(s)', icon='report', color='orange') \
                .props('dense outline') \
                .tooltip('A page points at a deleted panel — open the page and remove it')

    if not pages and not unplaced:
        ui.label('No pages yet — break the scenes into panels first, then lay out the book.') \
            .classes('text-sm text-gray-500')

    with ui.row().classes('w-full').style('gap: 12px; row-gap: 16px;'):
        for pm in sorted(pages, key=lambda p: p.page_number):
            with ui.column().classes('items-center').style('gap: 2px;'):
                with ui.card().classes('soft-card p-1 cursor-pointer relative') \
                        .style('width: 168px;') as card:
                    ui.image(source=_thumb(state, series_id, issue_id, pm)) \
                        .style('width: 160px;').props('fit=contain')
                card.on('click', lambda _, pid=pm.page_id: edit_page(pid))
                card.tooltip('Open this page to rearrange its panels')
                with ui.row().classes('items-center').style('gap: 0;'):
                    ui.button(icon='chevron_left').props('flat round dense size=xs') \
                        .tooltip('Earlier in the book') \
                        .on('click', lambda _, pid=pm.page_id: nudge_page(pid, -1))
                    ui.label(f'page {pm.page_number}').classes('text-xs')
                    ui.button(icon='chevron_right').props('flat round dense size=xs') \
                        .tooltip('Later in the book') \
                        .on('click', lambda _, pid=pm.page_id: nudge_page(pid, 1))
                    ui.button(icon='close').props('flat round dense size=xs') \
                        .tooltip('Tear this page out (its panels go to the tray)') \
                        .on('click', lambda _, pid=pm.page_id: remove_page(pid))

    if unplaced:
        with ui.row().classes('w-full items-center q-mt-sm').style('gap: 8px;'):
            ui.label('UNPLACED').classes('comic-label-sm')
            ui.label(f"{len(unplaced)} panel(s) not on any page — they'd flow onto "
                     f"overflow pages at the end of the book") \
                .classes('text-xs text-orange-8')
        with ui.row().classes('w-full').style('gap: 8px; row-gap: 10px;'):
            for scene, panel in unplaced:
                with ui.card().classes('soft-card p-1').style('width: 150px;'):
                    if panel.image and os.path.exists(panel.image):
                        ui.image(source=panel.image).style('height: 84px;').props('fit=cover')
                    else:
                        ui.label('unrendered').classes('text-xs text-gray-500 text-center w-full') \
                            .style('height: 84px; line-height: 84px;')
                    ui.label(f"{scene.name} · {panel.name}").classes('text-xs w-full') \
                        .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                    pb = ui.button('Place it', icon='post_add').props('outline dense size=sm no-caps') \
                        .classes('w-full')
                    with pb:
                        place_menu(scene.scene_id, panel.panel_id)
