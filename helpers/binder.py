"""
Bind an issue into a book: compose the covers and the panels (in reading
order) onto comic pages and write a PDF.
"""
import os
from loguru import logger
from PIL import Image

from storage.generic import GenericStorage
from schema import Issue, SceneModel, Panel, Cover

# 6.625in x 10.25in at 150dpi — standard US comic trim.
PAGE_W, PAGE_H = 994, 1538
MARGIN = 40      # outer page margin
GUTTER = 28      # vertical space between panels on a page


def _reading_order(storage: GenericStorage, series_id: str, issue_id: str):
    """Yield (scene, [panels]) in reading order."""
    scenes = storage.read_all_objects(SceneModel, {"series_id": series_id, "issue_id": issue_id}, order_by="scene_number")
    for scene in scenes:
        panels = storage.read_all_objects(Panel, {"series_id": series_id, "issue_id": issue_id, "scene_id": scene.scene_id}, order_by="panel_number")
        yield scene, panels


def page_coverage(storage: GenericStorage, series_id: str, issue_id: str):
    """The truth about the page layout: which panels are PLACED on pages,
    which are UNPLACED (in the issue but on no page), and which page refs are
    DANGLING (point at panels that no longer exist).

    Returns (has_layout, placed_keys, unplaced, dangling) where unplaced is
    [(scene, panel)] in reading order and dangling is [(page_number, PanelRef)].
    """
    from schema import Page
    page_models = storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id},
                                           order_by="page_number")
    all_panels = {}
    for scene, panels in _reading_order(storage, series_id, issue_id):
        for panel in panels:
            all_panels[(scene.scene_id, panel.panel_id)] = (scene, panel)
    placed, dangling = set(), []
    for pm in page_models:
        for row in pm.rows:
            for ref in row:
                key = (ref.scene_id, ref.panel_id)
                if key in all_panels:
                    placed.add(key)
                else:
                    dangling.append((pm.page_number, ref))
    unplaced = [sp for key, sp in all_panels.items() if key not in placed]
    return bool(page_models), placed, unplaced, dangling


def collect_issue(storage: GenericStorage, series_id: str, issue_id: str):
    """
    Gather everything needed to bind the issue.

    Returns (front_cover_image, ordered_panel_images, back_cover_image, missing)
    where missing is a list of human-readable gaps (unrendered panels/covers).
    """
    missing = []
    covers: list[Cover] = storage.read_all_objects(Cover, {"series_id": series_id, "issue_id": issue_id})
    front = next((c.image for c in covers if c.location.value == "front" and c.image and os.path.exists(c.image)), None)
    back = next((c.image for c in covers if c.location.value == "back" and c.image and os.path.exists(c.image)), None)
    if front is None:
        missing.append("front cover render (generate_cover_image)")

    panel_images = []
    for scene, panels in _reading_order(storage, series_id, issue_id):
        for panel in panels:
            if panel.image and os.path.exists(panel.image):
                panel_images.append(panel.image)
            else:
                missing.append(f"panel {panel.panel_number} of scene '{scene.name}' is not rendered (generate_panel_image)")

    # a page layout that doesn't cover the issue is a SILENT story-killer —
    # say so, loudly, wherever collect_issue is consulted
    has_layout, _placed, unplaced, dangling = page_coverage(storage, series_id, issue_id)
    if has_layout:
        for scene, panel in unplaced:
            missing.append(f"panel {panel.panel_number} of scene '{scene.name}' is on NO page "
                           f"(layout_issue_pages) — it would be left out of the book")
        for page_number, ref in dangling:
            missing.append(f"page {page_number} references a panel that no longer exists "
                           f"({ref.panel_id[:8]}…) — it prints as an empty box")
    return front, panel_images, back, missing


