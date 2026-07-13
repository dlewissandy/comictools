"""ONE PRODUCTION LEDGER: the single truth about what stands between an
issue and a bound book.

Every surface that speaks about production — the colophon's small print,
the masthead badge, the Editor's opening line, the reading room's missing
list, the preflight tool — reads THIS ledger.  None keeps its own count,
so they can never disagree.

Every line knows its door: the `anchor` is a data-banchor in the open
book (and `detail` the dial stop that shows it), so a rendering can walk
the reader straight to the first thing a line counts.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class LedgerLine:
    key: str                     # 'script' | 'scenes' | 'panels' | 'letters' | 'covers' | 'inserts' | 'placement'
    ok: bool
    text: str                    # the line as the colophon prints it
    count: int = 0               # how many things this line still counts
    items: list[str] = field(default_factory=list)   # per-offender phrases (agent-facing detail)
    anchor: str | None = None    # data-banchor of the first offender in the open book
    detail: str | None = None    # the dial stop that shows it ('stories'|'scenes'|'beats')


@dataclass
class Ledger:
    lines: list[LedgerLine]

    @property
    def todos(self) -> list[LedgerLine]:
        return [line for line in self.lines if not line.ok]

    @property
    def complete(self) -> bool:
        return not self.todos

    def summary(self) -> str:
        """The badge line: press-ready, or the shortest true account."""
        if self.complete:
            return 'press-ready'
        n = sum(max(line.count, 1) for line in self.todos)
        return f"{n} thing{'s' if n != 1 else ''} before press"


def issue_ledger(storage, series_id: str, issue_id: str) -> Ledger:
    """Read the whole issue once and account for everything that must be
    true before the book binds clean."""
    from schema import Issue, Story, SceneModel, Panel, Cover, Insert
    from helpers.compositor import is_placeholder

    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
    pk = {"series_id": series_id, "issue_id": issue_id}
    stories = storage.read_all_objects(Story, primary_key=pk)
    scenes = storage.read_all_objects(SceneModel, primary_key=pk, order_by="scene_number")
    panels_by_scene = {sc.scene_id: storage.read_all_objects(
        Panel, primary_key={**pk, "scene_id": sc.scene_id}, order_by="panel_number")
        for sc in scenes}
    covers = storage.read_all_objects(Cover, primary_key=pk)
    cover_at = {}
    for c in covers:
        cover_at.setdefault(c.location.value, c)
    inserts = sorted(storage.read_all_objects(Insert, primary_key=pk),
                     key=lambda i: (i.after_scene_number, i.insert_id))

    def rendered(obj) -> bool:
        return bool(obj.image and os.path.exists(obj.image))

    lines: list[LedgerLine] = []

    # THE SCRIPT: a book starts as words
    has_script = bool((issue is not None and issue.story) or stories or scenes)
    lines.append(LedgerLine(
        key='script', ok=has_script,
        text='the script opens the book' if has_script
        else 'no script yet — paste a story and it becomes the book',
        count=0 if has_script else 1, detail='stories'))

    # THE UNBROKEN SCRIPT: words with no scenes yet are the book's next
    # debt — a 1200-word story and zero scenes is NOT one thing before
    # press, it is the whole book waiting
    if has_script and not scenes:
        wc = len(((issue.story if issue else None) or "").split()) + sum(
            len((st.text or "").split()) for st in stories)
        lines.append(LedgerLine(
            key='breakdown', ok=False,
            text=f"the script ({wc} words) waits to be broken into scenes",
            count=1,
            items=["break the script into scenes (the Editor does this from the book)"],
            anchor=(f'story-{stories[0].story_id}' if stories else 'story-script'),
            detail='stories'))

    # SCRIPT DRIFT: the script changed AFTER its breakdown — the scenes
    # quietly draw the old story until the author re-breaks
    if scenes and getattr(issue, 'broken_script_sha', None):
        import hashlib as _hl
        _txt = ((issue.story if issue else None) or '') + '|' + '|'.join(
            (st.text or '') for st in stories)
        if _hl.sha1(_txt.encode()).hexdigest() != issue.broken_script_sha:
            lines.append(LedgerLine(
                key='drift', ok=False,
                text="the script changed after its breakdown — the scenes still draw the old story",
                count=1,
                items=["re-break the script (the Editor updates the scenes in place)"],
                anchor=(f'story-{stories[0].story_id}' if stories else 'story-script'),
                detail='stories'))

    # THE SCENES: every scene broken down into panels
    bare = [sc for sc in scenes if not panels_by_scene[sc.scene_id]]
    if scenes:
        lines.append(LedgerLine(
            key='scenes', ok=not bare,
            text='every scene broken into panels' if not bare
            else f"{len(bare)} scene{'s' if len(bare) != 1 else ''} still to break down",
            count=len(bare),
            items=[f"scene '{sc.name}' has no panels yet" for sc in bare],
            anchor=f'scene-{bare[0].scene_id}' if bare else None, detail='beats'))

    # THE PANELS: every panel inked
    all_panels = [p for sc in scenes for p in panels_by_scene[sc.scene_id]]
    if all_panels:
        unrendered = [p for p in all_panels if not rendered(p)]
        inked = len(all_panels) - len(unrendered)
        lines.append(LedgerLine(
            key='panels', ok=not unrendered,
            text=f'{inked} of {len(all_panels)} panels inked',
            count=len(unrendered),
            items=[f"panel {p.panel_number} ('{p.name}') is not inked" for p in unrendered],
            anchor=f'panel-{unrendered[0].panel_id}' if unrendered else None, detail='beats'))

    # THE LETTERS: scaffold text must never reach print
    holders: list[tuple[str, str]] = []      # (phrase, anchor)
    scene_of = {p.panel_id: sc for sc in scenes for p in panels_by_scene[sc.scene_id]}
    for p in all_panels:
        texts = [d.text for d in (p.dialogue or [])] + [n.text for n in (p.narration or [])]
        if any(is_placeholder(t) for t in texts):
            holders.append((f"panel {p.panel_number} of scene '{scene_of[p.panel_id].name}' "
                            f"still has placeholder lettering", f'panel-{p.panel_id}'))
    for c in covers:
        texts = [d.text for d in (getattr(c, 'dialogue', None) or [])] + \
                [n.text for n in (getattr(c, 'narration', None) or [])]
        if any(is_placeholder(t) for t in texts):
            holders.append((f"the {c.location.value} cover still has placeholder lettering",
                            f'cover-{c.location.value}'))
    if holders:
        lines.append(LedgerLine(
            key='letters', ok=False,
            text=f"placeholder lettering on {len(holders)} board{'s' if len(holders) != 1 else ''} "
                 f"— write the real words",
            count=len(holders), items=[h[0] for h in holders],
            anchor=holders[0][1], detail='beats'))

    # THE COVERS: a book needs a face
    front = cover_at.get('front')
    front_ok = front is not None and rendered(front)
    lines.append(LedgerLine(
        key='covers', ok=front_ok,
        text='the front cover is inked' if front_ok
        else ('the front cover is a bare board' if front is not None else 'no front cover yet'),
        count=0 if front_ok else 1,
        items=[] if front_ok else ['the front cover is not inked'],
        anchor='cover-front'))

    # THE INSERTS: a typeset insert prints as gray words, not art
    if inserts:
        unrendered_ins = [i for i in inserts if not rendered(i)]
        lines.append(LedgerLine(
            key='inserts', ok=not unrendered_ins,
            text=f"all {len(inserts)} insert{'s' if len(inserts) != 1 else ''} rendered"
            if not unrendered_ins
            else f"{len(unrendered_ins)} insert{'s' if len(unrendered_ins) != 1 else ''} "
                 f"still to render — stand-in pages print till then",
            count=len(unrendered_ins),
            items=[f"insert '{i.name}' ({i.kind}) is not rendered" for i in unrendered_ins],
            anchor=f'insert-{unrendered_ins[0].insert_id}' if unrendered_ins else None,
            detail='beats'))   # scene-anchored inserts only render at scenes/panels

    # THE PAGES: every panel placed on a page
    if all_panels:
        from helpers.binder import page_coverage
        _has, _placed, unplaced, dangling = page_coverage(storage, series_id, issue_id)
        placed_ok = not unplaced and not dangling
        lines.append(LedgerLine(
            key='placement', ok=placed_ok,
            text='every panel placed on its page' if placed_ok
            else f"{len(unplaced)} panel{'s' if len(unplaced) != 1 else ''} loose "
                 f"— the pages need restitching" if unplaced
            else 'the pages reference panels that no longer exist — restitch',
            count=len(unplaced) or len(dangling), detail='beats'))

    return Ledger(lines=lines)
