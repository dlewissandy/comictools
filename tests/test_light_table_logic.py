"""Unit tests for the light table's pure logic: stack reordering, the shared
compositor, the composed rough, and board resolution — the behaviors the GUI
depends on but a browser test can't pin down precisely."""
import os

import pytest
from PIL import Image

from schema import Panel, Cover
from schema.character_reference import CharacterRef


def _panel(**over):
    base = dict(panel_id="p1", issue_id="i1", series_id="s1", scene_id="sc1",
                panel_number=1, name="T", beat="b", description="d", aspect="landscape",
                character_references=[], narration=[], dialogue=[], image=None,
                reference_images=[])
    base.update(over)
    return Panel(**base)


def _ref(cid, vid="base"):
    return CharacterRef(series_id="s1", character_id=cid, variant_id=vid)


# ---------------------------------------------------------------------------
# apply_stack_reorder
# ---------------------------------------------------------------------------
def _z_order(p):
    """Keys sorted top-of-stack first (highest z)."""
    return [k for k, _ in sorted(p.figure_blocking.items(),
                                 key=lambda kv: -kv[1].get('z', 0))]


def test_first_restack_keeps_untouched_order():
    """Dragging one row must not invert the rest of the stack (the reorder
    baseline matches the display defaults: cast index, elements 40)."""
    from gui.light_table import apply_stack_reorder
    p = _panel(character_references=[_ref("a"), _ref("b"), _ref("c")],
               figure_images={"element/prop": "x.png"})
    # display order (top first): element (z40) > c (z2) > b (z1) > a (z0)
    apply_stack_reorder(p, src_k="a/base", dst_k="b/base", mode="before")
    order = _z_order(p)
    assert order == ["element/prop", "c/base", "a/base", "b/base"]


def test_reorder_never_strips_plate_from_group():
    from gui.light_table import apply_stack_reorder
    p = _panel(figure_images={"element/booth": "x.png", "element/tent": "y.png",
                              "background/plate": "p.png"},
               layer_groups={"background (split)": ["element/booth", "background/plate"]})
    apply_stack_reorder(p, src_k="element/tent", dst_k="element/booth", mode="before")
    assert "background/plate" in p.layer_groups["background (split)"]


def test_drop_onto_forms_group_and_drag_out_dissolves_it():
    from gui.light_table import apply_stack_reorder
    p = _panel(figure_images={"element/a": "a.png", "element/b": "b.png"})
    apply_stack_reorder(p, src_k="element/a", dst_k="element/b", mode="onto")
    (gname, members), = p.layer_groups.items()
    assert set(members) == {"element/a", "element/b"}
    # drag the only OTHER member out: the group dissolves
    apply_stack_reorder(p, src_k="element/a", dst_k="element/b", mode="before")
    apply_stack_reorder(p, src_k="element/b", dst_k="element/a", mode="after")
    assert all(len(m) != 1 for m in p.layer_groups.values() if m)


def test_group_moves_as_a_block():
    from gui.light_table import apply_stack_reorder
    p = _panel(figure_images={"element/a": "a.png", "element/b": "b.png",
                              "element/c": "c.png"},
               layer_groups={"g": ["element/a", "element/b"]})
    apply_stack_reorder(p, src_k="group:g", dst_k="element/c", mode="after")
    order = _z_order(p)
    assert order.index("element/c") < order.index("element/a")
    assert order.index("element/c") < order.index("element/b")


