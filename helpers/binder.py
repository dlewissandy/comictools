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

    # Interior: stack panels down the page; break when the next doesn't fit.
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
