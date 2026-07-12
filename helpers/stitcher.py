"""
THE PAGE STITCHER: lay the whole issue onto pages, scene after scene in
reading order, with the same banding the studio's mosaic uses — rethought
for a printed comic page divided into a 6-wide x 10-tall unit grid.

A band is a horizontal slice of the page:
  * two panels side by side, the row's height chosen from their aspects —
    boxes keep the panel's TRUE aspect, so art never clips
  * a portrait panel leading a TALL BAND, two landscape panels stacked in
    the region beside it — the signature comics shape
  * a pair of portraits, three squares across, or a full-width splash

Panel SIZE is a per-aspect multiplier the author sets on the tile:
landscape and portrait come in 1x and 2x, squares in 1x, 2x and 3x —
a 2x panel commands its own band instead of pairing.

Bands stack until the page's 10 units are spent; leftover height breathes
as extra gutters and top/bottom margin (never by stretching panels — that
clipped art).  The stitcher owns geometry: editing a stitched page means
reordering its panels and re-stitching.
"""
import json
import os
from uuid import uuid4

from loguru import logger

from schema import Page, PanelCell, PanelRef

PAGE_UNITS_W, PAGE_UNITS_H = 6.0, 10.0
AR = {"landscape": 1.5, "portrait": 2 / 3, "square": 1.0}
GAP_MAX = 0.5   # slack becomes gutters between bands, up to this much each


def _is_portrait(a: float) -> bool:
    return a < 0.9


def _is_square(a: float) -> bool:
    return abs(a - 1.0) < 0.1


def size_mult(size, a: float) -> int:
    """The author's size as a multiplier, clamped to what the aspect offers:
    squares come in 1x/2x/3x, portrait and landscape in 1x/2x.  Legacy names
    (regular/large/splash/small) still read."""
    m = {"1x": 1, "2x": 2, "3x": 3,
         "small": 1, "regular": 1, "large": 2,
         "splash": 3 if _is_square(a) else 2}.get(size or "1x", 1)
    return min(m, 3 if _is_square(a) else 2)


