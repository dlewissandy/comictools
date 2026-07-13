"""
Bind an issue into a book: compose the covers and the panels (in reading
order) onto comic pages and write a PDF.

The single source of truth is compose_book(): every sheet of the finished
book, in order — front cover, inside-front (indicia), interior pages with
folios, overflow pages, inside-back, back.  The PDF, the CBZ, and THE
READING ROOM all consume the same sheets, so what you read IS the book.
"""
import hashlib
import io
import json
import os
import re
import zipfile
from functools import lru_cache

from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from storage.generic import GenericStorage
from schema import Issue, SceneModel, Panel, Cover, Series, Publisher

# 6.625in x 10.1875in at 150dpi — US standard comic trim.  The live area
# is the 6x10-unit grid (1 unit = 1 inch); the difference is the fudge
# room for margins.
PAGE_W, PAGE_H = 994, 1528
MARGIN_X = (PAGE_W - 900) // 2    # 47px ≈ 5/16in side margins
MARGIN_Y = (PAGE_H - 1500) // 2   # 14px top/bottom
MARGIN = MARGIN_X                 # text blocks (indicia, credits) keep this inset
GUTTER = 28      # space between panels on a page


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


# ---------------------------------------------------------------------------
# type on the page: folios, credits, indicia
# ---------------------------------------------------------------------------

@lru_cache(maxsize=16)
def _font(size: int) -> "ImageFont.FreeTypeFont":
    for name in ("Helvetica.ttc", "HelveticaNeue.ttc", "Arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                      # ancient Pillow: tiny bitmap font
        return ImageFont.load_default()


def _wrap(draw: "ImageDraw.ImageDraw", text: str, font, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _center_text(draw: "ImageDraw.ImageDraw", cx: int, y: int, text: str, font, fill) -> int:
    """Draw text centered on cx with its top at y; return the new y below it."""
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (r - l) / 2, y - t), text, font=font, fill=fill)
    return y + (b - t)


