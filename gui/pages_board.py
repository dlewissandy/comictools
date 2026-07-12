"""
THE BOOK'S PAGES, shared pieces: composed page thumbnails (cells-aware),
the page dialog (rearrange, tear out, walk into any panel), placement
menus, and THE PRESSROOM — stitching and the unplaced tray.

The shelf on the issue view displays the sheets; everything here mutates
them.  Every change is a one-click direct write with a receipt; stitched
pages re-stitch themselves after any edit.
"""
import base64
import os
from io import BytesIO

from nicegui import ui

from schema import Page, Panel, PanelRef
from helpers.binder import _compose_page, _compose_page_cells, page_coverage, resolve_cells


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


def page_thumb(state, series_id, issue_id, pm) -> str:
    """A composed thumbnail of the page as a data URL, cached by content."""
    storage = state.storage
    cache = getattr(state, '_page_thumbs', None)
    if cache is None:
        cache = {}
        try:
            state._page_thumbs = cache
        except Exception:
            pass
    sig_parts = [repr(pm.rows), repr(pm.cells)]
    if pm.cells:
        specs = resolve_cells(storage, series_id, issue_id, pm)
        paths = [p for p, *_ in specs]
    else:
        rows = _resolve_rows(storage, series_id, issue_id, pm)
        paths = [p for row in rows for p in row]
    for path in paths:
        if path:
            try:
                sig_parts.append(str(os.path.getmtime(path)))
            except OSError:
                pass
    key = (pm.page_id, hash(tuple(sig_parts)))
    if key in cache:
        return cache[key]
    img = _compose_page_cells(specs) if pm.cells else _compose_page(rows)
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
    """Remove a panel from every page (in memory); return changed pages."""
    changed = []
    for pm in pages:
        new_rows = [[r for r in row if r.panel_id != panel_id] for row in pm.rows]
        new_rows = [row for row in new_rows if row]
        new_cells = [c for c in pm.cells if c.panel_id != panel_id]
        if new_rows != pm.rows or len(new_cells) != len(pm.cells):
            pm.rows = new_rows
            pm.cells = new_cells
            changed.append(pm)
    return changed


def _save(storage, pm):
    """Persist a page; a stitched page re-stitches itself first."""
    if pm.cells or not pm.rows:
        from helpers.stitcher import repack_page
        if pm.rows:
            repack_page(storage, pm)
        else:
            pm.cells = []
    storage.update_object(pm)


def open_panel(state, series_id, issue_id, scene_id, panel_id):
    """Walk from the book into a panel's light table."""
    from gui.selection import SelectionItem, SelectedKind
    from schema import SceneModel
    storage = state.storage
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


# ---- mutations (always on fresh reads) --------------------------------

def new_page_at_end(storage, series_id, issue_id) -> Page:
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


def _receipt(state, text, undo=None):
    from gui.light_table import table_receipt
    table_receipt(state, text, undo=undo)
    state.refresh_details()


def nudge_page(state, series_id, issue_id, page_id, d):
    storage = state.storage
    fresh = sorted(_pages(storage, series_id, issue_id), key=lambda p: p.page_number)
    i = next((j for j, p in enumerate(fresh) if p.page_id == page_id), None)
    if i is None or not (0 <= i + d < len(fresh)):
        return
    fresh[i], fresh[i + d] = fresh[i + d], fresh[i]
    for j, p in enumerate(fresh):
        if p.page_number != j + 1:
            p.page_number = j + 1
            storage.update_object(p)
    _receipt(state, f"↔️ moved a page {'earlier' if d < 0 else 'later'} in the book")


def remove_page(state, series_id, issue_id, page_id):
    storage = state.storage
    fresh = _pages(storage, series_id, issue_id)
    pm = next((p for p in fresh if p.page_id == page_id), None)
    if pm is None:
        return
    saved = pm.model_copy(deep=True)
    n_panels = sum(len(r) for r in pm.rows)
    storage.delete_object(cls=Page, primary_key=pm.primary_key)
    _renumber(storage, [p for p in _pages(storage, series_id, issue_id)])

    def undo():
        storage.create_object(data=saved, overwrite=True)
        _renumber(storage, _pages(storage, series_id, issue_id))
    _receipt(state, f"🗑 tore page {saved.page_number} out of the book — "
                    f"its {n_panels} panel(s) are unplaced now", undo=undo)


def place(state, series_id, issue_id, scene_id, panel_id, page_id, row_idx, label):
    storage = state.storage
    fresh = _pages(storage, series_id, issue_id)
    changed = _strip_ref(fresh, panel_id)
    if page_id is None:
        target = new_page_at_end(storage, series_id, issue_id)
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
    for p in {id(p): p for p in [*changed, target]}.values():
        _save(storage, p)
    _receipt(state, f"📄 placed the panel on {label}")


def unplace(state, series_id, issue_id, panel_id):
    storage = state.storage
    fresh = _pages(storage, series_id, issue_id)
    for p in _strip_ref(fresh, panel_id):
        _save(storage, p)
    _receipt(state, "📄 took the panel off its page — it waits in the unplaced tray")