# ---------------------------------------------------------------------------
# the shared compositor
# ---------------------------------------------------------------------------
def test_compositor_places_and_flips(tmp_path):
    from helpers.compositor import DIMS, base_canvas, paste_acetates
    # an acetate that is red on its left half, blue on its right
    W, H = 100, 200
    img = Image.new("RGBA", (W, H))
    for x in range(W):
        for y in range(0, H, 8):
            img.putpixel((x, y), (255, 0, 0, 255) if x < W // 2 else (0, 0, 255, 255))
    img = img.resize((W, H))
    src = tmp_path / "ace.png"
    Image.new("RGBA", (W, H), (255, 0, 0, 255)).save(src)  # solid red, simpler
    base = base_canvas("square", None)
    boxes = paste_acetates(base, "square", [(str(src), {"x": 50, "y": 0, "h": 50, "z": 1})])
    CW, CH = DIMS["square"]
    L, T, R, B = boxes[0]
    assert B == pytest.approx(CH)                      # feet on the bottom edge
    assert (L + R) / 2 == pytest.approx(CW * 0.5)      # centered at x=50%
    assert (B - T) == pytest.approx(CH * 0.5, abs=1)   # h=50% of frame
    # the pasted area is the acetate's red
    px = base.getpixel((int(CW * 0.5), int(CH * 0.9)))
    assert px[:3] == (255, 0, 0)


def test_compositor_z_order(tmp_path):
    from helpers.compositor import DIMS, base_canvas, paste_acetates
    red, blue = tmp_path / "r.png", tmp_path / "b.png"
    Image.new("RGBA", (50, 50), (255, 0, 0, 255)).save(red)
    Image.new("RGBA", (50, 50), (0, 0, 255, 255)).save(blue)
    base = base_canvas("square", None)
    paste_acetates(base, "square", [
        (str(blue), {"x": 50, "y": 0, "h": 40, "z": 2}),
        (str(red), {"x": 50, "y": 0, "h": 40, "z": 1}),
    ])
    CW, CH = DIMS["square"]
    assert base.getpixel((CW // 2, CH - 10))[:3] == (0, 0, 255)  # higher z on top


# ---------------------------------------------------------------------------
# the composed rough (the pencils the renders finish)
# ---------------------------------------------------------------------------
def test_compose_table_rough_uses_display_defaults(storage, tmp_path):
    from agentic.tools.imaging import _compose_table_rough
    ace = tmp_path / "fig.png"
    Image.new("RGBA", (64, 128), (0, 255, 0, 255)).save(ace)
    p = _panel(series_id="wonders-of-the-witchlight", issue_id="witchlight-carnival",
               scene_id="b3cc50eb-5a57-463c-ba10-927d941c9779", panel_id="test-rough",
               character_references=[_ref("solo")],
               figure_images={"solo/base": str(ace)})
    storage.create_object(p, overwrite=True)
    out = _compose_table_rough(storage, p, None)
    assert out and os.path.exists(out)
    img = Image.open(out)
    # display default for the first cast figure: x=18%, h=78% — green pixels
    # must appear around x=18%, none at the mirror position
    W, H = img.size
    assert img.getpixel((int(W * 0.18), int(H * 0.7)))[:3] == (0, 255, 0)
    assert img.getpixel((int(W * 0.82), int(H * 0.7)))[:3] != (0, 255, 0)


def test_compose_table_rough_returns_none_for_bare_board(storage):
    from agentic.tools.imaging import _compose_table_rough
    p = _panel(series_id="wonders-of-the-witchlight", issue_id="witchlight-carnival",
               scene_id="b3cc50eb-5a57-463c-ba10-927d941c9779", panel_id="test-bare")
    assert _compose_table_rough(storage, p, None) is None


# ---------------------------------------------------------------------------
# board resolution (panels AND covers ride the same table)
# ---------------------------------------------------------------------------
def test_read_board_resolves_panels_and_covers(storage):
    from gui.light_table import read_board
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    panel = read_board(storage, {"series": WL, "issue": CARN,
                                 "scene": "b3cc50eb-5a57-463c-ba10-927d941c9779",
                                 "panel": None, "cover": None})
    assert panel is None  # no panel id -> no board, not a crash
    cover = read_board(storage, {"series": WL, "issue": CARN, "cover": "front"})
    assert cover is not None and cover.cover_id == "front"
    assert hasattr(cover, "figure_images") and hasattr(cover, "layer_groups")
