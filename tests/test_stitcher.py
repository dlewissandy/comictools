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


def test_sizes_are_multipliers():
    # a 2x landscape refuses to pair — a splash band
    bands = pack_bands([("big", L, "2x"), ("a", L), ("b", L)])
    assert len(bands[0]["cells"]) == 1 and bands[0]["cells"][0][3:] == (6.0, 4.0)
    # a 2x portrait commands the band with two beats stacked beside it
    bands = pack_bands([("p", P, "2x"), ("a", L), ("b", S)])
    assert len(bands) == 1 and bands[0]["h"] == 6.0
    # a 3x square is the big inset moment
    bands = pack_bands([("sq", S, "3x")])
    assert bands[0]["cells"][0][3:] == (5.0, 5.0)
    # aspect clamps the multiplier: no 3x landscape exists
    bands = pack_bands([("l3", L, "3x")])
    assert bands[0]["cells"][0][3:] == (6.0, 4.0)
    # legacy names still read (large -> 2x)
    bands = pack_bands([("old", L, "large"), ("a", L)])
    assert bands[0]["cells"][0][3] == 6.0


def test_boxes_keep_true_aspect():
    # every box the packer produces matches its panel's aspect — the
    # anti-clipping guarantee (except the deliberate wide-splash crop)
    items = [("a", L), ("b", S), ("c", P), ("d", P), ("e", S), ("f", S), ("g", S)]
    for band in pack_bands(items):
        for key, _x, _y, w, h in band["cells"]:
            a = dict(items)[key]
            assert abs(w / h - a) < 0.05, f"{key} box {w}x{h} breaks aspect {a}"


def test_justify_breathes_without_stretching():
    items = [(f"x{i}", L) for i in range(10)]
    pages = paginate(pack_bands(items))
    cells = justify(pages[0], is_last=False)
    for _k, x, y, w, h in cells:
        assert abs(w / h - L) < 0.05, "justify must never stretch a panel"
        assert -1e-6 <= x and x + w <= PAGE_UNITS_W + 1e-6
        assert -1e-6 <= y and y + h <= PAGE_UNITS_H + 1e-6


def test_pinned_page_holds_its_exact_shape(storage):
    """THE PINNED PAGE: a picked swatch layout is written verbatim, survives
    a re-stitch untouched, and releases back into the flow on unpin."""
    from helpers.stitcher import (pin_page_layout, unpin_page, remember_stitch,
                                  alive_pins, stitch_pages)
    from helpers.tilings import swatches_for
    from schema import Page, Panel, SceneModel

    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    remember_stitch(storage, WL, CARN)
    pages = storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN},
                                     order_by="page_number")
    page = next(p for p in pages if len(p.cells) >= 4)
    n = len(page.cells)
    swatches = swatches_for(n)
    assert swatches, f"no exact fill for {n} panels — pick another fixture page"
    tiling = swatches[0]["pieces"]

    ordered = sorted(page.cells, key=lambda c: (c.y, c.x))
    panels = [storage.read_object(Panel, {"series_id": WL, "issue_id": CARN,
                                          "scene_id": c.scene_id, "panel_id": c.panel_id})
              for c in ordered]
    pin_page_layout(storage, WL, CARN, panels, tiling)

    pins = alive_pins(storage, WL, CARN)
    assert len(pins) == 1
    got = sorted(((c.x, c.y, c.w, c.h) for c in pins[0].cells))
    want = sorted((float(x), float(y), float(w), float(h)) for x, y, w, h in tiling)
    assert got == want, "the swatch's pieces are the page's cells, verbatim"

    # a re-stitch flows AROUND the pin, never through it
    remember_stitch(storage, WL, CARN)
    pins2 = alive_pins(storage, WL, CARN)
    assert len(pins2) == 1
    assert sorted(((c.x, c.y, c.w, c.h) for c in pins2[0].cells)) == want
    # every panel appears exactly once across the whole book
    fresh = stitch_pages(storage, WL, CARN)
    seen = [c.panel_id for p in fresh for c in p.cells]
    assert len(seen) == len(set(seen)), "no panel is stitched twice around a pin"

    # release: the pin dissolves and the page rejoins the flow
    unpin_page(storage, pins2[0])
    assert alive_pins(storage, WL, CARN) == []


def test_striking_a_pinned_panel_dissolves_the_pin(storage):
    """A pin whose panel was struck has lost its exact fill — it dissolves
    instead of printing a hole."""
    from helpers.stitcher import pin_page_layout, remember_stitch, alive_pins
    from helpers.tilings import swatches_for
    from schema import Page, Panel

    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    remember_stitch(storage, WL, CARN)
    pages = storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN},
                                     order_by="page_number")
    page = next(p for p in pages if len(p.cells) >= 4)
    ordered = sorted(page.cells, key=lambda c: (c.y, c.x))
    panels = [storage.read_object(Panel, {"series_id": WL, "issue_id": CARN,
                                          "scene_id": c.scene_id, "panel_id": c.panel_id})
              for c in ordered]
    tiling = swatches_for(len(panels))[0]["pieces"]
    pin_page_layout(storage, WL, CARN, panels, tiling)
    assert len(alive_pins(storage, WL, CARN)) == 1

    victim = panels[0]
    storage.delete_object(Panel, {"series_id": WL, "issue_id": CARN,
                                  "scene_id": victim.scene_id, "panel_id": victim.panel_id})
    assert alive_pins(storage, WL, CARN) == [], "a broken fill holds no pin"
    remember_stitch(storage, WL, CARN)
    for p in storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN}):
        assert not getattr(p, 'pinned', False)
