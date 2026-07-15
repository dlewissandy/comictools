"""EVERY BUTTON KEEPS ITS PROMISE: a button that briefs the coauthor must
post into a context whose toolkit holds the tools the brief names — and
every agent context must have a persona, or it speaks with no voice.

These pins came from a full audit of post_user_message sites vs toolkits
(2026-07-15).  If a button's message and its context's toolkit drift apart
again, one of these fails and names the broken promise."""
import re


def _names(kind):
    from agentic.toolkits import TOOLKITS
    return {getattr(t, "name", str(t)) for t in TOOLKITS[kind]}


def test_boards_with_cast_can_ink_a_missing_sheet():
    """light_table's 'Ink X's reference sheet' button posts from panel,
    cover AND insert benches — all three must hold the inking tool."""
    for kind in ("panel", "cover", "front-cover", "back-cover",
                 "inside-front-cover", "inside-back-cover", "insert"):
        assert "create_styled_image_for_character_variant" in _names(kind), kind


def test_the_borrow_door_keeps_its_promise():
    """THE DRAWER RETIRED: the pickers' 'Borrow from another series…' door
    prefills an import ask — every bench context must hold the import
    tools that ask names."""
    for kind in ("issue", "panel", "cover", "insert"):
        assert {"import_character", "import_setting"} <= _names(kind), kind
    for kind in ("issue", "panel"):
        assert {"import_prop", "import_outfit"} <= _names(kind), kind


def test_pickers_offer_the_borrow_door():
    """All three bench pickers carry the borrow footer."""
    src = open("gui/light_table.py").read()
    assert src.count("Borrow from another series…") == 3
    assert "gui/drawer" not in open("main.py").read(), "the drawer is retired"


def test_an_uploaded_picture_can_reach_a_panel():
    """The scene's drop-an-image flow names attach_panel_reference — the
    scene and panel contexts must hold it, and the tool must really attach."""
    assert "attach_panel_reference" in _names("scene")
    assert "attach_panel_reference" in _names("panel")


def test_the_sheet_grids_delete_button_has_its_tool():
    """The styled-sheet grid posts 'delete the currently selected …' — the
    styled-variant context must hold delete_styled_image."""
    assert "delete_styled_image" in _names("styled-variant")


def test_every_agent_context_has_a_voice():
    """Every toolkit context must carry a persona — an agent with an empty
    persona answers with no idea what room it is standing in."""
    from agentic.toolkits import TOOLKITS
    from agentic.instructions import PERSONAS
    missing = [k for k in TOOLKITS if not (PERSONAS.get(k) or "").strip()]
    assert missing == [], f"contexts with no persona: {missing}"


def test_button_briefs_name_tools_that_exist():
    """Any post_user_message literal that names a tool in parentheses or
    inline must name a REAL tool — a brief citing a ghost tool strands the
    agent."""
    import glob
    from agentic.toolkits import TOOLKITS
    all_tools = {getattr(t, "name", str(t)) for kit in TOOLKITS.values() for t in kit}
    ghost = []
    for path in glob.glob("gui/*.py"):
        for line in open(path):
            # a citation is a tool name written INSIDE a message string —
            # a quote must open before it on the line (code identifiers
            # like os.makedirs(export_dir) don't count)
            for m in re.finditer(r"\(([a-z_]+_[a-z_]+(?:_[a-z_]+)*)[,) ]", line):
                name = m.group(1)
                if not name.startswith(("create_", "update_", "delete_",
                                        "generate_", "import_", "attach_",
                                        "compose_", "swap_", "extract_")):
                    continue
                prefix = line[:m.start()]
                if prefix.count('"') % 2 == 0 and prefix.count("'") % 2 == 0:
                    continue                      # not inside a string
                if name not in all_tools:
                    ghost.append(f"{path}: ({name})")
    assert ghost == [], f"briefs citing ghost tools: {ghost}"