def _folio_stamp(page: "Image.Image", number: int) -> "Image.Image":
    """The folio: a quiet page number centered in the bottom margin."""
    draw = ImageDraw.Draw(page)
    _center_text(draw, PAGE_W // 2, PAGE_H - 30, str(number), _font(20), (140, 140, 140))
    return page


def _small_print(issue: Issue, series: Series | None, publisher: Publisher | None) -> str:
    """The indicia paragraph, the way real comics run it in tiny type."""
    parts = [f"{(series.name if series else issue.name).upper()} No. {issue.issue_number}."]
    if issue.publication_date:
        parts.append(f"Published {issue.publication_date}.")
    if publisher:
        parts.append(f"A {publisher.name} publication.")
    if issue.price:
        parts.append(f"Cover price ${issue.price:.2f}.")
    parts.append("All characters and events in this issue are entirely fictional.  "
                 "Any similarity to actual persons is purely coincidental.")
    return "  ".join(parts)


def _indicia_sheet(issue: Issue, series: Series | None, publisher: Publisher | None) -> "Image.Image":
    """A composed inside-front page: title block, the credits, the indicia.
    Used when the issue has no inside-front cover art of its own."""
    page = Image.new("RGB", (PAGE_W, PAGE_H), (250, 247, 240))
    draw = ImageDraw.Draw(page)
    cx, inner_w = PAGE_W // 2, PAGE_W - 2 * MARGIN
    ink, soft = (45, 42, 38), (120, 114, 104)

    y = 260
    for line in _wrap(draw, (series.name if series else issue.name).upper(), _font(68), inner_w):
        y = _center_text(draw, cx, y, line, _font(68), ink) + 10
    y += 18
    draw.line([(cx - 150, y), (cx + 150, y)], fill=soft, width=3)
    y += 40
    for line in _wrap(draw, f"No. {issue.issue_number}  ·  {issue.name}", _font(38), inner_w):
        y = _center_text(draw, cx, y, line, _font(38), ink) + 8

    credits = [(role, value) for role, value in (
        ("WRITER", issue.writer), ("ARTIST", issue.artist),
        ("COLORIST", issue.colorist), ("CREATED BY", issue.creative_minds),
    ) if value]
    if credits:
        y = max(y + 120, 640)
        for role, value in credits:
            y = _center_text(draw, cx, y, role, _font(24), soft) + 10
            for line in _wrap(draw, value, _font(34), inner_w):
                y = _center_text(draw, cx, y, line, _font(34), ink) + 6
            y += 44

    small = _font(17)
    lines = _wrap(draw, _small_print(issue, series, publisher), small, inner_w)
    line_h = 24
    y = PAGE_H - MARGIN - 20 - line_h * len(lines)
    for line in lines:
        y = _center_text(draw, cx, y, line, small, soft) + 7
    return page


def _stamp_indicia(art: "Image.Image", issue: Issue, series: Series | None,
                   publisher: Publisher | None) -> "Image.Image":
    """Run the indicia small print in a translucent band along the bottom of
    inside-front cover art — where real books carry it."""
    base = art.convert("RGBA")
    draw = ImageDraw.Draw(base)
    small = _font(17)
    inner_w = PAGE_W - 2 * MARGIN
    lines = _wrap(draw, _small_print(issue, series, publisher), small, inner_w)
    line_h, pad = 24, 18
    band_h = line_h * len(lines) + 2 * pad
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rectangle([0, base.height - band_h, base.width, base.height], fill=(255, 255, 255, 210))
    out = Image.alpha_composite(base, overlay)
    draw = ImageDraw.Draw(out)
    y = base.height - band_h + pad
    for line in lines:
        y = _center_text(draw, base.width // 2, y, line, small, (60, 58, 54)) + 7
    return out.convert("RGB")


def _insert_text_sheet(ins) -> "Image.Image":
    """A written insert (the mailbag's letters, ad copy) typeset as a page:
    masthead caption up top, the text flowed beneath — the way letters pages
    actually ran."""
    page = Image.new("RGB", (PAGE_W, PAGE_H), (250, 247, 240))
    draw = ImageDraw.Draw(page)
    cx, inner_w = PAGE_W // 2, PAGE_W - 2 * MARGIN
    ink, soft = (45, 42, 38), (120, 114, 104)
    y = 120
    for line in _wrap(draw, ins.name.upper(), _font(44), inner_w):
        y = _center_text(draw, cx, y, line, _font(44), ink) + 8
    y += 10
    draw.line([(cx - 150, y), (cx + 150, y)], fill=soft, width=3)
    y += 34
    body = _font(20)
    line_h = 28
    for para in (ins.description or '').split("\n"):
        if not para.strip():
            y += line_h // 2
            continue
        for line in _wrap(draw, para.strip(), body, inner_w):
            if y > PAGE_H - MARGIN - line_h:
                break
            draw.text((MARGIN, y), line, font=body, fill=ink)
            y += line_h
    _center_text(draw, cx, PAGE_H - 34, f"— the {ins.kind} —", _font(16), soft)
    return page


# ---------------------------------------------------------------------------
# composing the book
# ---------------------------------------------------------------------------

def _full_bleed(path: str) -> "Image.Image":
    img = Image.open(path).convert("RGB")
    scale = max(PAGE_W / img.width, PAGE_H / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    x, y = (img.width - PAGE_W) // 2, (img.height - PAGE_H) // 2
    return img.crop((x, y, x + PAGE_W, y + PAGE_H))


def _flow_pages(image_paths: list[str]) -> list["Image.Image"]:
    """Flow panels down each page in reading order — the layout-less binding,
    also used for overflow pages carrying panels the layout forgot."""
    pages: list[Image.Image] = []
    page, cursor = None, MARGIN_Y
    inner_w = PAGE_W - 2 * MARGIN_X
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        h = int(img.height * inner_w / img.width)
        if page is None or cursor + h > PAGE_H - MARGIN_Y:
            page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
            pages.append(page)
            cursor = MARGIN_Y
        page.paste(img.resize((inner_w, h), Image.LANCZOS), (MARGIN_X, cursor))
        cursor += h + GUTTER
    return pages


def compose_book(storage: GenericStorage, series_id: str, issue_id: str
                 ) -> tuple[list[tuple[str, "Image.Image"]], list[str]]:
    """
    Every sheet of the finished book, in order:

      front cover → inside-front (cover art stamped with the indicia, or a
      composed credits/indicia page) → interior pages (the designed grids, or
      panels flowed in reading order), folios stamped → overflow pages for
      rendered panels the layout forgot → inside-back cover → back cover.

    Returns (sheets, missing) where sheets is [(label, PIL.Image)].
    """
    front, panel_images, back, missing = collect_issue(storage, series_id, issue_id)
    covers: list[Cover] = storage.read_all_objects(Cover, {"series_id": series_id, "issue_id": issue_id})

    def cover_art(location: str):
        return next((c.image for c in covers
                     if c.location.value == location and c.image and os.path.exists(c.image)), None)

    issue: Issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    series: Series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
    publisher = None
    if series and series.publisher_id:
        publisher = storage.read_object(cls=Publisher, primary_key={"publisher_id": series.publisher_id})

    # ---- interior pages, folios stamped
    interior: list[tuple[str, Image.Image]] = []
    layout = layout_pages(storage, series_id, issue_id)
    folio = 0
    if layout:
        for page_model, rows in layout:
            folio = page_model.page_number
            if page_model.cells:
                # a STITCHED page: exact boxes on the 6x10 unit grid
                img = _compose_page_cells(resolve_cells(storage, series_id, issue_id, page_model))
            else:
                img = _compose_page(rows)
            interior.append((f"page {folio}", _folio_stamp(img, folio)))
        # panels the layout forgot are NEVER silently dropped: they flow onto
        # extra pages at the end (and collect_issue reports them as gaps)
        _has, _placed, unplaced, _dang = page_coverage(storage, series_id, issue_id)
        leftovers = [p.image for _s, p in unplaced if p.image and os.path.exists(p.image)]
        for page in _flow_pages(leftovers):
            folio += 1
            interior.append((f"page {folio} (overflow)", _folio_stamp(page, folio)))
    else:
        for page in _flow_pages(panel_images):
            folio += 1
            interior.append((f"page {folio}", _folio_stamp(page, folio)))

    # FULL-PAGE INSERTS: posters, ads, pin-ups, the mailbag — each anchored
    # after a scene, slotted between interior pages (unfolioed, like the
    # real thing)
    from schema import Insert
    inserts = sorted(storage.read_all_objects(Insert, {"series_id": series_id, "issue_id": issue_id}),
                     key=lambda i: (i.after_scene_number, i.insert_id))
    if inserts:
        scene_no = {sc.scene_id: sc.scene_number
                    for sc, _p in _reading_order(storage, series_id, issue_id)}
        from schema import Page as _Page
        page_models = storage.read_all_objects(_Page, {"series_id": series_id, "issue_id": issue_id},
                                               order_by="page_number")
        page_scenes = [[scene_no.get(r.scene_id, 0) for row in pm.rows for r in row]
                       for pm in page_models]
        for ins in reversed(inserts):
            # after the LAST page carrying a panel of the anchored scene (or
            # any earlier scene) — exactly where the open book slots it
            at = 0
            for pi, nums in enumerate(page_scenes):
                if any(0 < num <= ins.after_scene_number for num in nums):
                    at = pi + 1
            if ins.image and os.path.exists(ins.image):
                sheet = _full_bleed(ins.image)
            elif ins.kind == 'mailbag' and (ins.description or '').strip():
                # only the MAILBAG's description IS the page (letters and
                # replies) — it prints typeset until it's inked.  Any other
                # insert's description is a render BRIEF: production notes
                # that must never reach the page
                sheet = _insert_text_sheet(ins)
                missing.append(f"insert '{ins.name}' is not rendered (generate_insert_art)")
            else:
                sheet = Image.new("RGB", (PAGE_W, PAGE_H), (244, 240, 232))
                d = ImageDraw.Draw(sheet)
                _center_text(d, PAGE_W // 2, PAGE_H // 2 - 40,
                             ins.name.upper(), _font(40), (150, 144, 134))
                _center_text(d, PAGE_W // 2, PAGE_H // 2 + 20,
                             f"({ins.kind} — not rendered yet)", _font(22), (170, 164, 154))
                missing.append(f"insert '{ins.name}' is not rendered (generate_insert_art)")
            interior.insert(min(at, len(interior)), (f"insert — {ins.name}", sheet))

    if not interior and not front:
        return [], missing

    sheets: list[tuple[str, Image.Image]] = []
    if front:
        sheets.append(("front cover", _full_bleed(front)))
    inside_front = cover_art("inside-front")
    if inside_front:
        sheets.append(("inside front cover",
                       _stamp_indicia(_full_bleed(inside_front), issue, series, publisher)))
    elif issue is not None:
        sheets.append(("indicia", _indicia_sheet(issue, series, publisher)))
    sheets += interior
    inside_back = cover_art("inside-back")
    if inside_back:
        sheets.append(("inside back cover", _full_bleed(inside_back)))
    if back:
        sheets.append(("back cover", _full_bleed(back)))
    return sheets, missing


def bind_issue_pdf(storage: GenericStorage, series_id: str, issue_id: str, output_path: str) -> tuple[int, list[str]]:
    """
    Bind the issue into a PDF book — the sheets from compose_book, saved as
    one page each.  Returns (page_count, missing).
    """
    sheets, missing = compose_book(storage, series_id, issue_id)
    if not sheets:
        return 0, missing
    pages = [img for _label, img in sheets]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pages[0].save(output_path, "PDF", save_all=True, append_images=pages[1:], resolution=150)
    logger.info(f"Bound issue {issue_id} to {output_path} ({len(pages)} pages)")
    return len(pages), missing


def bind_issue_cbz(storage: GenericStorage, series_id: str, issue_id: str, output_path: str) -> tuple[int, list[str]]:
    """
    Bind the issue into a CBZ (comic book archive: a zip of page images in
    reading order) — the format every comic reader app opens natively.
    Returns (page_count, missing).
    """
    sheets, missing = compose_book(storage, series_id, issue_id)
    if not sheets:
        return 0, missing
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_STORED) as z:
        for i, (label, img) in enumerate(sheets):
            slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=92)
            z.writestr(f"{i:03d}-{slug}.jpg", buf.getvalue())
    logger.info(f"Bound issue {issue_id} to {output_path} ({len(sheets)} pages)")
    return len(sheets), missing


# ---------------------------------------------------------------------------
# THE READING ROOM's sheets — same composition, cached as files
# ---------------------------------------------------------------------------

def book_signature(storage: GenericStorage, series_id: str, issue_id: str) -> str:
    """A fingerprint of everything that shapes the composed book: issue
    metadata (the indicia), covers, page layout, and every panel's art."""
    from schema import Page

    def stamp(path):
        try:
            return f"{path}:{os.path.getmtime(path):.0f}"
        except OSError:
            return f"{path}:gone"

    parts = []
    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    parts.append(issue.model_dump_json() if issue else "no-issue")
    series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
    parts.append(series.name if series else "")
    from schema import Insert, Story
    for st in sorted(storage.read_all_objects(Story, {"series_id": series_id, "issue_id": issue_id}),
                     key=lambda s: s.story_id):
        # the text itself feeds the md5 below — never the salted builtin hash
        parts.append(f"story:{st.story_id}#{st.story_number}={st.name}\n{st.text}")
    for ins in sorted(storage.read_all_objects(Insert, {"series_id": series_id, "issue_id": issue_id}),
                      key=lambda i: i.insert_id):
        parts.append(f"insert:{ins.insert_id}@{ins.after_scene_number}="
                     f"{stamp(ins.image) if ins.image else 'none'}")
    for cover in sorted(storage.read_all_objects(Cover, {"series_id": series_id, "issue_id": issue_id}),
                        key=lambda c: c.cover_id):
        parts.append(f"{cover.location.value}={stamp(cover.image) if cover.image else 'none'}")
    for pm in storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id},
                                       order_by="page_number"):
        parts.append(f"page{pm.page_number}:" + json.dumps(
            [[(r.scene_id, r.panel_id) for r in row] for row in pm.rows])
            + json.dumps([(c.panel_id, c.x, c.y, c.w, c.h) for c in pm.cells]))
    for scene, panels in _reading_order(storage, series_id, issue_id):
        for p in panels:
            if p.image:
                face = stamp(p.image)
            else:
                # an unprinted panel's face is its ROUGH — table changes
                # must refresh the cached proof
                from helpers.rough_face import rough_signature
                face = f"rough:{rough_signature(p, scene) or 'brief'}"
            parts.append(f"{scene.scene_id}/{p.panel_id}#{p.panel_number}@{p.aspect.value}={face}")
    return hashlib.md5("\n".join(parts).encode()).hexdigest()[:16]