def bind_issue_pdf(storage: GenericStorage, series_id: str, issue_id: str, output_path: str) -> tuple[int, list[str]]:
    """
    Compose the issue into a PDF: covers full-bleed, interior panels stacked
    down each page in reading order with gutters, new page when full.

    Returns (page_count, missing).
    """
    front, panel_images, back, missing = collect_issue(storage, series_id, issue_id)

    pages: list[Image.Image] = []

    def full_bleed(path):
        img = Image.open(path).convert("RGB")
        scale = max(PAGE_W / img.width, PAGE_H / img.height)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        x, y = (img.width - PAGE_W) // 2, (img.height - PAGE_H) // 2
        return img.crop((x, y, x + PAGE_W, y + PAGE_H))

    if front:
        pages.append(full_bleed(front))

    layout = layout_pages(storage, series_id, issue_id)
    if layout:
        # A page layout exists: compose each page as its designed grid.
        for page_model, rows in layout:
            pages.append(_compose_page(rows))
        # panels the layout forgot are NEVER silently dropped: they flow onto
        # extra pages at the end (and collect_issue reports them as gaps)
        _has, _placed, unplaced, _dang = page_coverage(storage, series_id, issue_id)
        leftover_images = [p.image for _s, p in unplaced if p.image and os.path.exists(p.image)]
        if leftover_images:
            page = None
            cursor = MARGIN
            inner_w = PAGE_W - 2 * MARGIN
            for path in leftover_images:
                img = Image.open(path).convert("RGB")
                h = int(img.height * inner_w / img.width)
                if page is None or cursor + h > PAGE_H - MARGIN:
                    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
                    pages.append(page)
                    cursor = MARGIN
                page.paste(img.resize((inner_w, h), Image.LANCZOS), (MARGIN, cursor))
                cursor += h + GUTTER
    else:
        # No layout yet: flow panels down each page in reading order.
        page = None
        cursor = MARGIN
        inner_w = PAGE_W - 2 * MARGIN
        for path in panel_images:
            img = Image.open(path).convert("RGB")
            h = int(img.height * inner_w / img.width)
            if page is None or cursor + h > PAGE_H - MARGIN:
                page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
                pages.append(page)
                cursor = MARGIN
            page.paste(img.resize((inner_w, h), Image.LANCZOS), (MARGIN, cursor))
            cursor += h + GUTTER

    if back:
        pages.append(full_bleed(back))

    if not pages:
        return 0, missing

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pages[0].save(output_path, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    logger.info(f"Bound issue {issue_id} to {output_path} ({len(pages)} pages)")
    return len(pages), missing


def layout_pages(storage: GenericStorage, series_id: str, issue_id: str):
    """
    Resolve the issue's designed page layout, if any: a list of
    (Page, rows) where rows mirror Page.rows but hold rendered image paths
    (None for unrendered panels).
    """
    from schema import Page
    page_models = storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id}, order_by="page_number")
    if not page_models:
        return []
    resolved = []
    for pm in page_models:
        rows = []
        for row in pm.rows:
            paths = []
            for ref in row:
                panel = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                                    "scene_id": ref.scene_id, "panel_id": ref.panel_id})
                ok = panel and panel.image and os.path.exists(panel.image)
                paths.append(panel.image if ok else None)
            rows.append(paths)
        resolved.append((pm, rows))
    return resolved


def _compose_page(rows: list[list[str | None]]) -> "Image.Image":
    """
    Compose one designed page: each row's panels share a height chosen so the
    row spans the page width; rows are scaled uniformly if they overflow.
    Unrendered panels appear as light placeholder boxes.
    """
    inner_w = PAGE_W - 2 * MARGIN
    prepared: list[tuple[int, list[tuple["Image.Image | None", int]]]] = []
    total_h = 0
    for row in rows:
        imgs, ratios = [], []
        for path in row:
            if path:
                im = Image.open(path).convert("RGB")
                imgs.append(im)
                ratios.append(im.width / im.height)
            else:
                imgs.append(None)
                ratios.append(1.0)
        if not row or sum(ratios) <= 0:
            continue   # an empty row is a layout bug reported upstream — skip, don't crash
        usable = inner_w - GUTTER * (len(row) - 1)
        row_h = int(usable / sum(ratios))
        prepared.append((row_h, list(zip(imgs, [int(row_h * r) for r in ratios]))))
        total_h += row_h
    total_h += GUTTER * (len(rows) - 1)

    scale = min(1.0, (PAGE_H - 2 * MARGIN) / total_h) if total_h else 1.0
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    y = MARGIN
    for row_h, cells in prepared:
        h = int(row_h * scale)
        x = MARGIN
        for im, w0 in cells:
            w = int(w0 * scale)
            if im is not None:
                page.paste(im.resize((w, h), Image.LANCZOS), (x, y))
            else:
                from PIL import ImageDraw
                d = ImageDraw.Draw(page)
                d.rectangle([x, y, x + w, y + h], outline=(180, 180, 180), width=3, fill=(240, 240, 240))
            x += w + GUTTER
        y += h + GUTTER
    return page
