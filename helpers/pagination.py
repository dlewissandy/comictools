"""AUTO-FLOW EXACT-FILL PAGINATION.

The beat chooses each panel's shape — `(aspect, size)` — and the layout serves
the beats, not the other way round.  Given the panels in reading order, some with
their shape LOCKED by the author, this flows them into pages where:

  * every page is one of the swatch book's exact tilings (gapless, no splash —
    tiled pages run 4..15 panels; splashes/short pages live outside, as hand
    pages or inserts),
  * a LOCKED panel keeps its exact shape at its place in reading order,
  * the UNLOCKED panels flex to whatever shapes complete the tiling, preferring
    to keep their beat-shape (the flow minimizes total flexing),
  * and where no legal flow exists, it raises `LayoutImpossible` with a reason
    that points at the culprit — instead of silently mangling shapes.

Pure and deterministic: no storage, no rendering.  The stitcher wires page
objects from the pieces this returns.
"""
from __future__ import annotations

from functools import lru_cache

from helpers.tilings import PIECE_PANEL, swatch_book

# the six shapes a tiling piece can be — a panel shape outside this set can never
# be honored by an exact tiling (e.g. a square 3x, which has no piece)
TILE_SHAPES = frozenset(PIECE_PANEL.values())

# gentle nudge toward comfortable page sizes; flexing always dominates it
_TARGET_PAGE = 6
_SIZE_NUDGE = 0.02


class LayoutImpossible(Exception):
    """No exact-fill flow honors the locks (and the 4..15 page-size law).

    `panel_index` (0-based, when known) points at the offending panel so the UI
    can say 'unlock panel N, change its shape, or move it'."""

    def __init__(self, message: str, panel_index: int | None = None):
        super().__init__(message)
        self.panel_index = panel_index


def norm_shape(aspect, size) -> tuple[str, str]:
    """A panel's `(aspect, size)` as a plain, comparable shape."""
    a = getattr(aspect, "value", aspect) or "square"
    return (a, (size or "1x"))


@lru_cache(maxsize=1)
def _tilings_by_count() -> dict[int, list[tuple[tuple, tuple]]]:
    """count -> [(pieces, piece_shapes)], pieces in reading order."""
    by: dict[int, list] = {}
    for e in swatch_book():
        pieces = tuple(e["pieces"])
        shapes = tuple(PIECE_PANEL[(w, h)] for (_x, _y, w, h) in pieces)
        by.setdefault(e["count"], []).append((pieces, shapes))
    return by


def _best_page(shapes: tuple, locks: tuple):
    """The cheapest exact tiling of these panels honoring the locked ones, or
    None.  Returns (flex_cost, pieces) — flex_cost counts unlocked panels whose
    beat-shape the tiling had to change."""
    best = None
    for pieces, piece_shapes in _tilings_by_count().get(len(shapes), ()):
        flex = 0
        ok = True
        for k in range(len(shapes)):
            same = piece_shapes[k] == shapes[k]
            if locks[k]:
                if not same:
                    ok = False
                    break
            elif not same:
                flex += 1
        if ok and (best is None or flex < best[0]):
            best = (flex, pieces)
            if flex == 0:
                break                       # can't do better than no flexing
    return best


def paginate(panels: list[dict]) -> list[dict]:
    """Flow `panels` (reading order; each {aspect, size, locked}) into exact-fill
    pages.  Returns [{'indices': [i...], 'pieces': [(x,y,w,h)...], 'flex': n}].

    Raises LayoutImpossible when no legal flow exists."""
    n = len(panels)
    shapes = [norm_shape(p.get("aspect"), p.get("size")) for p in panels]
    locks = [bool(p.get("locked")) for p in panels]

    # a locked panel whose shape no piece can be is an instant dead-end
    for k in range(n):
        if locks[k] and shapes[k] not in TILE_SHAPES:
            raise LayoutImpossible(
                f"panel {k + 1} is locked to {shapes[k][0]} {shapes[k][1]}, a shape "
                f"no exact-fill page can contain — unlock it or give it a printable "
                f"size.", k)

    counts = _tilings_by_count().keys()
    if not counts:                                    # pragma: no cover
        raise LayoutImpossible("the swatch book is empty")
    lo, hi = min(counts), max(counts)

    if n < lo:
        raise LayoutImpossible(
            f"{n} panel{'s' if n != 1 else ''} can't fill an exact page (a tiled page "
            f"needs {lo}–{hi}); hand-lay this page or add panels.")

    # DP from the back: dp[i] = (cost, j, pieces) — the cheapest flow of panels[i:]
    dp: list[tuple | None] = [None] * (n + 1)
    dp[n] = (0.0, None, None)
    for i in range(n - 1, -1, -1):
        best = None
        for j in range(i + lo, min(n, i + hi) + 1):
            if dp[j] is None:
                continue
            page = _best_page(tuple(shapes[i:j]), tuple(locks[i:j]))
            if page is None:
                continue
            flex, pieces = page
            cost = flex + _SIZE_NUDGE * abs((j - i) - _TARGET_PAGE) + dp[j][0]
            if best is None or cost < best[0]:
                best = (cost, j, pieces)
        dp[i] = best

    if dp[0] is None:
        # find how far a legal flow CAN reach, to point at the wall
        reach = [False] * (n + 1)
        reach[0] = True
        frontier = 0
        for i in range(n):
            if not reach[i]:
                continue
            for j in range(i + lo, min(n, i + hi) + 1):
                if _best_page(tuple(shapes[i:j]), tuple(locks[i:j])) is not None:
                    reach[j] = True
                    frontier = max(frontier, j)
        tail = n - frontier
        raise LayoutImpossible(
            f"these panels can't be flowed into exact-fill pages — the last "
            f"{tail} panel{'s' if tail != 1 else ''} leave a remainder no page size "
            f"(4–15) can absorb.  Unlock a panel, change a locked shape, or move a "
            f"panel to the next scene.", frontier if frontier < n else None)

    pages = []
    i = 0
    while i < n:
        _cost, j, pieces = dp[i]
        idx = list(range(i, j))
        page_shapes = [PIECE_PANEL[(w, h)] for (_x, _y, w, h) in pieces]
        flex = sum(1 for k, gi in enumerate(idx)
                   if not locks[gi] and page_shapes[k] != shapes[gi])
        pages.append({"indices": idx, "pieces": list(pieces), "flex": flex})
        i = j
    return pages