def reader_sheets(storage: GenericStorage, series_id: str, issue_id: str
                  ) -> tuple[list[tuple[str, str]], list[str]]:
    """
    The book's sheets as image FILES for THE READING ROOM — composed with the
    exact math that binds the PDF, cached on disk by content signature so
    repeat visits open instantly.  Returns ([(label, path)], missing).
    """
    sig = book_signature(storage, series_id, issue_id)
    out_dir = os.path.join(str(storage.base_path), "series", series_id, "issues", issue_id,
                           "exports", "sheets")
    manifest_path = os.path.join(out_dir, "manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path) as f:
                data = json.load(f)
            if data.get("sig") == sig and all(os.path.exists(p) for _l, p in data.get("sheets", [])):
                return [(l, p) for l, p in data["sheets"]], data.get("missing", [])
        except (json.JSONDecodeError, OSError):
            pass

    sheets, missing = compose_book(storage, series_id, issue_id)
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):          # stale sheets from the last composition
        if name.endswith(".jpg"):
            os.remove(os.path.join(out_dir, name))
    entries: list[tuple[str, str]] = []
    for i, (label, img) in enumerate(sheets):
        path = os.path.join(out_dir, f"{i:03d}.jpg")
        img.save(path, "JPEG", quality=90)
        entries.append((label, path))
    with open(manifest_path, "w") as f:
        json.dump({"sig": sig, "sheets": entries, "missing": missing}, f)
    return entries, missing


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
            cells = []
            for ref in row:
                panel = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                                    "scene_id": ref.scene_id, "panel_id": ref.panel_id})
                ok = panel and panel.image and os.path.exists(panel.image)
                label = f"panel {panel.panel_number} — {panel.name}" if panel else "missing panel"
                img = panel.image if ok else None
                if img is None and panel is not None:
                    # THE PANEL'S TRUEST FACE, on hand-designed pages too:
                    # no print yet but a rough on the table — the page shows
                    # the rough instead of a gray hole
                    from helpers.rough_face import rough_face
                    from schema import SceneModel as _Scene
                    scene = storage.read_object(_Scene, {"series_id": series_id, "issue_id": issue_id,
                                                         "scene_id": ref.scene_id})
                    rf = rough_face(storage, panel, scene)
                    if rf:
                        img = rf
                        label = f"ROUGH · {label}"
                cells.append((img, label))
            rows.append(cells)
        resolved.append((pm, rows))
    return resolved


