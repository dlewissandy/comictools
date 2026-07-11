"""Binding an issue into a PDF book."""
import os

from helpers.binder import bind_issue_pdf, collect_issue

WL = "wonders-of-the-witchlight"
CARN = "witchlight-carnival"


def test_collect_reports_missing_renders(storage):
    front, panels, back, missing = collect_issue(storage, WL, CARN)
    assert front and os.path.exists(front)
    assert panels, "the tent panel render should be collected"
    assert any("not rendered" in m for m in missing), "unrendered panels must be reported"


def test_bind_writes_pdf(storage, tmp_data):
    out = os.path.join(tmp_data, "series", WL, "issues", CARN, "exports", "test.pdf")
    pages, missing = bind_issue_pdf(storage, WL, CARN, out)
    assert pages >= 2, "cover + at least one interior page"
    assert os.path.getsize(out) > 10_000
