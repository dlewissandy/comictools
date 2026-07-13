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

from helpers.tilings import PIECE_PANEL, all_tilings

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
    """count -> [(pieces, piece_shapes)], pieces in reading order.  Uses ALL
    tilings (mirror/rotation twins included) so the flow has every arrangement
    to choose from — a mirror is free visual variety."""
    by: dict[int, list] = {}
    for e in all_tilings():
        pieces = tuple(tuple(p) for p in e["pieces"])
        shapes = tuple(PIECE_PANEL[(w, h)] for (_x, _y, w, h) in pieces)
        by.setdefault(e["count"], []).append((pieces, shapes))
    return by


# ---------------------------------------------------------------------------
# THE FEEL KNOBS: four aesthetic dials that steer WHICH exact tiling the flow
# picks, and how many panels ride a page.  Each is a float in [-1, 1]; 0 is
# neutral (today's behavior).  They move only UNLOCKED panels — a locked panel
# is always honored — and flex (keeping beat-shapes) still anchors the choice.
# ---------------------------------------------------------------------------
FEEL_KEYS = ("density", "verticality", "irregularity", "variety")
_NEUTRAL_FEEL = {k: 0.0 for k in FEEL_KEYS}

# weights are calibrated so a maxed knob can OVERCOME flex (change unlocked
# panels' beat-shapes), while a mid setting is a gentle nudge — see
# tests/test_layout_feel.py
_W_VERT = 0.7       # verticality reward per portrait-over-landscape piece
_W_IRREG = 3.0      # irregularity reward per unit of size-variance (coeff. of variation)
_W_VARIETY = 8.0    # penalty for a page that repeats the previous page's shape multiset
                    # (high, because breaking a repeat of uniform panels means
                    # accepting some flex — that is what the knob asks for)
_W_DENSITY = 1.2    # how hard the density knob pulls the page toward its target size


def _feel_of(panel: dict) -> dict:
    f = panel.get("feel") or {}
    return {k: max(-1.0, min(1.0, float(f.get(k, 0.0)))) for k in FEEL_KEYS}


def _agg_feel(slice_: list) -> dict:
    """The feel a PAGE flows to: the average of its panels' feels (a page that
    straddles two scenes gets the blend)."""
    if not slice_:
        return dict(_NEUTRAL_FEEL)
    acc = {k: 0.0 for k in FEEL_KEYS}
    for p in slice_:
        f = _feel_of(p)
        for k in FEEL_KEYS:
            acc[k] += f[k]
    return {k: acc[k] / len(slice_) for k in FEEL_KEYS}


def _verticality(piece_shapes: tuple) -> int:
    """Portrait pieces minus landscape pieces in a tiling (squares neutral).  A
    per-piece count, not a share, so the knob scales against flex."""
    port = sum(1 for a, _s in piece_shapes if a == "portrait")
    land = sum(1 for a, _s in piece_shapes if a == "landscape")
    return port - land


def _irregularity(pieces: tuple) -> float:
    """A tiling's size variance as a coefficient of variation: 0 for a uniform
    grid, higher when a page mixes a big panel with small ones."""
    areas = [w * h for (_x, _y, w, h) in pieces]
    m = sum(areas) / len(areas) if areas else 0.0
    if m <= 0:
        return 0.0
    var = sum((a - m) ** 2 for a in areas) / len(areas)
    return (var ** 0.5) / m


def _sig(pieces: tuple) -> tuple:
    """A page's 'look' fingerprint — its actual tiling GEOMETRY, so a layout and
    its mirror/rotation count as DIFFERENT looks.  That lets variety pick a
    twin to differ from the previous page at zero flex (same shapes, rearranged)."""
    return tuple(sorted(tuple(p) for p in pieces))


def _best_page(shapes: tuple, locks: tuple, feel: dict | None = None,
               avoid_sig: tuple | None = None):
    """The best exact tiling of these panels honoring the locked ones, or None.
    Returns (score, flex, pieces).  `score` = flex (unlocked panels whose beat-
    shape changed) MINUS the aesthetic reward the feel knobs grant this tiling,
    PLUS a variety penalty when the tiling repeats `avoid_sig`."""
    feel = feel or _NEUTRAL_FEEL
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
        if not ok:
            continue
        # the knobs: verticality and irregularity REWARD (negative cost); a knob
        # turned negative flips the reward into a penalty (wide / grid)
        score = (flex
                 - feel["verticality"] * _verticality(piece_shapes) * _W_VERT
                 - feel["irregularity"] * _irregularity(pieces) * _W_IRREG)
        if avoid_sig is not None and feel["variety"] > 0 and _sig(pieces) == avoid_sig:
            score += feel["variety"] * _W_VARIETY
        if best is None or score < best[0]:
            best = (score, flex, pieces)
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

    # DP from the back: dp[i] = (cost, j) — the cheapest flow of panels[i:].  The
    # per-page cost is the tiling score (flex minus verticality/irregularity
    # reward) plus a DENSITY term pulling the page toward its target size.
    dp: list[tuple | None] = [None] * (n + 1)
    dp[n] = (0.0, None)
    for i in range(n - 1, -1, -1):
        best = None
        for j in range(i + lo, min(n, i + hi) + 1):
            if dp[j] is None:
                continue
            feel = _agg_feel(panels[i:j])
            page = _best_page(tuple(shapes[i:j]), tuple(locks[i:j]), feel)
            if page is None:
                continue
            score = page[0]
            target = min(hi, max(lo, _TARGET_PAGE + feel["density"] * 5))
            dens_w = _SIZE_NUDGE + abs(feel["density"]) * _W_DENSITY
            cost = score + dens_w * abs((j - i) - target) + dp[j][0]
            if best is None or cost < best[0]:
                best = (cost, j)
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

    # the DP fixed the page BREAKS; now walk them FORWARD to choose each page's
    # tiling — so the VARIETY knob can steer a page away from repeating the one
    # before it (order isn't known until the breaks are)
    spans = []
    i = 0
    while i < n:
        _cost, j = dp[i]
        spans.append((i, j))
        i = j

    pages = []
    prev_sig = None
    for (i, j) in spans:
        feel = _agg_feel(panels[i:j])
        _score, _flex0, pieces = _best_page(tuple(shapes[i:j]), tuple(locks[i:j]),
                                            feel, avoid_sig=prev_sig)
        page_shapes = [PIECE_PANEL[(w, h)] for (_x, _y, w, h) in pieces]
        flex = sum(1 for k, gi in enumerate(range(i, j))
                   if not locks[gi] and page_shapes[k] != shapes[gi])
        pages.append({"indices": list(range(i, j)), "pieces": list(pieces), "flex": flex})
        prev_sig = _sig(pieces)
    return pages
