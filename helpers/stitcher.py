"""
THE PAGE STITCHER: lay the whole issue onto pages, scene after scene in
reading order, with the same banding the studio's mosaic uses — rethought
for a printed comic page divided into a 6-wide x 10-tall unit grid.

A band is a horizontal slice of the page:
  * two panels side by side, the row's height chosen from their aspects and
    the pair stretched to close the page width (art crops to fill, never
    distorts)
  * a portrait panel leading a TALL BAND, two landscape panels stacked in
    the region beside it — the signature comics shape
  * a pair of portraits, three squares across, or a full-width splash

Bands stack until the page's 10 units are spent; the leftover justifies
vertically so every page prints full.  The stitcher owns geometry: editing
a stitched page means reordering its panels and re-stitching.
"""
import json
import os
from uuid import uuid4

from loguru import logger

from schema import Page, PanelCell, PanelRef

PAGE_UNITS_W, PAGE_UNITS_H = 6.0, 10.0
AR = {"landscape": 1.5, "portrait": 2 / 3, "square": 1.0}
MAX_STRETCH = 1.15   # never blow a sparse page up more than this


def _is_portrait(a: float) -> bool:
    return a < 0.9


def pack_bands(items: list[tuple]) -> list[dict]:
    """Pack (key, aspect_ratio) items into bands, reading order preserved.
    Each band: {"h": units, "cells": [(key, x, y_in_band, w, h)]}."""
    bands, i, n = [], 0, len(items)
    while i < n:
        key, a = items[i]
        nxt = items[i + 1] if i + 1 < n else None
        nx2 = items[i + 2] if i + 2 < n else None
        if _is_portrait(a):
            if nxt and _is_portrait(nxt[1]):
                # portraits pair up, half the page tall
                bands.append({"h": 4.5, "cells": [(key, 0.0, 0.0, 3.0, 4.5),
                                                  (nxt[0], 3.0, 0.0, 3.0, 4.5)]})
                i += 2
            elif nxt and nx2 and not _is_portrait(nxt[1]) and not _is_portrait(nx2[1]):
                # THE TALL BAND: a portrait beside two stacked landscapes
                bands.append({"h": 4.0, "cells": [(key, 0.0, 0.0, 8 / 3, 4.0),
                                                  (nxt[0], 8 / 3, 0.0, 10 / 3, 2.0),
                                                  (nx2[0], 8 / 3, 2.0, 10 / 3, 2.0)]})
                i += 3
            elif nxt:
                # portrait rules a shared row beside one wide neighbor
                bands.append({"h": 3.0, "cells": [(key, 0.0, 0.0, 2.0, 3.0),
                                                  (nxt[0], 2.0, 0.0, 4.0, 3.0)]})
                i += 2
            else:
                # a lone portrait closes the book inset, breathing room around it
                bands.append({"h": 4.5, "cells": [(key, 1.5, 0.0, 3.0, 4.5)]})
                i += 1
        else:
            if nxt and not _is_portrait(nxt[1]):
                if (nx2 and abs(a - 1) < 0.1 and abs(nxt[1] - 1) < 0.1
                        and abs(nx2[1] - 1) < 0.1):
                    # three squares across, a steady beat-beat-beat tier
                    bands.append({"h": 2.0, "cells": [(key, 0.0, 0.0, 2.0, 2.0),
                                                      (nxt[0], 2.0, 0.0, 2.0, 2.0),
                                                      (nx2[0], 4.0, 0.0, 2.0, 2.0)]})
                    i += 3
                else:
                    # two across: height from their aspects, stretched to close
                    # the width (the crop is mild and the page stays honest)
                    s = a + nxt[1]
                    h = max(2.0, min(3.0, PAGE_UNITS_W / s))
                    w1 = PAGE_UNITS_W * a / s
                    bands.append({"h": h, "cells": [(key, 0.0, 0.0, w1, h),
                                                    (nxt[0], w1, 0.0, PAGE_UNITS_W - w1, h)]})
                    i += 2
            else:
                # a wide panel with no partner takes the page width — a splash
                if abs(a - 1) < 0.1:
                    bands.append({"h": 4.0, "cells": [(key, 0.5, 0.0, 5.0, 4.0)]})
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
    """Absolute cells for one page: bands stretch a little (capped) and the
    remaining slack spreads BETWEEN bands so the page prints full.  The last
    page keeps its natural height — a short final page is honest."""
    used = sum(b["h"] for b in page_bands)
    scale = 1.0 if is_last or used <= 0 else min(PAGE_UNITS_H / used, MAX_STRETCH)
    slack = 0.0 if is_last else max(0.0, PAGE_UNITS_H - used * scale)
    gap = slack / (len(page_bands) - 1) if len(page_bands) > 1 else 0.0
    cells, y = [], 0.0
    for b in page_bands:
        for key, x, yy, w, h in b["cells"]:
            cells.append((key, x, y + yy * scale, w, h * scale))
        y += b["h"] * scale + gap
    return cells


def stitch_pages(storage, series_id: str, issue_id: str) -> list[Page]:
    """Pack EVERY scene's panels, in reading order, onto pages.  Returns the
    new Page objects (not yet saved)."""
    from helpers.binder import _reading_order
    items = []
    for scene, panels in _reading_order(storage, series_id, issue_id):
        for p in panels:
            items.append(((p.scene_id, p.panel_id), AR.get(p.aspect.value, 1.5)))
    if not items:
        return []
    band_pages = paginate(pack_bands(items))
    pages = []
    for pi, pb in enumerate(band_pages):
        cells_abs = justify(pb, pi == len(band_pages) - 1)
        pages.append(Page(
            page_id=f"page-{pi + 1}", issue_id=issue_id, series_id=series_id,
            page_number=pi + 1,
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
            items.append(((ref.scene_id, ref.panel_id), aspect))
    bands = pack_bands(items)
    cells_abs = justify(bands, is_last=(sum(b["h"] for b in bands) < PAGE_UNITS_H))
    pm.rows = [[PanelRef(scene_id=k[0], panel_id=k[1]) for k, *_ in b["cells"]] for b in bands]
    pm.cells = [PanelCell(scene_id=k[0], panel_id=k[1], x=round(x, 3), y=round(y, 3),
                          w=round(w, 3), h=round(h, 3)) for k, x, y, w, h in cells_abs]
    return pm