def pack_bands(items: list[tuple]) -> list[dict]:
    """Pack (key, aspect_ratio[, size]) items into bands, reading order
    preserved.  Every box keeps its panel's true aspect — leftover width
    inside a band becomes symmetric side breathing, never a stretch.
    Each band: {"h": units, "cells": [(key, x, y_in_band, w, h)]}."""
    items = [(it[0], it[1], size_mult(it[2] if len(it) > 2 else None, it[1]))
             for it in items]

    def pairable(it):
        return it is not None and it[2] == 1

    def centered(cells_w, h, parts):
        """Lay parts (widths at height h) across the band, centered."""
        x = (PAGE_UNITS_W - cells_w) / 2
        out = []
        for key, w in parts:
            out.append((key, round(x, 3), 0.0, w, h))
            x += w
        return {"h": h, "cells": out}

    bands, i, n = [], 0, len(items)
    while i < n:
        key, a, m = items[i]
        nxt = items[i + 1] if i + 1 < n else None
        nx2 = items[i + 2] if i + 2 < n else None

        if m >= 2:
            if _is_square(a) and m >= 3:
                # the big square moment, inset on its own band
                bands.append({"h": 5.0, "cells": [(key, 0.5, 0.0, 5.0, 5.0)]})
                i += 1
            elif _is_portrait(a):
                if pairable(nxt) and pairable(nx2):
                    # a 2x portrait commands the band, two beats stacked
                    # beside it — each at its TRUE aspect (width 2), the
                    # column's slack breathing between them
                    h1, h2 = 2.0 / nxt[1], 2.0 / nx2[1]
                    lead = max(0.0, (6.0 - h1 - h2) / 3)
                    bands.append({"h": 6.0, "cells": [(key, 0.0, 0.0, 4.0, 6.0),
                                                      (nxt[0], 4.0, round(lead, 3), 2.0, round(h1, 3)),
                                                      (nx2[0], 4.0, round(2 * lead + h1, 3), 2.0, round(h2, 3))]})
                    i += 3
                else:
                    bands.append({"h": 6.0, "cells": [(key, 1.0, 0.0, 4.0, 6.0)]})
                    i += 1
            elif _is_square(a):
                if nxt is not None and _is_square(nxt[1]) and nxt[2] == 2:
                    bands.append({"h": 3.0, "cells": [(key, 0.0, 0.0, 3.0, 3.0),
                                                      (nxt[0], 3.0, 0.0, 3.0, 3.0)]})
                    i += 2
                else:
                    bands.append(centered(3.0, 3.0, [(key, 3.0)]))
                    i += 1
            else:
                # a 2x landscape takes the page width — a splash band
                bands.append({"h": 4.0, "cells": [(key, 0.0, 0.0, 6.0, 4.0)]})
                i += 1
            continue

        if _is_portrait(a):
            if pairable(nxt) and _is_portrait(nxt[1]):
                # portraits pair up, half the page tall
                bands.append({"h": 4.5, "cells": [(key, 0.0, 0.0, 3.0, 4.5),
                                                  (nxt[0], 3.0, 0.0, 3.0, 4.5)]})
                i += 2
            elif pairable(nxt) and pairable(nx2) and not _is_portrait(nxt[1]) and not _is_portrait(nx2[1]):
                # THE TALL BAND: a portrait beside two stacked landscapes
                bands.append({"h": 4.0, "cells": [(key, 0.0, 0.0, 8 / 3, 4.0),
                                                  (nxt[0], 8 / 3, 0.0, 10 / 3, 2.0),
                                                  (nx2[0], 8 / 3, 2.0, 10 / 3, 2.0)]})
                i += 3
            elif pairable(nxt):
                # portrait shares a 3-high row with one wide neighbor,
                # both at true aspect, breathing centered
                w2 = 3.0 * nxt[1]
                band = centered(2.0 + min(w2, 4.0), 3.0,
                                [(key, 2.0), (nxt[0], min(w2, 4.0))])
                bands.append(band)
                i += 2
            else:
                # a lone portrait closes the book inset, breathing around it
                bands.append(centered(3.0, 4.5, [(key, 3.0)]))
                i += 1
        else:
            if pairable(nxt) and not _is_portrait(nxt[1]):
                if (pairable(nx2) and _is_square(a) and _is_square(nxt[1])
                        and _is_square(nx2[1])):
                    # three squares across, a steady beat-beat-beat tier
                    bands.append({"h": 2.0, "cells": [(key, 0.0, 0.0, 2.0, 2.0),
                                                      (nxt[0], 2.0, 0.0, 2.0, 2.0),
                                                      (nx2[0], 4.0, 0.0, 2.0, 2.0)]})
                    i += 3
                else:
                    # two across at true aspect: height chosen so the pair
                    # spans the width when it can, else centered breathing
                    s = a + nxt[1]
                    h = max(2.0, min(3.0, PAGE_UNITS_W / s))
                    w1, w2 = h * a, h * nxt[1]
                    bands.append(centered(w1 + w2, h, [(key, w1), (nxt[0], w2)]))
                    i += 2
            else:
                # a wide panel with no partner takes the page width — a splash
                if _is_square(a):
                    bands.append(centered(4.0, 4.0, [(key, 4.0)]))
                else:
                    bands.append({"h": 4.0, "cells": [(key, 0.0, 0.0, 6.0, 4.0)]})
                i += 1
    return bands


def paginate(bands: list[dict]) -> list[list[dict]]:
    """Stack bands onto pages, breaking when the 10 units are spent."""
    pages, cur, used = [], [], 0.0
    for b in bands:
        if cur and used + b["h"] > PAGE_UNITS_H + 1e-6:
            pages.append(cur)
            cur, used = [], 0.0
        cur.append(b)
        used += b["h"]
    if cur:
        pages.append(cur)
    return pages


def justify(page_bands: list[dict], is_last: bool) -> list[tuple]:
    """Absolute cells for one page.  Slack breathes as extra gutters between
    bands (capped) and symmetric top/bottom margin — panels NEVER stretch,
    so art keeps its true aspect and nothing clips.  The last page keeps its
    natural height — a short final page is honest."""
    used = sum(b["h"] for b in page_bands)
    slack = 0.0 if is_last else max(0.0, PAGE_UNITS_H - used)
    n = len(page_bands)
    gap = min(slack / (n - 1), GAP_MAX) if n > 1 else 0.0
    lead = (slack - gap * (n - 1)) / 2
    cells, y = [], lead
    for b in page_bands:
        for key, x, yy, w, h in b["cells"]:
            cells.append((key, x, y + yy, w, h))
        y += b["h"] + gap
    return cells