def resolve_cells(storage: GenericStorage, series_id: str, issue_id: str, pm) -> list[tuple]:
    """A stitched page's cells resolved to (image_path_or_None, x, y, w, h,
    label) — the label names an unrendered panel right on the placeholder."""
    specs = []
    for c in pm.cells:
        panel = storage.read_object(Panel, {"series_id": series_id, "issue_id": issue_id,
                                            "scene_id": c.scene_id, "panel_id": c.panel_id})
        ok = panel and panel.image and os.path.exists(panel.image)
        label = f"panel {panel.panel_number} — {panel.name}" if panel else "missing panel"
        img = panel.image if ok else None
        if img is None and panel is not None:
            # THE PANEL'S TRUEST FACE: no print yet, but a rough on the
            # table — the proof shows the rough, stamped as one, instead
            # of a gray hole
            from helpers.rough_face import rough_face
            from schema import SceneModel as _Scene
            scene = storage.read_object(_Scene, {"series_id": series_id, "issue_id": issue_id,
                                                 "scene_id": c.scene_id})
            rf = rough_face(storage, panel, scene)
            if rf:
                img = rf
                label = f"ROUGH · {label}"
        specs.append((img, c.x, c.y, c.w, c.h, label))
    return specs


def _compose_page_cells(cells: list[tuple]) -> "Image.Image":
    """
    Compose one STITCHED page: each cell is an exact box on the 6-wide x
    10-tall unit grid.  Art is scaled-to-cover and center-cropped into its
    box (never distorted); unrendered panels print as placeholder boxes.
    A crowded page (units past 10 after an edit) scales to fit the trim.
    """
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    if not cells:
        return page
    draw = ImageDraw.Draw(page)
    grid_h = max(10.0, max(y + h for _p, _x, y, _w, h, *_ in cells))
    ux = (PAGE_W - 2 * MARGIN_X) / 6.0
    uy = (PAGE_H - 2 * MARGIN_Y) / grid_h
    for path, x, y, w, h, *extra in cells:
        left = MARGIN_X + x * ux + (GUTTER / 2 if x > 0.05 else 0)
        right = MARGIN_X + (x + w) * ux - (GUTTER / 2 if x + w < 5.95 else 0)
        top = MARGIN_Y + y * uy + (GUTTER / 2 if y > 0.05 else 0)
        bottom = MARGIN_Y + (y + h) * uy - (GUTTER / 2 if y + h < grid_h - 0.05 else 0)
        bw, bh = max(1, round(right - left)), max(1, round(bottom - top))
        if path:
            im = Image.open(path).convert("RGB")
            s = max(bw / im.width, bh / im.height)
            im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
            cx, cy = (im.width - bw) // 2, (im.height - bh) // 2
            page.paste(im.crop((cx, cy, cx + bw, cy + bh)), (round(left), round(top)))
        else:
            draw.rectangle([left, top, left + bw, top + bh],
                           outline=(180, 180, 180), width=3, fill=(240, 240, 240))
            # the placeholder NAMES what belongs here — a gray box that
            # says which panel is missing is a to-do, not a mystery
            label = extra[0] if extra else ""
            if label:
                f = _font(18)
                for li, line in enumerate(_wrap(draw, label, f, bw - 24)[:3]):
                    _center_text(draw, round(left + bw / 2),
                                 round(top + bh / 2) - 24 + li * 26, line, f, (150, 146, 138))
    return page


