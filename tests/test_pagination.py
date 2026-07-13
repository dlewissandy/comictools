"""AUTO-FLOW EXACT-FILL PAGINATION: the beat picks each panel's shape, locks are
honored, the rest flex to complete gapless pages, and a true dead-end errors."""
import pytest

from helpers.pagination import LayoutImpossible, paginate
from helpers.tilings import PIECE_PANEL, swatch_book


def _panels_from_swatch(sw, locked=False):
    shapes = [PIECE_PANEL[(w, h)] for (_x, _y, w, h) in sw["pieces"]]
    return [{"aspect": a, "size": s, "locked": locked} for (a, s) in shapes]


def _swatch(count):
    return next(e for e in swatch_book() if e["count"] == count)


def _area(pieces):
    return sum(w * h for (_x, _y, w, h) in pieces)


def test_beat_shapes_that_already_tile_need_no_flex():
    pages = paginate(_panels_from_swatch(_swatch(4)))
    assert len(pages) == 1
    assert pages[0]["indices"] == [0, 1, 2, 3]
    assert pages[0]["flex"] == 0
    assert _area(pages[0]["pieces"]) == 60          # exact fill, no gaps


def test_all_locked_returns_that_exact_tiling():
    sw = _swatch(5)
    pages = paginate(_panels_from_swatch(sw, locked=True))
    assert len(pages) == 1 and pages[0]["flex"] == 0
    got = [PIECE_PANEL[(w, h)] for (_x, _y, w, h) in pages[0]["pieces"]]
    want = [PIECE_PANEL[(w, h)] for (_x, _y, w, h) in sw["pieces"]]
    assert got == want                              # the locks force this tiling


def test_unlocked_panels_flex_to_complete_the_page():
    # four 'square 1x' panels can't stay 2x2 (that leaves the page unfilled),
    # so the flow grows some of them — but it still produces a gapless page
    panels = [{"aspect": "square", "size": "1x", "locked": False} for _ in range(4)]
    pages = paginate(panels)
    assert len(pages) == 1 and len(pages[0]["pieces"]) == 4
    assert pages[0]["flex"] >= 1
    assert _area(pages[0]["pieces"]) == 60


def test_lock_is_honored_while_neighbors_flex():
    # a locked landscape-2x lead forces a SHORT page (a 6x4 can only lead a
    # 4- or 5-panel tiling) — the flow honors the lock and sizes the page to it
    panels = [{"aspect": "square", "size": "1x", "locked": False} for _ in range(5)]
    panels[0] = {"aspect": "landscape", "size": "2x", "locked": True}
    pages = paginate(panels)
    first_piece = pages[0]["pieces"][0]
    assert (first_piece[2], first_piece[3]) == (6, 4)   # PIECE for landscape 2x
    assert len(pages[0]["indices"]) in (4, 5)


def test_locked_big_panel_mid_flow_keeps_its_shape():
    # a landscape-2x locked in the middle of a long run: the auto-flow sizes and
    # breaks pages so the lock is honored wherever it lands (lead OR tail of a page)
    panels = [{"aspect": "square", "size": "1x", "locked": False} for _ in range(12)]
    panels[6] = {"aspect": "landscape", "size": "2x", "locked": True}
    pages = paginate(panels)
    pg = next(p for p in pages if 6 in p["indices"])
    piece = pg["pieces"][pg["indices"].index(6)]
    assert (piece[2], piece[3]) == (6, 4)              # the lock is honored
    assert all(_area(p["pieces"]) == 60 for p in pages)
    assert [i for p in pages for i in p["indices"]] == list(range(12))


def test_flow_splits_into_contiguous_reading_order_pages():
    panels = [{"aspect": "landscape", "size": "1x", "locked": False} for _ in range(20)]
    pages = paginate(panels)
    assert sum(len(p["indices"]) for p in pages) == 20
    flat = [i for p in pages for i in p["indices"]]
    assert flat == list(range(20))                  # reading order preserved
    for p in pages:
        assert 4 <= len(p["indices"]) <= 15
        assert _area(p["pieces"]) == 60


@pytest.mark.parametrize("n", [1, 2, 3])
def test_error_when_too_few_for_an_exact_page(n):
    with pytest.raises(LayoutImpossible) as ei:
        paginate([{"aspect": "square", "size": "1x", "locked": False}] * n)
    assert "exact page" in str(ei.value)


def test_error_when_locked_to_an_unprintable_shape():
    panels = [{"aspect": "square", "size": "1x", "locked": False} for _ in range(4)]
    panels[1] = {"aspect": "square", "size": "3x", "locked": True}   # no 3x square piece
    with pytest.raises(LayoutImpossible) as ei:
        paginate(panels)
    assert ei.value.panel_index == 1
    assert "no exact-fill page can contain" in str(ei.value)
