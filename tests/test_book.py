"""BOUND = BOOK: the PDF, the CBZ, and THE READING ROOM all come from the
same compose_book() sheets — covers in order, an indicia page, folios."""
import os
import zipfile

from helpers.binder import compose_book, bind_issue_cbz, reader_sheets, book_signature, PAGE_W, PAGE_H

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"


def test_compose_book_order_and_trim(storage):
    sheets, _missing = compose_book(storage, WL, CARN)
    labels = [l for l, _img in sheets]
    # front cover first, indicia (no inside-front art in this data) second,
    # then the interior pages in order
    assert labels[0] == "front cover"
    assert labels[1] == "indicia"
    assert labels[2] == "page 1"
    # every sheet is cut to the same trim — a real book
    assert all(img.size == (PAGE_W, PAGE_H) for _l, img in sheets)


def test_cbz_holds_every_sheet(storage, tmp_path):
    out = str(tmp_path / "book.cbz")
    page_count, _missing = bind_issue_cbz(storage, WL, CARN, out)
    with zipfile.ZipFile(out) as z:
        names = sorted(z.namelist())
    assert len(names) == page_count
    assert names[0].startswith("000-front-cover")
    # zip order IS reading order for comic reader apps
    assert names == sorted(names)


def test_reader_sheets_cache_and_invalidation(storage):
    sheets, _m = reader_sheets(storage, WL, CARN)
    assert sheets and all(os.path.exists(p) for _l, p in sheets)
    sig1 = book_signature(storage, WL, CARN)
    # a second visit reuses the cached sheets (same files, same signature)
    again, _m2 = reader_sheets(storage, WL, CARN)
    assert [p for _l, p in again] == [p for _l, p in sheets]
    assert book_signature(storage, WL, CARN) == sig1
    # touching the issue's credits changes the book (the indicia page)
    from schema import Issue
    issue = storage.read_object(cls=Issue, primary_key={"series_id": WL, "issue_id": CARN})
    issue.writer = "A Different Hand"
    storage.update_object(data=issue)
    assert book_signature(storage, WL, CARN) != sig1


def test_remember_stitch_persists_and_is_idempotent(storage):
    from helpers.stitcher import remember_stitch
    from schema import Page
    remember_stitch(storage, WL, CARN)
    pages1 = storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN},
                                      order_by="page_number")
    assert pages1 and all(p.cells for p in pages1)
    # calling again changes nothing (same signature -> no writes)
    remember_stitch(storage, WL, CARN)
    pages2 = storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN},
                                      order_by="page_number")
    assert [p.model_dump() for p in pages1] == [p.model_dump() for p in pages2]


def test_insert_prints_in_the_book(storage, tmp_path):
    from schema import Insert, Page
    from helpers.binder import _reading_order
    # anchor the insert after the scene that owns the FIRST printed page's
    # panels — wherever the author's reordering has numbered it today
    pages = storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN},
                                     order_by="page_number")
    first_scene_id = pages[0].rows[0][0].scene_id
    scene_no = {sc.scene_id: sc.scene_number for sc, _p in _reading_order(storage, WL, CARN)}
    ins = Insert(insert_id="test-poster", issue_id=CARN, series_id=WL,
                 kind="poster", name="Carnival poster", description="a poster",
                 after_scene_number=scene_no[first_scene_id], image=None)
    storage.create_object(ins, overwrite=True)
    sheets, missing = compose_book(storage, WL, CARN)
    labels = [l for l, _ in sheets]
    assert any(l.startswith("insert — Carnival poster") for l in labels)
    # unrendered inserts are named as gaps, never silently dropped
    assert any("insert 'Carnival poster' is not rendered" in m for m in missing)
    # it lands after the page carrying that scene's panels
    idx = labels.index("insert — Carnival poster")
    assert labels[idx - 1].startswith("page"), f"got order: {labels}"


def test_undo_survives_remember_stitch(storage):
    """The critical chain: delete a panel, let the book quietly re-remember
    its layout, then 'undo my last delete' — the panel MUST come back.
    remember_stitch writes pages in place (no trash churn) and the trash
    walks past superseded entries."""
    from schema import Page, Panel
    from helpers.binder import _reading_order
    from helpers.stitcher import remember_stitch
    from storage.trash import restore_last

    remember_stitch(storage, WL, CARN)
    scene, panels = next((s, p) for s, p in _reading_order(storage, WL, CARN) if p)
    victim = panels[0]
    storage.delete_object(cls=Panel, primary_key=victim.primary_key)
    # strip refs the way delete_panel does, then the view syncs the layout
    for pm in storage.read_all_objects(Page, {"series_id": WL, "issue_id": CARN}):
        pm.rows = [[r for r in row if r.panel_id != victim.panel_id] for row in pm.rows]
        pm.rows = [row for row in pm.rows if row]
        storage.update_object(pm)
    remember_stitch(storage, WL, CARN)

    restored = restore_last(storage.base_path)
    assert restored, "undo found nothing to restore — the delete was buried"
    back = storage.read_object(cls=Panel, primary_key=victim.primary_key)
    assert back is not None and back.panel_id == victim.panel_id
