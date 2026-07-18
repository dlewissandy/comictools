"""THE BOOK MUST TELL THE TRUTH: a page layout that doesn't cover the issue
can no longer silently drop panels from the bound book, and empty rows can't
crash the compositor.  (The live data that exposed this: witchlight-carnival
had pages placing only a fraction of its panels.)"""
import os

from helpers.binder import page_coverage, collect_issue, bind_issue_pdf, _compose_page

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"


def _orphan_panel(storage):
    """A panel the layout doesn't know about — the gap the truth must name."""
    from schema import Panel
    SC = "b3cc50eb-5a57-463c-ba10-927d941c9779"
    p = Panel(panel_id="test-orphan", issue_id=CARN, series_id=WL, scene_id=SC,
              panel_number=97, name="Orphan", beat="b", description="d",
              aspect="landscape", character_references=[], narration=[],
              dialogue=[], image=None, reference_images=[])
    storage.create_object(p, overwrite=True)
    return p


def test_page_coverage_reports_unplaced_panels(storage):
    _orphan_panel(storage)
    has_layout, placed, unplaced, dangling = page_coverage(storage, WL, CARN)
    assert has_layout
    assert len(placed) > 0
    # a panel on no page — coverage must SAY so
    assert any(p.panel_id == "test-orphan" for _s, p in unplaced)


def test_collect_issue_names_the_gap(storage):
    _orphan_panel(storage)
    _f, _p, _b, missing = collect_issue(storage, WL, CARN)
    assert any("on NO page" in m for m in missing)


def test_bind_appends_rendered_leftovers_instead_of_dropping(storage, tmp_path):
    from PIL import Image
    from schema import Page, Panel
    # give the issue a RENDERED panel that no page places
    SC = "b3cc50eb-5a57-463c-ba10-927d941c9779"
    p = Panel(panel_id="test-leftover", issue_id=CARN, series_id=WL, scene_id=SC,
              panel_number=98, name="Leftover", beat="b", description="d",
              aspect="landscape", character_references=[], narration=[],
              dialogue=[], image=None, reference_images=[])
    storage.create_object(p, overwrite=True)
    from storage.filepath import obj_to_imagepath
    img_dir = obj_to_imagepath(obj=p, base_path=storage.base_path)
    os.makedirs(img_dir, exist_ok=True)
    art = os.path.join(img_dir, "take.png")
    Image.new("RGB", (300, 200), (90, 40, 40)).save(art)
    p.image = art
    storage.update_object(p)

    out = str(tmp_path / "book.pdf")
    page_count, missing = bind_issue_pdf(storage, WL, CARN, out)
    assert os.path.exists(out)
    # ONE BOOK EVERYWHERE: composing now re-stitches a drifted machine
    # layout FIRST, so the leftover lands ON a page — placed, not merely
    # rescued onto an overflow sheet, and never silently dropped.  Exact-fill
    # packs denser, so assert against the FRESH interior count plus covers,
    # not the stale stored page count.
    from helpers.stitcher import stitch_pages
    interior = len(stitch_pages(storage, WL, CARN))
    assert page_count >= interior + 2
    assert not any("on NO page" in m for m in missing), \
        "the drift heals at the composition door"
    from helpers.binder import page_coverage
    _has, _placed, unplaced, _dang = page_coverage(storage, WL, CARN)
    assert not unplaced, "every rendered panel sits on a page after the bind"
    # and the bind left its papers: signature + hour beside the file
    import json as _json
    meta = _json.load(open(out + ".meta.json"))
    assert meta.get("sig") and meta.get("pages") == page_count


def test_compose_page_survives_empty_rows(storage):
    # an empty row is a layout bug, not a ZeroDivisionError
    front, panels, _b, _m = collect_issue(storage, WL, CARN)
    img = _compose_page([[], [(panels[0], "panel 1 — the tent")]])
    assert img.size[0] > 0


def test_only_the_mailbag_typesets_its_description(storage, tmp_data, monkeypatch):
    """A poster's description is a render BRIEF — production notes must never
    typeset onto a bound page.  The mailbag's description IS the page."""
    from helpers import binder
    from schema import Insert
    ins = storage.read_all_objects(Insert, {"series_id": WL, "issue_id": CARN})[0]
    ins.image = None
    ins.description = "HEADER: big carnival wordmark\n\nMasthead: issue #1 blurb"
    out = os.path.join(tmp_data, "series", WL, "issues", CARN, "exports", "gate.pdf")

    typeset = []
    real = binder._insert_text_sheet
    monkeypatch.setattr(binder, "_insert_text_sheet",
                        lambda i: typeset.append(i.kind) or real(i))

    ins.kind = "poster"
    storage.update_object(ins)
    binder.bind_issue_pdf(storage, WL, CARN, out)
    assert typeset == [], "a poster's brief never typesets onto a page"

    ins.kind = "mailbag"
    storage.update_object(ins)
    binder.bind_issue_pdf(storage, WL, CARN, out)
    assert typeset == ["mailbag"], "the mailbag's letters still print typeset"


