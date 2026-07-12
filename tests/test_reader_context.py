"""The reader tools must resolve primary keys against the DEEPEST selection.

Regression test: read_one/read_all compared keys against context[0] (the
shallowest selection), so reading the currently-selected object always failed
with "It is not in the context of the current selection".
"""
from types import SimpleNamespace

import pytest

from agentic.tools import reader
from gui.selection import SelectionItem, SelectedKind
from schema import Issue, Series


def ctx(storage, selection):
    return SimpleNamespace(context=SimpleNamespace(storage=storage, selection=selection))


def sel(*items):
    return [SelectionItem(name=n, id=i, kind=k) for (n, i, k) in items]


ISSUE_SEL = (("Series", None, SelectedKind.ALL_SERIES),
             ("WL", "wonders-of-the-witchlight", SelectedKind.SERIES),
             ("Witchlight Carnival", "witchlight-carnival", SelectedKind.ISSUE))


def test_read_one_currently_selected_issue(storage):
    issue = reader.read_one(ctx(storage, sel(*ISSUE_SEL)), Issue,
                            {"series_id": "wonders-of-the-witchlight", "issue_id": "witchlight-carnival"})
    assert isinstance(issue, Issue)


def test_read_one_child_of_selected_series(storage):
    issue = reader.read_one(ctx(storage, sel(*ISSUE_SEL[:2])), Issue,
                            {"series_id": "wonders-of-the-witchlight", "issue_id": "witchlight-carnival"})
    assert isinstance(issue, Issue)


def test_read_one_top_level_with_empty_context(storage):
    series = reader.read_one(ctx(storage, sel(ISSUE_SEL[0])), Series, {"series_id": "wonders-of-the-witchlight"})
    assert isinstance(series, Series)


def test_read_one_out_of_context_raises(storage):
    other_sel = sel(("Series", None, SelectedKind.ALL_SERIES),
                    ("Rugor", "3e3fdb21-8f39-42ff-add7-6fbdda798a21", SelectedKind.SERIES))
    with pytest.raises(ValueError):
        reader.read_one(ctx(storage, other_sel), Issue,
                        {"series_id": "wonders-of-the-witchlight", "issue_id": "witchlight-carnival"})


def test_read_all_children_of_selection(storage):
    issues = reader.read_all(ctx(storage, sel(*ISSUE_SEL[:2])), Issue, {"series_id": "wonders-of-the-witchlight"})
    assert len(issues) >= 1
