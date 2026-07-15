"""THE PRODUCTION BOARD: one staged account of how far an issue has come
from script to bound book, broken down by story and scene.

A comics issue moves through fixed stages — the script gets written, it
breaks into scenes, the scenes break into beats (panels), the beats get
laid out on pages, the panels get roughed on the light table and then
inked, and the covers get roughed and inked.  The colophon prints THIS
board as the issue's dashboard: every stage knows its tally, and every
row is a door into the open book.

This reads the same truths the ledger does (helpers/ledger.py) but keeps
the per-story / per-scene shape the dashboard needs.  Nothing here counts
anything the ledger contradicts — both walk the same objects.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


# THE EIGHT STAGES, in production order.  key -> (label, dial detail)
STAGE_ORDER = [
    ("scripted", "stories scripted", "stories"),
    ("scenes", "scenes created", "scenes"),
    ("beats", "beats created", "beats"),
    ("layout", "layout completed", "beats"),
    ("roughed", "panels roughed", "beats"),
    ("inked", "panels inked", "beats"),
    ("covers_roughed", "covers roughed", None),
    ("covers_inked", "covers inked", None),
]


@dataclass
class SceneRow:
    scene_id: str
    name: str
    scene_number: int
    panels: int            # beats that exist
    laid: int              # panels placed on a page
    roughed: int           # panels with light-table pencils
    inked: int             # panels rendered to art
    anchor: str            # data-banchor door in the open book

    @property
    def has_beats(self) -> bool:
        return self.panels > 0


@dataclass
class StoryRow:
    story_id: str | None   # None == the issue's own opening script
    name: str
    scripted: bool
    scenes: list[SceneRow]
    anchor: str
    writer: str | None = None
    artist: str | None = None
    letterer: str | None = None

    @property
    def scenes_created(self) -> bool:
        return bool(self.scenes)

    @property
    def panels(self) -> int:
        return sum(s.panels for s in self.scenes)


@dataclass
class Stage:
    key: str
    label: str
    done: int
    total: int
    anchor: str | None = None      # first offender's door
    detail: str | None = None      # dial stop that shows it

    @property
    def ok(self) -> bool:
        # a stage with nothing upstream yet is not "done" — it is simply not
        # started; only a stage with work, all of it finished, is complete
        return self.total > 0 and self.done >= self.total

    @property
    def started(self) -> bool:
        return self.total > 0


@dataclass
class ProductionBoard:
    stories: list[StoryRow]
    stages: list[Stage]
    cover_slots: int
    cover_roughed: int
    cover_inked: int

    def stage(self, key: str) -> Stage:
        return next(s for s in self.stages if s.key == key)

    @property
    def press_ready(self) -> bool:
        return all(s.ok for s in self.stages if s.started)

    def summary(self) -> str:
        """The shortest true account for the masthead badge."""
        pending = [s for s in self.stages if s.started and not s.ok]
        if not pending:
            return "press-ready"
        left = sum(s.total - s.done for s in pending)
        return f"{left} thing{'s' if left != 1 else ''} before press"


def production_board(storage, series_id: str, issue_id: str) -> ProductionBoard:
    """Read the whole issue once and stage it from script to bound book."""
    from schema import Issue, Story, SceneModel, Panel, Cover
    from helpers.binder import page_coverage

    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    pk = {"series_id": series_id, "issue_id": issue_id}
    stories_all = sorted(storage.read_all_objects(Story, primary_key=pk),
                         key=lambda s: s.story_number)
    scenes = storage.read_all_objects(SceneModel, primary_key=pk, order_by="scene_number")
    panels_by_scene = {sc.scene_id: storage.read_all_objects(
        Panel, primary_key={**pk, "scene_id": sc.scene_id}, order_by="panel_number")
        for sc in scenes}
    covers = storage.read_all_objects(Cover, primary_key=pk)

    _has_layout, placed, _unplaced, _dangling = (
        page_coverage(storage, series_id, issue_id) if scenes else (False, set(), [], []))

    def rendered(obj) -> bool:
        return bool(getattr(obj, "image", None) and os.path.exists(obj.image))

    def roughed(obj) -> bool:
        # a beat is "roughed" once the author has pencilled it on the light
        # table — any acetate or plate placed counts as the start of a rough
        return bool(getattr(obj, "figure_images", None)) or rendered(obj)

    # GROUP SCENES UNDER THEIR STORY: a scene whose story_id names no real
    # story (or is None) falls under the issue's own opening script.
    real_ids = {st.story_id for st in stories_all}
    by_story: dict[str | None, list] = {}
    for sc in scenes:
        sid = sc.story_id if sc.story_id in real_ids else None
        by_story.setdefault(sid, []).append(sc)

    def _scene_row(sc) -> SceneRow:
        ps = panels_by_scene[sc.scene_id]
        return SceneRow(
            scene_id=sc.scene_id, name=sc.name, scene_number=sc.scene_number,
            panels=len(ps),
            laid=sum(1 for p in ps if (sc.scene_id, p.panel_id) in placed),
            roughed=sum(1 for p in ps if roughed(p)),
            inked=sum(1 for p in ps if rendered(p)),
            # a paneled scene renders as beat TILES (panel-… anchors) at the
            # dashboard's landing altitude — aim at its first tile, exactly
            # like the '{n} panels' chip; only a bare scene keeps its slip
            anchor=(f"panel-{ps[0].panel_id}" if ps else f"scene-{sc.scene_id}"))

    story_rows: list[StoryRow] = []

    # the issue's own opening script leads the book whenever it has words or
    # holds unfiled scenes; a brand-new issue with neither still shows it so
    # the dashboard always has a first line to pencil into
    lead_scenes = by_story.get(None, [])
    if (issue and issue.story) or lead_scenes or not stories_all:
        story_rows.append(StoryRow(
            story_id=None, name=(issue.name if issue else "the script"),
            scripted=bool(issue and issue.story),
            scenes=[_scene_row(sc) for sc in lead_scenes],
            anchor="story-script",
            writer=(issue.writer if issue else None),
            artist=(issue.artist if issue else None),
            letterer=None))

    for st in stories_all:
        story_rows.append(StoryRow(
            story_id=st.story_id, name=st.name, scripted=bool(st.text),
            scenes=[_scene_row(sc) for sc in by_story.get(st.story_id, [])],
            anchor=f"story-{st.story_id}",
            writer=st.writer, artist=st.artist, letterer=st.letterer))

    # ---- roll the per-story/per-scene truths up into the eight stages ----
    all_scene_rows = [sr for st in story_rows for sr in st.scenes]
    total_panels = sum(sr.panels for sr in all_scene_rows)

    def _first_unscripted():
        return next((st for st in story_rows if not st.scripted), None)

    def _first_unbroken():
        return next((st for st in story_rows if st.scripted and not st.scenes_created), None)

    def _first_beatless():
        return next((sr for sr in all_scene_rows if not sr.has_beats), None)

    def _first_scene_short(attr):
        return next((sr for sr in all_scene_rows if getattr(sr, attr) < sr.panels), None)

    stages: list[Stage] = []

    st = _first_unscripted()
    stages.append(Stage("scripted", "stories scripted",
                        done=sum(1 for s in story_rows if s.scripted),
                        total=len(story_rows),
                        anchor=(st.anchor if st else None), detail="stories"))

    scripted_stories = [s for s in story_rows if s.scripted]
    br = _first_unbroken()
    stages.append(Stage("scenes", "scenes created",
                        done=sum(1 for s in scripted_stories if s.scenes_created),
                        total=len(scripted_stories),
                        anchor=(br.anchor if br else None), detail="scenes"))

    bl = _first_beatless()
    stages.append(Stage("beats", "beats created",
                        done=sum(1 for sr in all_scene_rows if sr.has_beats),
                        total=len(all_scene_rows),
                        anchor=(bl.anchor if bl else None), detail="beats"))

    for key, label, attr in (("layout", "layout completed", "laid"),
                             ("roughed", "panels roughed", "roughed"),
                             ("inked", "panels inked", "inked")):
        off = _first_scene_short(attr)
        stages.append(Stage(key, label,
                            done=sum(getattr(sr, attr) for sr in all_scene_rows),
                            total=total_panels,
                            anchor=(off.anchor if off else None), detail="beats"))

    # COVERS: a book needs a face — the front at minimum.  Count the slots
    # that exist, but never let "nothing yet" read as "done".
    cover_slots = len(covers) or 1
    cover_roughed = sum(1 for c in covers if roughed(c))
    cover_inked = sum(1 for c in covers if rendered(c))
    stages.append(Stage("covers_roughed", "covers roughed",
                        done=cover_roughed, total=cover_slots,
                        anchor="cover-front", detail=None))
    stages.append(Stage("covers_inked", "covers inked",
                        done=cover_inked, total=cover_slots,
                        anchor="cover-front", detail=None))

    return ProductionBoard(stories=story_rows, stages=stages,
                           cover_slots=cover_slots, cover_roughed=cover_roughed,
                           cover_inked=cover_inked)