def test_a_handed_full_page_keeps_its_shape(storage, tmp_data):
    """THE HANDED PAGE KEEPS ITS EDGES: art the author pastes onto a full
    page (an ad, a scanned mailbag) arrives in its own shape.  The sheet
    scales it WHOLE and centres it — it never crops the edges off to fill
    the trim."""
    from PIL import Image
    from helpers import binder
    from schema import Insert
    from storage.filepath import obj_to_imagepath

    ins = storage.read_all_objects(Insert, {"series_id": WL, "issue_id": CARN})[0]
    # a WIDE ad — nothing like the page's portrait trim — with edges that
    # only survive if the whole picture lands on the sheet
    img_dir = obj_to_imagepath(obj=ins, base_path=storage.base_path)
    os.makedirs(img_dir, exist_ok=True)
    art = os.path.join(img_dir, "wide-ad.png")
    ad = Image.new("RGB", (1600, 900), (30, 60, 180))
    for x in range(40):
        for y in range(900):
            ad.putpixel((x, y), (255, 0, 0))          # left edge
            ad.putpixel((1599 - x, y), (0, 255, 0))   # right edge
    ad.save(art)
    ins.image = art
    storage.update_object(ins)

    sheet, missing = binder._insert_page(ins)
    assert missing is None
    assert sheet.size == (binder.PAGE_W, binder.PAGE_H), "it still prints a full sheet"

    mid = binder.PAGE_H // 2
    assert sheet.getpixel((2, mid)) == (255, 0, 0), "the ad's left edge is still on the page"
    assert sheet.getpixel((binder.PAGE_W - 3, mid)) == (0, 255, 0), "and its right edge too"

    # the picture kept its own proportions: scaled to the page's width, the
    # 16:9 ad stands 900/1600 as tall, and paper shows above and below
    art_h = round(900 * (binder.PAGE_W / 1600))
    assert sheet.getpixel((binder.PAGE_W // 2, (binder.PAGE_H - art_h) // 4)) == binder.PAPER
    assert sheet.getpixel((binder.PAGE_W // 2, mid)) != binder.PAPER, "the art holds the middle"


def test_the_reading_room_reprints_when_the_press_changes(storage):
    """The sheets cache by signature, and the COMPOSITION MATH shapes the
    sheet as surely as the art does — so the signature must move when the
    press does, or a book composed yesterday serves yesterday's crop."""
    from helpers import binder
    before = binder.book_signature(storage, WL, CARN)
    binder.BINDER_REV += 1
    try:
        assert binder.book_signature(storage, WL, CARN) != before, \
            "a new press must invalidate the cached sheets"
    finally:
        binder.BINDER_REV -= 1


def test_the_pdf_binds_at_full_quality(storage, tmp_path):
    """The flagship deliverable is never the softest copy: pages encode at
    JPEG q95, not Pillow's silent default 75."""
    out = str(tmp_path / "quality.pdf")
    page_count, _m = bind_issue_pdf(storage, WL, CARN, out)
    assert page_count > 0
    q75 = str(tmp_path / "q75.pdf")
    from helpers.binder import compose_book
    sheets, _ = compose_book(storage, WL, CARN)
    pages = [img for _l, img in sheets]
    pages[0].save(q75, "PDF", save_all=True, append_images=pages[1:],
                  resolution=150, quality=75)
    assert os.path.getsize(out) > os.path.getsize(q75) * 1.15, \
        "q95 pages carry visibly more detail than the old default"


def test_exports_carry_the_books_name(storage):
    from helpers.binder import export_basename
    base = export_basename(storage, WL, CARN)
    assert base != CARN and "-" in base
    assert not base.startswith("1."), "never a bare issue number"


def test_the_cbz_carries_its_papers(storage, tmp_path):
    import zipfile as _zf
    from helpers.binder import bind_issue_cbz
    out = str(tmp_path / "book.cbz")
    n, _m = bind_issue_cbz(storage, WL, CARN, out)
    assert n > 0
    with _zf.ZipFile(out) as z:
        names = z.namelist()
        assert "ComicInfo.xml" in names
        info = z.read("ComicInfo.xml").decode()
        assert "<Series>" in info and f"<PageCount>{n}</PageCount>" in info
