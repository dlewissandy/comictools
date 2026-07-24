"""THE HEAL NEVER EATS THE ORIGINAL: pasting a take down from the choices
sheet lays NEW art beside the original and re-points whatever featured it.
The author's file is never overwritten, never deleted — it keeps its place
in the takes list (the one standing rule: nothing the author made is
destroyed unless they ask)."""
import json
import os
from types import SimpleNamespace

from PIL import Image

from schema import Cover
from gui.selection import SelectionItem, SelectedKind

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
FRONT_PK = {"series_id": WL, "issue_id": CARN, "cover_id": "front"}


def _bench_state(storage, original, choices, trail):
    st = SimpleNamespace()
    st.storage = storage
    st.selection = trail
    st.image_editor_original_image = original
    st.image_editor_image = original
    st.image_editor_choices = list(choices)
    st.image_editor_choice_selected = choices[0]
    st.image_editor_session_id = "s1"
    st.is_dirty = False

    def change_selection(new):
        st.selection = new
    st.change_selection = change_selection
    st.refresh_details = lambda: None
    return st


def _trail(original):
    return [
        SelectionItem(name="WL", id=WL, kind=SelectedKind.SERIES),
        SelectionItem(name="Carnival", id=CARN, kind=SelectedKind.ISSUE),
        SelectionItem(name="Front", id="front", kind=SelectedKind.COVER),
        SelectionItem(name="Edit this take", id=original,
                      kind=SelectedKind.IMAGE_EDITOR),
        SelectionItem(name="Choices", id=f"s1|{original}",
                      kind=SelectedKind.IMAGE_EDITOR_CHOICES),
    ]


def _choices_beside(original, n=2):
    folder = os.path.dirname(original)
    out = []
    for i in range(n):
        p = os.path.join(folder, f"choice-s1-{i:02d}.png")
        Image.new("RGB", (64, 96), (200, 30 + i, 40)).save(p)
        out.append(p)
    return out


def test_apply_lays_new_art_and_swaps_the_feature(storage):
    """A FEATURED cover take: the heal becomes a new file, the cover
    features it, and the original file survives byte-for-byte."""
    from gui.image_editor_choices import _apply
    front = storage.read_object(cls=Cover, primary_key=FRONT_PK)
    original = front.image
    before = open(original, "rb").read()
    choices = _choices_beside(original)
    chosen_bytes = open(choices[0], "rb").read()

    st = _bench_state(storage, original, choices, _trail(original))
    _apply(st)

    # the original file is untouched — same path, same bytes
    assert os.path.exists(original)
    assert open(original, "rb").read() == before

    # the healed art is a NEW file beside it, and the cover features it
    fresh = storage.read_object(cls=Cover, primary_key=FRONT_PK)
    assert fresh.image != original
    assert os.path.dirname(fresh.image) == os.path.dirname(original)
    assert open(fresh.image, "rb").read() == chosen_bytes

    # the bench selection follows the healed art
    bench = [s for s in st.selection if s.kind == SelectedKind.IMAGE_EDITOR][-1]
    assert bench.id == fresh.image
    assert not any(s.kind == SelectedKind.IMAGE_EDITOR_CHOICES for s in st.selection)

    # the raw choice files leave the wall (they wait in the wastebasket,
    # they do not burn) and the manifest is gone
    assert not any(os.path.exists(c) for c in choices)
    assert not os.path.exists(os.path.join(os.path.dirname(original),
                                           ".choices-s1.json"))
    trash = os.path.join(str(storage.base_path), ".trash")
    assert os.path.isdir(trash) and os.listdir(trash), \
        "unpicked takes wait in the wastebasket"


def test_apply_on_an_unfeatured_take_just_adds_a_take(storage):
    """Healing a take that is NOT the print: the featured image stands,
    the healed art simply joins the wall beside the original."""
    from gui.image_editor_choices import _apply
    front = storage.read_object(cls=Cover, primary_key=FRONT_PK)
    featured = front.image
    folder = os.path.dirname(featured)
    original = os.path.join(folder, "an-older-take.png")
    Image.new("RGB", (64, 96), (10, 90, 10)).save(original)
    before = open(original, "rb").read()
    choices = _choices_beside(original)

    st = _bench_state(storage, original, choices, _trail(original))
    _apply(st)

    assert open(original, "rb").read() == before, "the original take stands"
    fresh = storage.read_object(cls=Cover, primary_key=FRONT_PK)
    assert fresh.image == featured, "an unfeatured heal never steals the print"
    healed = [f for f in os.listdir(folder) if f.startswith("healed-")]
    assert healed, "the healed art joined the wall as a new take"


def test_apply_preserves_acetate_alpha_outside_the_patch(storage):
    """A clear acetate healed in a marked region: outside the patch the
    ORIGINAL's transparency survives verbatim in the healed file — and the
    original acetate itself is never touched."""
    from gui.image_editor_choices import _apply
    front = storage.read_object(cls=Cover, primary_key=FRONT_PK)
    folder = os.path.dirname(front.image)

    original = os.path.join(folder, "clear-acetate.png")
    art = Image.new("RGBA", (64, 96), (90, 90, 90, 255))
    for x in range(64):                       # the bottom half is CLEAR
        for y in range(48, 96):
            art.putpixel((x, y), (0, 0, 0, 0))
    art.save(original)
    front.image = original                     # feature it so the swap runs
    storage.update_object(front)

    chosen = os.path.join(folder, "choice-s1-00.png")
    Image.new("RGB", (64, 96), (250, 10, 10)).save(chosen)   # fully opaque
    region = {"x": 0, "y": 0, "width": 32, "height": 32}
    with open(os.path.join(folder, ".choices-s1.json"), "w") as f:
        json.dump({"image": original, "choices": [chosen], "session_id": "s1",
                   "region": region, "mode": "inpaint"}, f)

    st = _bench_state(storage, original, [chosen], _trail(original))
    _apply(st)

    assert os.path.exists(original), "the acetate itself is never touched"
    fresh = storage.read_object(cls=Cover, primary_key=FRONT_PK)
    assert fresh.image != original and os.path.exists(fresh.image)
    healed = Image.open(fresh.image).convert("RGBA")
    assert healed.getpixel((5, 90))[3] == 0, \
        "outside the patch, the original's transparency rules"
    assert healed.getpixel((5, 5))[3] == 255, \
        "inside the patch, the take's own alpha rules"
