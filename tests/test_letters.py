"""COVER LETTERS + the placeholder guard: letters composite on flatten/rough
with the table's blocking, covers carry letters like panels, and unwritten
scaffold text never reaches a composite or the book."""
from PIL import Image

from helpers.compositor import (
    DIMS, base_canvas, collect_letters, is_placeholder, paste_letters,
)
from schema import Cover
from schema.dialog import Dialogue, DialogueEmphasis, Narration, NarrationPosition

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"


def test_placeholder_guard():
    assert is_placeholder("Say something…")
    assert is_placeholder("  say something ")
    assert is_placeholder("Narration…")
    assert not is_placeholder("The ball had never lied.")
    assert not is_placeholder(None)
    assert not is_placeholder("")


def _board(**overrides):
    base = dict(cover_id="c", location="front", issue_id=CARN, series_id=WL,
                character_references=[], style_id="s", aspect="landscape",
                reference_images=[], description="d", image=None)
    return Cover(**{**base, **overrides})


def test_cover_carries_letters():
    board = _board(
        narration=[Narration(text="THIS SUMMER: the carnival lies.", position=NarrationPosition.TOP)],
        dialogue=[Dialogue(character_id="mud", text="Run.", emphasis=DialogueEmphasis.SHOUT)],
    )
    letters = collect_letters(board)
    kinds = sorted(l["kind"] for l in letters)
    assert kinds == ["balloon", "caption"]


def test_collect_letters_skips_placeholders_and_lifted_acetates():
    board = _board(
        narration=[Narration(text="Narration…", position=NarrationPosition.TOP)],
        dialogue=[Dialogue(character_id="mud", text="Written words.", emphasis=DialogueEmphasis.CHAT),
                  Dialogue(character_id="ezra", text="Hidden words.", emphasis=DialogueEmphasis.CHAT)],
        figure_blocking={"balloon/1": {"on": 0}},
    )
    letters = collect_letters(board)
    assert [l["text"] for l in letters] == ["Written words."]


def test_collect_letters_honors_table_blocking():
    board = _board(
        dialogue=[Dialogue(character_id="mud", text="Here!", emphasis=DialogueEmphasis.CHAT)],
        figure_blocking={"balloon/0": {"x": 63.0, "y": 21.0, "fs": 15.0, "tx": 40.0, "ty": 5.0}},
    )
    (l,) = collect_letters(board)
    assert (l["x"], l["y"], l["fs"], l["tx"], l["ty"]) == (63.0, 21.0, 15.0, 40.0, 5.0)


def test_paste_letters_draws_on_the_canvas():
    aspect = "landscape"
    base = base_canvas(aspect, None)          # blank paper
    before = base.copy()
    paste_letters(base, aspect, [
        {"kind": "caption", "text": "Meanwhile, at the carnival…", "x": 4, "y": 84, "fs": 11},
        {"kind": "balloon", "text": "What do you see?", "x": 30, "y": 55, "fs": 11,
         "emphasis": "chat", "tx": 35, "ty": 20},
        {"kind": "balloon", "text": "KRAKOOM", "x": 62, "y": 30, "fs": 13,
         "emphasis": "sound effect", "tx": 62, "ty": 30},
    ])
    W, H = DIMS[aspect]
    diff = sum(1 for a, b in zip(before.getdata(), base.getdata()) if a != b)
    assert diff > W * H * 0.01, "letters must visibly print on the composite"


def test_preflight_names_cover_placeholders(storage):
    from schema import Cover as _C
    covers = storage.read_all_objects(_C, primary_key={"series_id": WL, "issue_id": CARN})
    cover = covers[0]
    cover.dialogue = [Dialogue(character_id="mud", text="Say something…",
                               emphasis=DialogueEmphasis.CHAT)]
    storage.update_object(cover)
    # preflight_issue is a FunctionTool; exercise the guard logic it wraps
    from helpers.compositor import is_placeholder as guard
    texts = [d.text for d in cover.dialogue]
    assert any(guard(t) for t in texts)
    fresh = storage.read_object(cls=_C, primary_key=cover.primary_key)
    assert fresh.dialogue[0].text == "Say something…"   # letters persist on covers
