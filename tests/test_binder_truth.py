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

    n_layout_pages = len(storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN}))
    out = str(tmp_path / "book.pdf")
    page_count, missing = bind_issue_pdf(storage, WL, CARN, out)
    assert os.path.exists(out)
    # front cover + indicia + designed pages + AT LEAST one overflow page
    # carrying the rendered leftover — never fewer
    assert page_count >= n_layout_pages + 3
    assert any("on NO page" in m for m in missing)


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