def test_attach_panel_reference_attaches(storage):
    """The new tool's body: attaching an existing file lands it in the
    panel's reference_images with the asked relation."""
    import os
    import json
    from types import SimpleNamespace
    from schema import Panel, SceneModel
    WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    panel = next(p for sc in scenes for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id}))
    img = os.path.join(str(storage.base_path), ".promise-test.png")
    from PIL import Image
    Image.new("RGB", (8, 8), "red").save(img)

    import asyncio
    from agentic.tools.updater import attach_panel_reference
    wrapper = SimpleNamespace(context=SimpleNamespace(storage=storage, is_dirty=False))
    out = asyncio.run(
        attach_panel_reference.on_invoke_tool(wrapper, json.dumps({
            "series_id": WL, "issue_id": CARN, "scene_id": panel.scene_id,
            "panel_id": panel.panel_id, "image_path": img, "relation": "left"})))
    assert "Attached" in str(out)
    fresh = storage.read_object(Panel, {"series_id": WL, "issue_id": CARN,
                                        "scene_id": panel.scene_id, "panel_id": panel.panel_id})
    ref = (fresh.reference_images or [])[-1]
    assert ref.image == img and ref.relation.value == "left"


def test_a_take_wears_its_own_orientation(tmp_path):
    """The takes wall frames each take by the IMAGE's orientation — a
    portrait render on a landscape-flipped board must get a portrait frame
    (fit=cover would otherwise crop it sideways)."""
    from PIL import Image
    from schema.enums import FrameLayout
    from gui.light_table import take_shape, TAKE_SHAPES

    land = str(tmp_path / "l.jpg"); Image.new("RGB", (1536, 1024)).save(land)
    port = str(tmp_path / "p.jpg"); Image.new("RGB", (1024, 1536)).save(port)
    sq = str(tmp_path / "s.jpg"); Image.new("RGB", (1024, 1024)).save(sq)

    # the art decides, whatever the board claims
    assert take_shape(port, FrameLayout.LANDSCAPE) == TAKE_SHAPES[FrameLayout.PORTRAIT]
    assert take_shape(land, FrameLayout.PORTRAIT) == TAKE_SHAPES[FrameLayout.LANDSCAPE]
    assert take_shape(sq, FrameLayout.LANDSCAPE) == TAKE_SHAPES[FrameLayout.SQUARE]
    # an unreadable file falls back to the board's shape
    assert take_shape(str(tmp_path / "missing.jpg"), FrameLayout.PORTRAIT) \
        == TAKE_SHAPES[FrameLayout.PORTRAIT]


def test_a_silent_turn_speaks_the_work():
    """A run that ends on a bare tool call gets a closing balloon built from
    the tools' own human answers — not an apologetic shrug."""
    from messaging import closing_from_receipts
    out = closing_from_receipts([
        "called create_scene({...})",
        "→ Created scene 3 'Joey's Bedroom' (scene_id=abc).",
        "→ {\"raw\": \"structured payload stays out\"}",
        "→ " + "x" * 400,
        "→ PROBLEM: nothing to see here",
    ])
    assert out is not None
    assert "Created scene 3 'Joey's Bedroom'" in out
    assert "structured payload" not in out and "xxx" not in out and "PROBLEM" not in out
    assert closing_from_receipts(["called read_scene({})"]) is None


def test_racks_scroll_not_overflow():
    """ONE DIALOG SHELL: every bench picker rides studio_dialog with
    scroll=True — a 30-swatch rack keeps its footer reachable."""
    src = open("gui/light_table.py").read()
    for title in ("Lay a figure on the table", "Lay a background on the table",
                  "Lay a prop on the table", "Swap the style swatch"):
        at = src.index(title)
        window = src[max(0, at - 300):at]
        assert "studio_dialog" in window, f"{title} still hand-rolls its shell"
    assert "studio_dialog" in open("gui/scene.py").read()
