"""THE PAGE STITCHER: the studio's banding on the printed page's 6x10 unit
grid — every panel placed exactly once, in reading order, full pages."""
from helpers.stitcher import (
    AR, PAGE_UNITS_H, PAGE_UNITS_W, apply_stitch, pack_bands, paginate,
    justify, repack_page, stitch_pages,
)

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
L, P, S = AR["landscape"], AR["portrait"], AR["square"]


def test_tall_band_portrait_beside_stacked_landscapes():
    bands = pack_bands([("p", P), ("l1", L), ("l2", L)])
    assert len(bands) == 1
    band = bands[0]
    assert band["h"] == 4.0
    keys = {c[0]: c for c in band["cells"]}
    # portrait leads at the left, full band height
    assert keys["p"][1] == 0 and keys["p"][4] == 4.0
    # the two landscapes stack beside it
    assert keys["l1"][2] == 0.0 and keys["l2"][2] == 2.0
    assert keys["l1"][1] == keys["l2"][1] > 2.0


def test_pairs_and_splash():
    bands = pack_bands([("a", L), ("b", L), ("c", L)])
    assert [len(b["cells"]) for b in bands] == [2, 1]
    # the pair closes the page width exactly
    pair = bands[0]["cells"]
    assert abs(sum(c[3] for c in pair) - PAGE_UNITS_W) < 1e-6
    # the lone survivor prints as a full-width splash
    assert bands[1]["cells"][0][3] == 6.0


def test_portrait_pair_and_lone_portrait():
    two = pack_bands([("p1", P), ("p2", P)])
    assert len(two) == 1 and two[0]["h"] == 4.5
    one = pack_bands([("p1", P)])
    (cell,) = one[0]["cells"]
    assert cell[1] == 1.5   # inset, breathing room around it


def test_pagination_and_justify_fill_the_page():
    # 6 landscape pairs = 6 bands of h in [2,3] — more than one page
    items = [(f"x{i}", L) for i in range(12)]
    pages = paginate(pack_bands(items))
    assert len(pages) >= 2
    cells = justify(pages[0], is_last=False)
    bottom = max(y + h for _k, _x, y, _w, h in cells)
    assert abs(bottom - PAGE_UNITS_H) < 0.05, "a non-final page prints full"
    for _k, x, y, w, h in cells:
        assert -1e-6 <= x and x + w <= PAGE_UNITS_W + 1e-6
        assert -1e-6 <= y and y + h <= PAGE_UNITS_H + 1e-6


def test_stitch_places_every_panel_exactly_once(storage):
    pages = stitch_pages(storage, WL, CARN)
    assert pages, "the carnival issue stitches"
    placed = [c.panel_id for pm in pages for c in pm.cells]
    from helpers.binder import _reading_order
    expected = [p.panel_id for _s, panels in _reading_order(storage, WL, CARN) for p in panels]
    assert placed == expected, "every panel, reading order, exactly once"
    for pm in pages:
        # rows mirror the band grouping — same refs, same order
        assert [r.panel_id for row in pm.rows for r in row] == [c.panel_id for c in pm.cells]


def test_apply_stitch_replaces_and_snapshots(storage):
    from schema import Page
    old = storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN})
    assert old, "fixture has a layout to replace"
    new_pages, old_pages = apply_stitch(storage, WL, CARN)
    assert len(old_pages) == len(old)
    now = storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN})
    assert len(now) == len(new_pages)
    assert all(p.cells for p in now), "stitched pages carry cells"
    # the coverage truth: nothing unplaced, nothing dangling
    from helpers.binder import page_coverage
    _has, _placed, unplaced, dangling = page_coverage(storage, WL, CARN)
    assert not unplaced and not dangling


def test_repack_after_removing_a_panel(storage):
    pages = stitch_pages(storage, WL, CARN)
    pm = next(p for p in pages if sum(len(r) for r in p.rows) >= 2)
    gone = pm.rows[0][0].panel_id
    pm.rows = [[r for r in row if r.panel_id != gone] for row in pm.rows]
    pm.rows = [row for row in pm.rows if row]
    repack_page(storage, pm)
    assert gone not in [c.panel_id for c in pm.cells]
    assert [r.panel_id for row in pm.rows for r in row] == [c.panel_id for c in pm.cells]


def test_compose_page_cells(storage, tmp_path):
    from PIL import Image
    from helpers.binder import _compose_page_cells, PAGE_W, PAGE_H
    art = str(tmp_path / "take.png")
    Image.new("RGB", (300, 200), (200, 30, 30)).save(art)
    img = _compose_page_cells([(art, 0, 0, 3, 2), (None, 3, 0, 3, 2), (art, 0, 2, 6, 4)])
    assert img.size == (PAGE_W, PAGE_H)
    # art landed in the first cell (red), placeholder gray in the second
    assert img.getpixel((260, 150))[0] > 150
    px = img.getpixel((740, 150))
    assert abs(px[0] - px[1]) < 12 and px[0] > 200, "placeholder is light gray"


def test_sizes_speak():
    # a splash takes the whole page
    bands = pack_bands([("s", L, "splash"), ("a", L), ("b", L)])
    assert bands[0]["h"] == 10.0 and bands[0]["cells"][0][3:] == (6.0, 10.0)
    # a large landscape refuses to pair
    bands = pack_bands([("big", L, "large"), ("a", L), ("b", L)])
    assert len(bands[0]["cells"]) == 1 and bands[0]["cells"][0][3] == 6.0
    # a large portrait commands the band with two beats stacked beside it
    bands = pack_bands([("p", P, "large"), ("a", L), ("b", S)])
    assert len(bands) == 1 and bands[0]["h"] == 6.0
    # three smalls share one compact tier
    bands = pack_bands([("a", L, "small"), ("b", L, "small"), ("c", L, "small")])
    assert len(bands) == 1 and len(bands[0]["cells"]) == 3
    assert bands[0]["h"] <= 2.0