def shift_in_row(state, series_id, issue_id, page_id, row_idx, panel_id, d):
    storage = state.storage
    pm = next((p for p in _pages(storage, series_id, issue_id) if p.page_id == page_id), None)
    if pm is None or row_idx >= len(pm.rows):
        return
    row = pm.rows[row_idx]
    i = next((j for j, r in enumerate(row) if r.panel_id == panel_id), None)
    if i is None:
        return
    if 0 <= i + d < len(row):
        row[i], row[i + d] = row[i + d], row[i]
    elif pm.cells and 0 <= row_idx + d < len(pm.rows):
        # on a stitched page the sequence is what matters — walking off a
        # band's edge carries the panel into the neighboring band
        ref = row.pop(i)
        pm.rows[row_idx + d].insert(len(pm.rows[row_idx + d]) if d > 0 else 0, ref)
        pm.rows = [r for r in pm.rows if r]
    else:
        return
    _save(storage, pm)
    _receipt(state, "↔️ reordered the panels on the page")


def own_row(state, series_id, issue_id, page_id, row_idx, panel_id):
    storage = state.storage
    pm = next((p for p in _pages(storage, series_id, issue_id) if p.page_id == page_id), None)
    if pm is None or row_idx >= len(pm.rows) or pm.cells:
        return   # a stitched page's banding is the stitcher's to decide
    row = pm.rows[row_idx]
    ref = next((r for r in row if r.panel_id == panel_id), None)
    if ref is None or len(row) == 1:
        return
    row.remove(ref)
    pm.rows.insert(row_idx + 1, [ref])
    storage.update_object(pm)
    _receipt(state, "📄 gave the panel its own row")


def stitch_now(state, series_id, issue_id):
    """One click: the whole issue onto pages — every panel, reading order."""
    from helpers.stitcher import apply_stitch
    storage = state.storage
    new_pages, old_pages = apply_stitch(storage, series_id, issue_id)
    if not new_pages:
        ui.notify("Nothing to stitch yet — break the scenes into panels first.", type='warning')
        return
    saved = [p.model_copy(deep=True) for p in old_pages]

    def undo():
        for p in _pages(storage, series_id, issue_id):
            storage.delete_object(cls=Page, primary_key=p.primary_key)
        for p in saved:
            storage.create_object(data=p, overwrite=True)
    _receipt(state, f"🧵 stitched the whole issue onto {len(new_pages)} page(s) — "
                    f"every panel placed, reading order, full pages", undo=undo)


# ---- placement menu -----------------------------------------------------

def placement_items(storage, series_id, issue_id, panel_id):
    items = []
    for pm in sorted(_pages(storage, series_id, issue_id), key=lambda p: p.page_number):
        items.append((f"page {pm.page_number} — new row", pm.page_id, None))
        for ri, row in enumerate(pm.rows):
            if len(row) < 3 and not any(r.panel_id == panel_id for r in row):
                items.append((f"page {pm.page_number}, row {ri + 1} "
                              f"(beside {len(row)})", pm.page_id, ri))
    items.append(("a new page at the end", None, None))
    return items


def place_menu(state, series_id, issue_id, scene_id, panel_id):
    with ui.menu():
        for label, pid, ri in placement_items(state.storage, series_id, issue_id, panel_id):
            ui.menu_item(label, on_click=lambda _, s=scene_id, p=panel_id,
                         g=pid, r=ri, l=label: place(state, series_id, issue_id, s, p, g, r, l))


# ---- the page dialog -----------------------------------------------------