def stitch_pages(storage, series_id: str, issue_id: str) -> list[Page]:
    """Pack EVERY scene's panels, in reading order, onto pages.  The flow
    breaks exactly where the open book breaks it — at a bare scene holding
    its place as a manuscript page, and at a full-page insert's anchor — so
    what prints IS what the issue view shows.  Returns the new Page objects
    (not yet saved)."""
    from helpers.binder import _reading_order
    from schema import Insert
    anchors = {i.after_scene_number
               for i in storage.read_all_objects(Insert, {"series_id": series_id,
                                                          "issue_id": issue_id})}
    segments, run = [], []
    for scene, panels in _reading_order(storage, series_id, issue_id):
        if panels:
            run += [((p.scene_id, p.panel_id), AR.get(p.aspect.value, 1.5),
                     getattr(p, 'size', None) or '1x') for p in panels]
        if (not panels or scene.scene_number in anchors) and run:
            segments.append(run)
            run = []
    if run:
        segments.append(run)
    if not segments:
        return []

    pages, n = [], 0
    for seg in segments:
        band_pages = paginate(pack_bands(seg))
        for pi, pb in enumerate(band_pages):
            n += 1
            cells_abs = justify(pb, is_last=(pi == len(band_pages) - 1))
            pages.append(Page(
                page_id=f"page-{n}", issue_id=issue_id, series_id=series_id,
                page_number=n,
                rows=[[PanelRef(scene_id=k[0], panel_id=k[1]) for k, *_ in b["cells"]]
                      for b in pb],
                cells=[PanelCell(scene_id=k[0], panel_id=k[1], x=round(x, 3), y=round(y, 3),
                                 w=round(w, 3), h=round(h, 3))
                       for k, x, y, w, h in cells_abs]))
    return pages


def apply_stitch(storage, series_id: str, issue_id: str) -> tuple[list[Page], list[Page]]:
    """Stitch and SAVE: snapshot the outgoing layout to a wastebasket JSON,
    replace it with the stitched pages.  Returns (new_pages, old_pages)."""
    new_pages = stitch_pages(storage, series_id, issue_id)
    old_pages = storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id},
                                         order_by="page_number")
    if not new_pages:
        return [], old_pages
    if old_pages:
        try:
            snap_dir = os.path.join(str(storage.base_path), "series", series_id, "issues", issue_id)
            os.makedirs(snap_dir, exist_ok=True)
            snap = os.path.join(snap_dir, f".trash--layout--{uuid4().hex[:6]}.json")
            with open(snap, "w") as fh:
                json.dump([p.model_dump() for p in old_pages], fh, indent=1)
            logger.info(f"page-layout snapshot: {snap}")
        except OSError as ex:
            logger.warning(f"layout snapshot skipped: {ex}")
    for old in old_pages:
        storage.delete_object(cls=Page, primary_key=old.primary_key)
    for page in new_pages:
        storage.create_object(data=page, overwrite=True)
    return new_pages, old_pages


def remember_stitch(storage, series_id: str, issue_id: str) -> None:
    """THE LAYOUT IS REMEMBERED: persist the current stitched pagination
    when it differs from what's stored — quietly, no receipts.  Never
    touches a hand-designed layout (rows without cells)."""
    stored = storage.read_all_objects(Page, {"series_id": series_id, "issue_id": issue_id},
                                      order_by="page_number")
    if stored and not all(p.cells for p in stored):
        return
    fresh = stitch_pages(storage, series_id, issue_id)

    def sig(pages):
        return [(p.page_number, [(c.panel_id, c.x, c.y, c.w, c.h) for c in p.cells])
                for p in pages]
    if sig(fresh) == sig(stored):
        return
    # write IN PLACE (overwrite same page ids) — layout pages are derived
    # data, and routing them through the wastebasket on every quiet sync
    # would bury the author's real deletes under page churn
    for page in fresh:
        storage.create_object(data=page, overwrite=True)
    fresh_ids = {p.page_id for p in fresh}
    for old in stored:
        if old.page_id not in fresh_ids:
            storage.delete_object(cls=Page, primary_key=old.primary_key)
    logger.info(f"remembered the stitched layout for {issue_id} ({len(fresh)} pages)")


def repack_page(storage, pm: Page) -> Page:
    """Re-stitch ONE page after an edit: its rows' flat sequence runs back
    through the band packer (no page break — a crowded page composes scaled).
    Rows become the new band grouping; cells the new geometry."""
    from schema import Panel
    items = []
    for row in pm.rows:
        for ref in row:
            panel = storage.read_object(Panel, {"series_id": pm.series_id, "issue_id": pm.issue_id,
                                                "scene_id": ref.scene_id, "panel_id": ref.panel_id})
            aspect = AR.get(panel.aspect.value, 1.5) if panel else 1.5
            items.append(((ref.scene_id, ref.panel_id), aspect,
                          (getattr(panel, 'size', None) or '1x') if panel else '1x'))
    bands = pack_bands(items)
    cells_abs = justify(bands, is_last=(sum(b["h"] for b in bands) < PAGE_UNITS_H))
    pm.rows = [[PanelRef(scene_id=k[0], panel_id=k[1]) for k, *_ in b["cells"]] for b in bands]
    pm.cells = [PanelCell(scene_id=k[0], panel_id=k[1], x=round(x, 3), y=round(y, 3),
                          w=round(w, 3), h=round(h, 3)) for k, x, y, w, h in cells_abs]
    return pm
