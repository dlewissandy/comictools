"""THE TRADE DRESS: covers wear credits, issue № and price; panels can
carry attribution — bordered pieces stamped from the issue's metadata,
identical on the rough and in the print."""
from types import SimpleNamespace

from helpers.trade_dress import (COVER_PIECES, PANEL_PIECES, DRESS_DEFAULTS,
                                 collect_dress, dress_text, refresh_dress_text)


def _issue(**kw):
    base = dict(writer="Ann Author", artist="Pei Painter", colorist=None,
                creative_minds="The Table", issue_number=3, price="$4.99")
    base.update(kw)
    return SimpleNamespace(**base)


def test_dress_text_speaks_the_masthead():
    iss = _issue()
    credits = dress_text(iss, "dress/credits")
    assert "STORY · ANN AUTHOR" in credits and "ART · PEI PAINTER" in credits
    assert "COLORS" not in credits, "missing metadata never prints an empty slot"
    assert dress_text(iss, "dress/issue") == "No. 3"
    assert dress_text(iss, "dress/price") == "$4.99"
    assert dress_text(_issue(price="Free"), "dress/price") == "Free", \
        "the price is free text and prints verbatim"
    assert dress_text(_issue(price=None), "dress/price") is None
    assert dress_text(None, "dress/credits") is None


def test_price_is_free_text_and_old_numbers_dress_themselves():
    """The price field holds whatever should PRINT ('Free', '10¢') — and a
    house minted before the ruling, whose JSON holds a NUMBER, loads with
    the dollar dress it always printed."""
    from schema import Issue
    base = dict(issue_id="i", name="N", style_id="s", series_id="ser",
                story=None, issue_number=1, publication_date=None,
                writer=None, artist=None, colorist=None, creative_minds=None)
    assert Issue(**base, price="Free").price == "Free"
    assert Issue(**base, price=3.99).price == "$3.99"
    assert Issue(**base, price=None).price is None


def test_collect_dress_reads_snapshots_only():
    blk = {"dress/credits": {"on": 1, "text": "STORY · X", "x": 10, "y": 5},
           "dress/issue": {"on": 0, "text": "No. 3"},
           "dress/price": {"on": 1, "text": ""}}
    out = collect_dress(blk)
    assert len(out) == 1, "off and empty pieces never print"
    assert out[0]["kind"] == "credit" and out[0]["x"] == 10
    assert collect_dress(None) == []


def test_refresh_keeps_snapshots_honest():
    saved = []
    storage = SimpleNamespace(update_object=lambda b: saved.append(b))
    board = SimpleNamespace(figure_blocking={
        "dress/issue": {"on": 1, "text": "No. 2", **DRESS_DEFAULTS["dress/issue"]}})
    assert refresh_dress_text(storage, board, _issue(issue_number=3))
    assert board.figure_blocking["dress/issue"]["text"] == "No. 3"
    assert saved, "the refresh persists"
    # already honest → no write
    saved.clear()
    assert not refresh_dress_text(storage, board, _issue(issue_number=3))
    assert not saved


def test_the_print_wears_the_dress():
    """collect_letters carries the dress on any board, and paste_letters
    stamps visibly distinct pieces (band + shadow, heavy badge)."""
    from helpers.compositor import collect_letters, paste_letters, base_canvas
    board = SimpleNamespace(figure_blocking={
        "dress/credits": {"on": 1, "text": "STORY · ANN   ART · PEI",
                          **DRESS_DEFAULTS["dress/credits"]},
        "dress/price": {"on": 1, "text": "$4.99", **DRESS_DEFAULTS["dress/price"]}},
        kind="poster", description=None)
    letters = collect_letters(board)
    kinds = sorted(L["kind"] for L in letters)
    assert kinds == ["badge", "credit"]

    base = base_canvas("portrait", None)
    before = base.copy()
    paste_letters(base, "portrait", letters)
    assert list(base.getdata()) != list(before.getdata()), "the dress inked"


def test_cover_and_panel_wear_different_dress():
    assert set(COVER_PIECES) == {"dress/credits", "dress/issue", "dress/price"}
    assert set(PANEL_PIECES) == {"dress/credits"}, "a panel carries attribution only"