def edit_page(state, series_id, issue_id, page_id):
    """The page in hand: move it through the book, tear it out, rearrange
    its panels, or walk into any panel's light table."""
    storage = state.storage
    pm = next((p for p in _pages(storage, series_id, issue_id) if p.page_id == page_id), None)
    if pm is None:
        return
    with ui.dialog() as dlg, ui.card().classes('soft-card') \
            .style('min-width: 560px; max-width: 860px;'):
        with ui.row().classes('w-full items-center').style('gap: 6px;'):
            ui.label(f'Page {pm.page_number}').classes('caption-box caption-box-sm')
            if pm.cells:
                ui.label('stitched — reorder panels and the page re-stitches itself') \
                    .classes('text-xs text-gray-500')
            ui.space()
            ui.button(icon='chevron_left').props('flat round dense size=sm') \
                .tooltip('Earlier in the book') \
                .on('click', lambda _: (dlg.close(), nudge_page(state, series_id, issue_id, page_id, -1)))
            ui.button(icon='chevron_right').props('flat round dense size=sm') \
                .tooltip('Later in the book') \
                .on('click', lambda _: (dlg.close(), nudge_page(state, series_id, issue_id, page_id, 1)))
            ui.button(icon='delete_sweep').props('flat round dense size=sm') \
                .tooltip('Tear this page out (its panels go to the unplaced tray)') \
                .on('click', lambda _: (dlg.close(), remove_page(state, series_id, issue_id, page_id)))
        for ri, row in enumerate(pm.rows):
            with ui.row().classes('w-full items-center q-mt-sm').style('gap: 8px;'):
                ui.label(f'row {ri + 1}').classes('text-xs text-gray-500').style('width: 44px;')
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
                            ui.button(icon='open_in_new').props('flat round dense size=xs') \
                                .tooltip('Open this panel on its light table') \
                                .on('click', lambda _, r=ref: (dlg.close(),
                                    open_panel(state, series_id, issue_id, r.scene_id, r.panel_id)))
                            ui.button(icon='chevron_left').props('flat round dense size=xs') \
                                .tooltip('Move left') \
                                .on('click', lambda _, r=ref, ri=ri: (dlg.close(),
                                    shift_in_row(state, series_id, issue_id, page_id, ri, r.panel_id, -1)))
                            ui.button(icon='chevron_right').props('flat round dense size=xs') \
                                .tooltip('Move right') \
                                .on('click', lambda _, r=ref, ri=ri: (dlg.close(),
                                    shift_in_row(state, series_id, issue_id, page_id, ri, r.panel_id, 1)))
                            if not pm.cells:
                                ui.button(icon='vertical_split').props('flat round dense size=xs') \
                                    .tooltip('Give it its own row below') \
                                    .on('click', lambda _, r=ref, ri=ri: (dlg.close(),
                                        own_row(state, series_id, issue_id, page_id, ri, r.panel_id)))
                            mb = ui.button(icon='drive_file_move').props('flat round dense size=xs') \
                                .tooltip('Move to another page / row')
                            with mb:
                                place_menu(state, series_id, issue_id, ref.scene_id, ref.panel_id)
                            ui.button(icon='close').props('flat round dense size=xs') \
                                .tooltip('Take it off the page (to the unplaced tray)') \
                                .on('click', lambda _, r=ref: (dlg.close(),
                                    unplace(state, series_id, issue_id, r.panel_id)))
        if not pm.rows:
            ui.label('An empty page — place panels from the unplaced tray.') \
                .classes('text-sm text-gray-500 q-mt-sm')
    dlg.open()


# ---- THE PRESSROOM -------------------------------------------------------

def pressroom(state, series_id: str, issue_id: str):
    """The last station before print: stitch the book, tend the unplaced
    tray, chase dangling refs.  The shelf up top displays the sheets; this
    is where loose panels get placed."""
    from gui.elements import caption_action, CrudButtonKind as _CK
    storage = state.storage
    pages = _pages(storage, series_id, issue_id)
    _has, _placed, unplaced, dangling = page_coverage(storage, series_id, issue_id)

    with ui.row().classes('w-full items-center').style('gap: 10px;'):
        caption_action("The pressroom", _CK.CREATE,
                       lambda _: (new_page_at_end(storage, series_id, issue_id),
                                  _receipt(state, "📄 added a blank page to the book")), 3)
        ui.button('Stitch the book', icon='auto_awesome_mosaic').props('unelevated dense no-caps') \
            .tooltip('Lay every panel onto pages automatically — reading order, '
                     'full pages, tall bands and splashes where they belong') \
            .on('click', lambda _: stitch_now(state, series_id, issue_id))
        if pages:
            ui.label(f"{len(pages)} page(s) — pacing lives in the page turn; "
                     f"click a sheet on the shelf to rearrange it").classes('text-xs text-gray-500')
        if dangling:
            ui.chip(f'{len(dangling)} dangling ref(s)', icon='report', color='orange') \
                .props('dense outline') \
                .tooltip('A page points at a deleted panel — open the page and remove it')

    if not pages and not unplaced:
        ui.label('No pages yet — break the scenes into panels, then stitch the book.') \
            .classes('text-sm text-gray-500')

    if unplaced:
        with ui.row().classes('w-full items-center q-mt-sm').style('gap: 8px;'):
            ui.label('UNPLACED').classes('comic-label-sm')
            ui.label(f"{len(unplaced)} panel(s) not on any page — they'd flow onto "
                     f"overflow pages at the end of the book") \
                .classes('text-xs text-orange-8')
        with ui.row().classes('w-full').style('gap: 8px; row-gap: 10px;'):
            for scene, panel in unplaced:
                with ui.card().classes('soft-card p-1 relative').style('width: 150px;'):
                    if panel.image and os.path.exists(panel.image):
                        ui.image(source=panel.image).style('height: 84px;').props('fit=cover')
                    else:
                        ui.label('unrendered').classes('text-xs text-gray-500 text-center w-full') \
                            .style('height: 84px; line-height: 84px;')
                    ui.button(icon='open_in_new').props('flat round dense size=xs') \
                        .classes('absolute top-1 right-1 z-10 bg-white/70 dark:bg-black/50') \
                        .tooltip('Open this panel on its light table') \
                        .on('click', lambda _, s=scene, p=panel:
                            open_panel(state, series_id, issue_id, s.scene_id, p.panel_id))
                    ui.label(f"{scene.name} · {panel.name}").classes('text-xs w-full') \
                        .style('overflow: hidden; text-overflow: ellipsis; white-space: nowrap;')
                    pb = ui.button('Place it', icon='post_add').props('outline dense size=sm no-caps') \
                        .classes('w-full')
                    with pb:
                        place_menu(state, series_id, issue_id, scene.scene_id, panel.panel_id)
