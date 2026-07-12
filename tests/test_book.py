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