def _compose_page(rows: list[list[tuple[str | None, str | None]]]) -> "Image.Image":
    """
    Compose one designed page: each row's (image path, label) panels share a
    height chosen so the row spans the page width; rows are scaled uniformly
    if they overflow.  An unrendered panel prints as a placeholder box that
    NAMES what belongs there — a to-do, not a mystery.
    """
    inner_w = PAGE_W - 2 * MARGIN_X
    prepared: list[tuple[int, list[tuple["Image.Image | None", int, str]]]] = []
    total_h = 0
    for row in rows:
        imgs, ratios, labels = [], [], []
        for path, label in row:
            if path:
                im = Image.open(path).convert("RGB")
                imgs.append(im)
                ratios.append(im.width / im.height)
            else:
                imgs.append(None)
                ratios.append(1.0)
            labels.append(label or "")
        if not row or sum(ratios) <= 0:
            continue   # an empty row is a layout bug reported upstream — skip, don't crash
        usable = inner_w - GUTTER * (len(row) - 1)
        row_h = int(usable / sum(ratios))
        prepared.append((row_h, list(zip(imgs, [int(row_h * r) for r in ratios], labels))))
        total_h += row_h
    total_h += GUTTER * (len(rows) - 1)

    scale = min(1.0, (PAGE_H - 2 * MARGIN_Y) / total_h) if total_h else 1.0
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    y = MARGIN_Y
    for row_h, cells in prepared:
        h = int(row_h * scale)
        x = MARGIN_X
        for im, w0, label in cells:
            w = int(w0 * scale)
            if im is not None:
                page.paste(im.resize((w, h), Image.LANCZOS), (x, y))
            else:
                d = ImageDraw.Draw(page)
                d.rectangle([x, y, x + w, y + h], outline=(180, 180, 180), width=3, fill=(240, 240, 240))
                if label:
                    f = _font(18)
                    for li, line in enumerate(_wrap(d, label, f, w - 24)[:3]):
                        _center_text(d, round(x + w / 2),
                                     round(y + h / 2) - 24 + li * 26, line, f, (150, 146, 138))
            x += w + GUTTER
        y += h + GUTTER
    return page
