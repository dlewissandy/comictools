"""THE LAYOUT SWATCH BOOK: every exact tiling of the printed page.

The book's page is a 6-wide x 10-tall unit grid, and its panels come in
six shapes the stitcher already speaks: square 1x (2x2), landscape 1x
(3x2), portrait 1x (2x3), square 2x (4x4), landscape 2x (6x4), portrait
2x (4x6).  There are 1125 exact tilings of the page with those pieces —
354 once mirrored and rotated twins are identified (the author's
catalog: unique_6x10_tilings.pdf).

This module enumerates them once (deterministically), canonicalizes
modulo horizontal flip, vertical flip and 180° rotation, and serves them
sorted by piece count — the swatch book the layout picker leafs through.
"""
from __future__ import annotations

from functools import lru_cache

W, H = 6, 10
# (w, h) in grid units -> the panel vocabulary that produces that piece
PIECES = [(2, 2), (3, 2), (2, 3), (4, 4), (6, 4), (4, 6)]
PIECE_PANEL = {
    (2, 2): ("square", "1x"),
    (3, 2): ("landscape", "1x"),
    (2, 3): ("portrait", "1x"),
    (4, 4): ("square", "2x"),
    (6, 4): ("landscape", "2x"),
    (4, 6): ("portrait", "2x"),
}


def _enumerate_raw() -> list[tuple[tuple[int, int, int, int], ...]]:
    """Every exact cover of the grid: tilings as tuples of (x, y, w, h)
    pieces, discovered top-left-first (reading order by construction)."""
    results = []
    grid = [[False] * W for _ in range(H)]

    def first_empty():
        for y in range(H):
            for x in range(W):
                if not grid[y][x]:
                    return x, y
        return None

    placed: list[tuple[int, int, int, int]] = []

    def fits(x, y, w, h):
        if x + w > W or y + h > H:
            return False
        return all(not grid[yy][xx] for yy in range(y, y + h) for xx in range(x, x + w))

    def mark(x, y, w, h, v):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                grid[yy][xx] = v

    def solve():
        spot = first_empty()
        if spot is None:
            results.append(tuple(placed))
            return
        x, y = spot
        for w, h in PIECES:
            if fits(x, y, w, h):
                mark(x, y, w, h, True)
                placed.append((x, y, w, h))
                solve()
                placed.pop()
                mark(x, y, w, h, False)

    solve()
    return results


def _canon(tiling) -> tuple:
    """The canonical representative under {identity, h-flip, v-flip, 180}."""
    def hflip(t):
        return tuple(sorted((W - x - w, y, w, h) for x, y, w, h in t))

    def vflip(t):
        return tuple(sorted((x, H - y - h, w, h) for x, y, w, h in t))

    def rot180(t):
        return tuple(sorted((W - x - w, H - y - h, w, h) for x, y, w, h in t))

    base = tuple(sorted(tiling))
    return min(base, hflip(base), vflip(base), rot180(base))


@lru_cache(maxsize=1)
def swatch_book() -> list[dict]:
    """The 354 unique tilings, each as {"pieces": [(x, y, w, h)...] in
    reading order, "count": n} — sorted by piece count then discovery."""
    seen = {}
    for t in _enumerate_raw():
        key = _canon(t)
        if key not in seen:
            seen[key] = t          # keep the reading-order original
    book = [{"pieces": sorted(t, key=lambda p: (p[1], p[0])), "count": len(t)}
            for t in seen.values()]
    book.sort(key=lambda e: (e["count"], e["pieces"]))
    return book


def swatches_for(count: int, spread: int = 0) -> list[dict]:
    """Tilings with exactly `count` pieces (± spread when nearby layouts
    should show too)."""
    return [e for e in swatch_book() if abs(e["count"] - count) <= spread]
