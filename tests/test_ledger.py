"""ONE PRODUCTION LEDGER: every surface quotes helpers/ledger.py, so the
counts can never disagree.  These tests pin the ledger's honesty."""
import os

from helpers.ledger import issue_ledger
from schema import Panel, SceneModel

WL, CARN = "wonders-of-the-witchlight", "witchlight-carnival"


def test_ledger_counts_match_storage(storage):
    led = issue_ledger(storage, WL, CARN)
    keys = [line.key for line in led.lines]
    assert len(keys) == len(set(keys)), "one line per truth — no duplicates"
    assert 'script' in keys and 'covers' in keys

    # the panels line must count exactly what storage holds
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    panels = [p for sc in scenes for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id})]
    unrendered = [p for p in panels if not (p.image and os.path.exists(p.image))]
    by = {line.key: line for line in led.lines}
    if panels:
        assert by['panels'].count == len(unrendered)
        assert by['panels'].ok == (not unrendered)


def test_every_todo_line_is_a_door(storage):
    """A line that reports work must point somewhere: an anchor in the open
    book or at least a dial stop."""
    led = issue_ledger(storage, WL, CARN)
    for line in led.todos:
        assert line.anchor or line.detail, f"ledger line '{line.key}' has no door"


def test_ledger_notices_an_uninked_panel(storage):
    import pytest
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    panel = next((p for sc in scenes for p in storage.read_all_objects(
        Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id})
        if p.image and os.path.exists(p.image)), None)
    if panel is None:
        pytest.skip("no inked panel in the fixture data to un-ink")
    before = issue_ledger(storage, WL, CARN)
    n0 = {l.key: l for l in before.lines}['panels'].count
    panel.image = None
    storage.update_object(panel)
    led = issue_ledger(storage, WL, CARN)
    line = {l.key: l for l in led.lines}['panels']
    assert line.count == n0 + 1 and not line.ok
    # the door leads to the FIRST uninked panel so the click answers
    assert line.anchor and line.anchor.startswith('panel-')
    assert not led.complete
    assert 'before press' in led.summary()


def test_ledger_sees_the_unbroken_script(storage):
    """A story with zero scenes is the whole book waiting, not silence —
    the ledger must say so, and the line must door to the script."""
    from schema import Issue, Story, Insert, Cover
    issue = storage.read_object(Issue, {"series_id": WL, "issue_id": CARN})
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    for sc in scenes:
        for pnl in storage.read_all_objects(
                Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id}):
            storage.delete_object(Panel, {"series_id": WL, "issue_id": CARN,
                                          "scene_id": sc.scene_id, "panel_id": pnl.panel_id})
        storage.delete_object(SceneModel, {"series_id": WL, "issue_id": CARN,
                                           "scene_id": sc.scene_id})
    issue.story = "One dark and stormy night " * 50   # a real script, unbroken
    storage.update_object(issue)

    led = issue_ledger(storage, WL, CARN)
    by = {l.key: l for l in led.lines}
    assert by['script'].ok, "the words exist"
    assert 'breakdown' in by and not by['breakdown'].ok
    assert 'waits to be broken into scenes' in by['breakdown'].text
    assert by['breakdown'].anchor and by['breakdown'].anchor.startswith('story-')
    assert by['breakdown'].detail == 'stories'
    assert not led.complete


def test_broken_script_clears_the_breakdown_line(storage):
    led = issue_ledger(storage, WL, CARN)
    assert 'breakdown' not in {l.key for l in led.lines}, \
        "scenes exist — the breakdown debt is paid and the line stays silent"


def test_breakdown_line_doors_to_the_story_sheet(storage):
    """When the script lives in a Story object, the breakdown line anchors
    THAT story sheet — the click answers with the words themselves."""
    from schema import Issue, Story
    issue = storage.read_object(Issue, {"series_id": WL, "issue_id": CARN})
    scenes = storage.read_all_objects(SceneModel, {"series_id": WL, "issue_id": CARN})
    for sc in scenes:
        for pnl in storage.read_all_objects(
                Panel, {"series_id": WL, "issue_id": CARN, "scene_id": sc.scene_id}):
            storage.delete_object(Panel, {"series_id": WL, "issue_id": CARN,
                                          "scene_id": sc.scene_id, "panel_id": pnl.panel_id})
        storage.delete_object(SceneModel, {"series_id": WL, "issue_id": CARN,
                                           "scene_id": sc.scene_id})
    issue.story = ""
    storage.update_object(issue)
    storage.create_object(Story(story_id="feature", issue_id=CARN, series_id=WL,
                                story_number=1, name="The Feature",
                                text="a real script " * 40))
    st = storage.read_all_objects(Story, {"series_id": WL, "issue_id": CARN})[0]

    led = issue_ledger(storage, WL, CARN)
    by = {l.key: l for l in led.lines}
    assert 'breakdown' in by and not by['breakdown'].ok
    assert by['breakdown'].anchor == f'story-{st.story_id}'
    assert str(len(st.text.split())) in by['breakdown'].text, "the word count is the debt's size"


def test_the_ledger_sees_script_drift(storage):
    """Edit the script after its breakdown and the ledger says the scenes
    still draw the old story — drift is never silent."""
    import hashlib
    from schema import Issue, Story
    issue = storage.read_object(Issue, {"series_id": WL, "issue_id": CARN})
    stories = storage.read_all_objects(Story, {"series_id": WL, "issue_id": CARN})
    txt = (issue.story or '') + '|' + '|'.join((st.text or '') for st in stories)
    issue.broken_script_sha = hashlib.sha1(txt.encode()).hexdigest()
    storage.update_object(data=issue)
    led = issue_ledger(storage, WL, CARN)
    assert 'drift' not in {l.key for l in led.lines}, "matching hash — no drift"

    issue.story = (issue.story or '') + "  And then act two changed entirely."
    storage.update_object(data=issue)
    led = issue_ledger(storage, WL, CARN)
    by = {l.key: l for l in led.lines}
    assert 'drift' in by and not by['drift'].ok
    assert "changed after its breakdown" in by['drift'].text


def test_character_card_prefers_the_base_look_by_any_base_name(storage):
    """The character card shows the BASE look — even when the base is named
    '<Character> Base' with a UUID id, never an arbitrary costume."""
    import os
    from schema import CharacterModel, CharacterVariant
    S = "wonders-of-the-witchlight"
    storage.create_object(CharacterModel(character_id="vera", series_id=S,
        name="Vera", description="a PI"), overwrite=True)

    def _mk(vid, name):
        v = CharacterVariant(variant_id=vid, series_id=S, character_id="vera",
            name=name, description="d", race="human", gender="f", age="40s",
            height="avg", attire="a", behavior="b", appearance="ap", images={})
        storage.create_object(v, overwrite=True)
        d = os.path.join(str(storage.base_path), "series", S, "characters", "vera",
                         "variants", vid, "images", "vintage-four-color")
        os.makedirs(d, exist_ok=True)
        from PIL import Image
        art = os.path.join(d, "sheet.jpg")
        Image.new("RGB", (80, 53), (10, 20, 30)).save(art)
        v.images = {"vintage-four-color": art}
        storage.update_object(v)
        return art

    costume = _mk("zzz-costume", "Ballgown")   # sorts last by id
    base_art = _mk("aaa-uuid", "Vera Base")    # a '… base' name, non-'base' id
    pick = storage.find_character_image(series_id=S, character_id="vera")
    assert pick == base_art, "the card wears the base look, not the costume"
