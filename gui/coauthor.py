"""
The coauthor speaks first.

When a view opens with a fresh conversation, the coauthor posts one short,
context-aware line, and suggestion chips above the input offer natural next
messages.  Chips SEND MESSAGES into the conversation — they are conversation
starters, not wired buttons.  Everything is computed from cheap storage reads;
no model call is made until the user actually speaks.
"""
import os
from loguru import logger

from schema import CharacterModel, CharacterVariant, Cover, Issue, Panel, SceneModel, Series, Setting


def opening_and_chips(state) -> tuple[str | None, list[str]]:
    """
    Returns (opening_line, suggestion_chips) for the current selection.
    The opening line may be None (nothing worth saying beats saying nothing).
    """
    sel = state.selection
    storage = state.storage
    kind = sel[-1].kind.value if sel else "lobby"
    try:
        match kind:
            case "lobby":
                from gui.home import all_house_publishers
                if not all_house_publishers(storage):
                    return ("Welcome to the studio.  I'm the Editor — tell me a story "
                            "and I'll help you build it into a comic.  First we need "
                            "a publishing house to work in.",
                            ["Found a publishing house", "What can you do?"])
                return ("Welcome back.  The bench you left is on the card — "
                        "or tell me what we're making today.",
                        ["Pick up where I left off", "Start something new…",
                         "What still needs doing?"])

            case "library":
                return ("I keep the studio's collection — every character, wardrobe and setting across all series.  Ask me to find something or import it into a series.",
                        ["What characters do we have?", "What settings do we have?"])

            case "series":
                series_id = sel[-1].id
                issues = storage.read_all_objects(Issue, {"series_id": series_id})
                chars = storage.read_all_objects(CharacterModel, {"series_id": series_id})
                if not issues:
                    return ("This series has no issues yet.  Give me a story and I'll break it down into a full issue — scenes, cast, panels.",
                            ["Create issue 1 from a story idea", "Create a character", "Import a character from the library"])
                return (None,
                        ["Create a new issue", "Create a character", "Import an asset from the library"])

            case "issue":
                # the Editor quotes THE PRODUCTION LEDGER — the same truth
                # the masthead badge and the colophon print
                series_id, issue_id = sel[-2].id, sel[-1].id
                from helpers.ledger import issue_ledger
                led = issue_ledger(storage, series_id, issue_id)
                by = {l.key: l for l in led.lines}
                if not by['script'].ok:
                    return ("Paste the story you want in this issue and I'll break it down — scenes with settings and cast, then panels.",
                            ["Break my story into scenes", "Create a front cover"])
                if led.complete:
                    return ("The ledger is clean — every panel inked and placed.  This issue is ready to bind.",
                            ["Export the issue as a PDF", "Read the issue"])
                chips = []
                if 'breakdown' in by and not by['breakdown'].ok:
                    # the whole book is waiting on the breakdown — offer it first
                    chips.append("Break the script into scenes")
                if 'panels' in by and not by['panels'].ok:
                    chips.append(f"Render the {by['panels'].count} missing panels")
                if 'scenes' in by and not by['scenes'].ok:
                    chips.append("Break the scenes into panels")
                if not by['covers'].ok:
                    chips.append("Create a front cover" if 'no front cover' in by['covers'].text
                                 else "Render the front cover")
                if 'inserts' in by and not by['inserts'].ok:
                    chips.append("Render the inserts")
                chips.append("Export the issue as a PDF")
                todo = ";  ".join(l.text for l in led.todos[:3])
                return (f"The production ledger reads: {todo}.  Want me to work through it?",
                        chips[:3])

            case "scene":
                series_id, issue_id, scene_id = sel[-3].id, sel[-2].id, sel[-1].id
                scene = storage.read_object(SceneModel, {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
                panels = storage.read_all_objects(Panel, {"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
                chips = []
                if scene and not scene.setting_id:
                    chips.append("Give this scene a setting")
                if not panels:
                    return ("No panels yet — I can thumbnail a layout from the scene's story, one beat per panel.",
                            ["Break this scene into panels"] + chips)
                unrendered = [p for p in panels if not (p.image and os.path.exists(p.image))]
                if unrendered:
                    return (f"{len(panels)} panels, {len(unrendered)} unrendered.",
                            [f"Render the missing panels"] + chips + ["Add a panel"])
                return (None, chips + ["Add a panel", "Reorder the panels"])

            case "panel":
                return (None, ["Compose this panel: …", "Render this panel", "Punch up the dialogue"])

            case "character":
                series_id, character_id = sel[-2].id, sel[-1].id
                variants = storage.read_all_objects(CharacterVariant, {"series_id": series_id, "character_id": character_id})
                if not variants:
                    return ("No looks yet — describe the base look once (that's the identity), and every other look gets composed from it.",
                            ["Create the base look", "Create the base look from an image"])
                return (None, ["Compose a new look from an outfit", "Extract this character's wardrobe into outfits"])

            case "variant":
                return (None, ["Render the reference sheet", "Swap the outfit", "Extract this look's outfit"])

            case "styled-variant":
                return (None, ["Re-ink this sheet", "Sculpt the exemplar portrait"])

            case "outfit":
                return (None, ["Render this outfit's reference art",
                               "Compose a look wearing this outfit"])

            case "prop":
                return (None, ["Render this prop's reference art",
                               "Put this prop in a scene"])

            case "setting":
                series_id, setting_id = sel[-2].id, sel[-1].id
                setting = storage.read_object(Setting, {"series_id": series_id, "setting_id": setting_id})
                if setting is not None and not setting.images:
                    return ("This setting has no master backgrounds yet — render one per style and every panel set here will share it.",
                            ["Render a master background", "Add props"])
                return (None, ["Render a master background in another style", "Update the props"])

            case "cover":
                series_id = sel[-3].id if len(sel) > 2 else None
                cover = storage.read_object(Cover, {"series_id": series_id, "issue_id": sel[-2].id, "cover_id": sel[-1].id}) if series_id else None
                if cover is not None and not cover.image:
                    return ("This cover hasn't been rendered.  Compose it on the light table or describe the scene you want — I can also propose one from the issue's story.",
                            ["Compose this cover: …", "Propose a cover concept", "Render the cover"])
                return (None, ["Compose this cover: …", "Re-render the cover", "Try a different text layout"])

            case "insert":
                from schema import Insert
                series_id = sel[-3].id if len(sel) > 2 else None
                ins = storage.read_object(Insert, {"series_id": series_id, "issue_id": sel[-2].id,
                                                   "insert_id": sel[-1].id}) if series_id else None
                if ins is not None and not ins.image:
                    return (f"This {ins.kind} reads as typeset words until it's inked — "
                            f"compose it on the light table or say the word and I'll render it.",
                            ["Render this page", "Work on the words with me", "Move it in the book"])
                return (None, ["Re-render this page", "Rework it on the table", "Move it in the book"])

            case "image-editor":
                return ("The acetate's on the bench.  Drag a marquee over what needs "
                        "fixing and tell me what belongs there — I'll repaint just that "
                        "patch.  Or we can extend the paper past its edges.",
                        ["Heal the marked patch: …", "Extend the paper into …"])

            case "image-editor-choices":
                return ("The takes are on the sheet — pick the one that reads best and "
                        "paste it down.  The original stays safe either way.", [])

            case "style":
                return (None, ["Generate an art style example", "Tune the bubble styles"])

            case "all-styles":
                return (None, ["Create a new style", "Compare the styles"])

            case "all-publishers":
                return ("Welcome to the studio.  Every series lives under its publisher — pick one, or found a new house.",
                        ["Create a publisher", "What series do we publish?"])

            case "publisher":
                return (None, ["Create a new series", "Compare the house styles", "Generate the logo"])
    except Exception as e:  # never let the greeter break the page
        logger.debug(f"coauthor opener skipped: {e}")
    return (None, [])


# The studio staff: who you're talking to on each view.  The coauthor is a
# person with a role, not a "Bot".
ROLE_NAMES = {
    "lobby": "the Editor",
    "artboard": "the Letterer",
    "all-series": "the Editor",
    "all-publishers": "the Editor",
    "all-styles": "the Art Director",
    "library": "the Librarian",
    "series": "the Editor",
    "issue": "the Editor",
    "scene": "the Layout Artist",
    "panel": "the Penciller",
    "character": "the Character Designer",
    "variant": "the Character Designer",
    "styled-variant": "the Character Designer",
    "outfit": "the Character Designer",
    "prop": "the Prop Master",
    "setting": "the Background Artist",
    "cover": "the Cover Artist",
    "insert": "the Production Artist",
    "front-cover": "the Cover Artist",
    "back-cover": "the Cover Artist",
    "inside-front-cover": "the Cover Artist",
    "inside-back-cover": "the Cover Artist",
    "style": "the Art Director",
    "publisher": "the Editor",
    "image-editor": "the Inker",
    "image-editor-choices": "the Inker",
}


def coauthor_name(selection) -> str:
    kind = selection[-1].kind.value if selection else "all-series"
    return ROLE_NAMES.get(kind, "the Coauthor")
