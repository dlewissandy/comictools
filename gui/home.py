import os
from nicegui import ui
from gui.elements import view_all_instances
from gui.state import APPState
from schema.series import Series
from schema.publisher import Publisher
from schema.style.comic import ComicStyle
from storage.generic import GenericStorage
        

def all_house_publishers(storage) -> list[Publisher]:
    """Every publisher on the wall — one per registered house (each house
    is a git repo holding exactly one publisher, mounted at data/<slug>).
    Falls back to the handed storage when no registry exists (legacy
    single-directory layout)."""
    from storage import registry
    if str(getattr(storage, 'base_path', '')) != registry.DATA_DIR or not registry.registered():
        return storage.read_all_objects(Publisher)
    out = []
    for _slug, st in registry.mounted_storages():
        out.extend(st.read_all_objects(Publisher))
    return out


def house_logo(pub: Publisher):
    """The publisher's logo, already mount-resolved: house storages
    translate 'data/…' locators to 'data/<slug>/…' on read."""
    return pub.image


async def choose_folder() -> str | None:
    """A real file-system dialog on the studio's own machine (the app is
    local-first — server and author share the desk).  None on cancel or
    when no native dialog is available."""
    import asyncio
    try:
        proc = await asyncio.create_subprocess_exec(
            'osascript', '-e',
            'POSIX path of (choose folder with prompt '
            '"Where does the publishing house live (or get founded)?")',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _err = await proc.communicate()
        if proc.returncode != 0:
            return None
        return out.decode().strip().rstrip('/')
    except (OSError, FileNotFoundError):
        return None


def found_house_dialog(state: APPState):
    """FOUND (or ADOPT) A HOUSE: pick a folder on disk.  A folder that
    already has a house's structure joins the rack as it is; anything else
    gets a fresh repo founded in it with the studio's default styles."""
    from storage import registry
    chosen = {'dir': None, 'existing': None}
    from gui.elements import studio_dialog
    with studio_dialog('A NEW PUBLISHING HOUSE', min_w=480) as dlg:
        ui.label('Every house is its own git repository.  Pick where it lives — '
                 'an existing house joins the rack as it is.') \
            .classes('text-sm q-mt-sm')
        name = ui.input('The house’s name', placeholder='e.g. Midnight Owl Press') \
            .classes('w-full q-mt-sm').props('outlined dense')
        status = ui.label('No folder chosen yet.').classes('text-xs text-gray-500 q-mt-xs')

        def _describe():
            d = chosen['dir']
            if not d:
                return
            if chosen['existing']:
                status.text = (f"{d} already holds “{chosen['existing']}” — "
                               f"it joins the rack exactly as it is.")
                go_btn.set_text('Adopt this house')
            elif os.path.isdir(d) and os.listdir(d):
                import re
                slug = re.sub(r'[^a-z0-9]+', '-', (name.value or 'new house').lower()).strip('-')
                status.text = (f"{d} isn’t a comics repo yet (and isn’t empty) — "
                               f"initialize one at {os.path.join(d, slug + '-comics')}?")
                go_btn.set_text('Initialize the repo there')
            else:
                status.text = (f"{d} isn’t a comics repo yet — initialize it as one, "
                               f"with the studio's default styles?")
                go_btn.set_text('Initialize & found here')

        async def pick(_=None):
            d = await choose_folder()
            if d is None:
                if chosen['dir'] is None:
                    status.text = ('No native dialog available — type the folder path here.')
                    manual.set_visibility(True)
                return
            chosen['dir'] = d
            chosen['existing'] = registry.looks_like_house(d)
            _describe()

        manual = ui.input('Folder path', placeholder='~/git') \
            .classes('w-full').props('outlined dense')
        manual.set_visibility(False)

        def manual_changed():
            d = os.path.expanduser(manual.value or '')
            if os.path.isdir(d):
                chosen['dir'] = d.rstrip('/')
                chosen['existing'] = registry.looks_like_house(chosen['dir'])
                _describe()
            elif d.strip():
                # a path that doesn't exist yet is where the house WILL
                # live — take it, say so, and create it at founding
                chosen['dir'] = d.rstrip('/')
                chosen['existing'] = False
                _describe()
                status.set_text(f"{chosen['dir']} doesn't exist yet — "
                                f"it will be created when you found the house.")
        manual.on('change', lambda _: manual_changed())
        name.on('change', lambda _: _describe())

        with ui.row().classes('w-full items-center q-mt-sm').style('gap: 8px;'):
            ui.button('Choose a folder…', icon='folder_open').props('outline dense no-caps') \
                .on('click', pick)
            ui.space()

            def go():
                d = chosen['dir']
                if not d:
                    ui.notify('Pick a folder first.', type='warning')
                    return
                if chosen['existing']:
                    registry.register(d)
                    dlg.close()
                    ui.notify(f"“{chosen['existing']}” joined the rack — it's on the wall now.",
                              type='positive')
                    state.refresh_details()
                    return
                nm = (name.value or '').strip()
                if not nm:
                    ui.notify('Give the house a name.', type='warning')
                    return
                import re
                # a not-yet-existing folder founds directly there (created
                # by the founding); an occupied one gets a child repo
                target = d if (not os.path.isdir(d) or not os.listdir(d)) else os.path.join(
                    d, re.sub(r'[^a-z0-9]+', '-', nm.lower()).strip('-') + '-comics')
                try:
                    slug = registry.found_house(nm, target)
                except Exception as ex:
                    ui.notify(f'Could not found the house: {ex}', type='warning')
                    return
                dlg.close()
                from gui.light_table import table_receipt
                table_receipt(state, f"\U0001F3DB founded **{nm}** at `{target}` — "
                                     f"a fresh repository with the studio's default styles",
                              bench='the publishers wall')
                state.refresh_details()
            go_btn = ui.button('Found the house', icon='gavel').props('unelevated dense no-caps')
            go_btn.on('click', lambda _: go())
    dlg.open()


def _last_bench(storage):
    """(series, issue, storage) most recently touched anywhere under any
    mounted house — the bench the author left their pencils on."""
    from storage import registry
    if str(getattr(storage, 'base_path', '')) != registry.DATA_DIR or not registry.registered():
        sid, issue, _when = _house_bench(storage)
        return sid, issue, storage
    best = (None, None, storage)
    best_when = 0.0
    for _slug, st in registry.mounted_storages():
        sid, issue, when = _house_bench(st)
        if issue is not None and when > best_when:
            best, best_when = (sid, issue, st), when
    return best


def _house_bench(storage):
    """(series_id, issue, mtime) of one house's freshest bench."""
    from schema import Issue
    base = str(storage.base_path)
    newest, when = None, 0.0
    for sdir in (os.scandir(os.path.join(base, 'series'))
                 if os.path.isdir(os.path.join(base, 'series')) else []):
        issues_dir = os.path.join(sdir.path, 'issues')
        if not os.path.isdir(issues_dir):
            continue
        for idir in os.scandir(issues_dir):
            if not idir.is_dir():
                continue
            m = 0.0
            for root, _dirs, files in os.walk(idir.path):
                for f in files:
                    try:
                        m = max(m, os.path.getmtime(os.path.join(root, f)))
                    except OSError:
                        pass
            if m > when:
                when, newest = m, (sdir.name, idir.name)
    if newest is None:
        return None, None, 0.0
    issue = storage.read_object(cls=Issue, primary_key={"series_id": newest[0],
                                                        "issue_id": newest[1]})
    return (newest[0], issue, when) if issue else (None, None, 0.0)


def view_lobby(state: APPState):
    """THE FRONT DOOR: one screen that says where you are and where to go —
    the bench you left (dominant), the rack of houses, the Library."""
    from storage import registry as _reg
    from gui.selection import SelectionItem, SelectedKind
    from schema import Issue
    storage: GenericStorage = state.storage
    with state.details:
        ui.label('COMIC STUDIO').classes('comic-title')

        pubs = all_house_publishers(storage)
        if not pubs:
            # A BRAND-NEW STUDIO: every comic starts with a conversation
            ui.label('Every comic starts with a conversation.') \
                .classes('caption-box q-mt-md')
            ui.label('Tell the Editor a story below — but first the studio '
                     'needs a publishing house to work in.') \
                .classes('text-sm text-gray-600 q-mt-sm')
            with ui.row().classes('q-mt-md').style('gap: 12px;'):
                ui.button('Found your publishing house', icon='home_work') \
                    .props('unelevated no-caps size=lg') \
                    .on('click', lambda _: found_house_dialog(state))
                ui.button('Adopt the demo house', icon='auto_stories') \
                    .props('outline no-caps size=lg') \
                    .tooltip('Foglamp Press and its one small series — a living '
                             'example to walk through and make your own') \
                    .on('click', lambda _: adopt_demo_house(state))
            return

        # THE STUDIO WALL: the whole catalog at one glance — every house's
        # logo, every series' masthead, every issue's face; each tile a door,
        # each row ending in a ghost door; the issue you left wears the
        # drawing-board ribbon right on its tile.
        from schema import Series as _Series
        resume_sel = getattr(state, 'resume_selection', None)
        live_issue = None
        if resume_sel:
            live_issue = next((it.id for it in resume_sel
                               if it.kind == SelectedKind.ISSUE), None)
        if live_issue is None:
            _sid, _iss, _bst = _last_bench(storage)
            live_issue = _iss.issue_id if _iss is not None else None

        def _house_rows():
            rows = []
            for pub in pubs:
                slug = _reg.house_of_publisher(pub.publisher_id) if _reg.registered() else None
                st = _reg.storage_for(slug) if slug else storage
                series = sorted([x for x in st.read_all_objects(_Series)
                                 if x.publisher_id == pub.publisher_id],
                                key=lambda x: x.name)
                rows.append((pub, st, series))
            return rows

        def _goto(sel_items):
            state.change_selection(new=[SelectionItem(name='Studio', id=None,
                                                      kind=SelectedKind.LOBBY)] + sel_items)

        def _open_mark(st, scope_id, board_kind, name, trail, style_id=None,
                       aspect=None):
            # ONE TOOL, MANY USES: every mark edits on the lightboard —
            # render from text (the brief), from image (drop a take), or
            # from rough (compose layers).  The click IS "open the editor".
            from schema import ArtBoard
            from schema.enums import FrameLayout
            bid = f"{board_kind}-{style_id}" if style_id else board_kind
            board = st.read_object(cls=ArtBoard, primary_key={
                "scope_id": scope_id, "board_id": bid})
            if board is None:
                board = ArtBoard(board_id=bid, scope_id=scope_id,
                                 board_kind=board_kind, name=name,
                                 style_id=style_id,
                                 aspect=aspect or (FrameLayout.SQUARE if board_kind == 'logo'
                                                   else FrameLayout.LANDSCAPE))
                st.create_object(data=board, overwrite=True)
            _goto([*trail, SelectionItem(name=name, id=bid, kind=SelectedKind.ARTBOARD)])

        with ui.column().classes('w-full q-mt-md studio-wall').style('gap: 14px;'):
            for pub, st, series_list in _house_rows():
                with ui.row().classes('w-full flex-nowrap items-start').style('gap: 10px;'):
                    # THE HOUSE CELL: the logo, spanning its series rows
                    logo = house_logo(pub)
                    with ui.card().classes('soft-card p-2 cursor-pointer relative') \
                            .style('width: 128px; flex-shrink: 0;') as hc:
                        if logo and os.path.exists(logo):
                            ui.image(source=logo).style('height: 84px;').props('fit=contain')
                        else:
                            # NO MARK YET: the wall itself offers the brush
                            def _ink_logo(_=None, p=pub, st=st):
                                _open_mark(st, p.publisher_id, 'logo',
                                           f"{p.name} logo",
                                           [SelectionItem(name=p.name, id=p.publisher_id,
                                                          kind=SelectedKind.PUBLISHER)])
                            ui.button(icon='brush').props('flat round dense size=sm') \
                                .classes('absolute top-1 right-1 z-10') \
                                .tooltip('No logo yet — describe one and the house gets its mark') \
                                .on('click.stop', _ink_logo)
                        ui.label(pub.name.title()).classes('text-xs text-center w-full text-bold')

                        # THE SYNC GLYPH: every house is a git repo — one
                        # transparent button commits (with a slate message
                        # naming what was inked), pulls and pushes.  A badge
                        # counts what's waiting.
                        _slug_g = _reg.house_of_publisher(pub.publisher_id) if _reg.registered() else None
                        _house_g = next((h for h in _reg.registered()
                                         if h['slug'] == _slug_g), None) if _slug_g else None
                        if _house_g is not None:
                            from helpers.house_git import repo_state
                            _gs = repo_state(_house_g['path'])
                            if _gs is not None:
                                _waiting = _gs['dirty'] + _gs['ahead'] + _gs['behind']
                                _tip = (f"Sync the house — commit, pull & push "
                                        f"({_gs['dirty']} changed"
                                        + (f", {_gs['ahead']} to push" if _gs['ahead'] else "")
                                        + (f", {_gs['behind']} to pull" if _gs['behind'] else "")
                                        + ")") if _waiting else \
                                    'Sync the house — everything is committed' \
                                    + (' and pushed' if _gs['remote'] else ' (no remote yet)')
                                _sbtn = ui.button(icon='sync') \
                                    .props('flat round dense size=xs') \
                                    .classes('absolute bottom-1 right-1 z-10 '
                                             'bg-white/70 dark:bg-black/50') \
                                    .tooltip(_tip)
                                if _waiting:
                                    with _sbtn:
                                        ui.badge(str(_waiting), color='orange') \
                                            .props('floating rounded')

                                async def _sync_house(_=None, p=_house_g['path'],
                                                      name=pub.name, btn=_sbtn):
                                    import asyncio
                                    from helpers.house_git import sync_house
                                    btn.props('loading')
                                    try:
                                        receipts = await asyncio.to_thread(sync_house, p)
                                    finally:
                                        btn.props(remove='loading')
                                    from gui.thread import thread_aside
                                    for r in receipts:
                                        thread_aside(state, f"{r} · {name}")
                                    state.refresh_details()
                                _sbtn.on('click.stop', _sync_house)
                    hc.tooltip(f"The {pub.name} house — its room holds the series wall and the style rack")
                    hc.on('click', lambda _, p=pub: _goto([
                        SelectionItem(name=p.name, id=p.publisher_id, kind=SelectedKind.PUBLISHER)]))

                    with ui.column().classes('w-full').style('gap: 10px; min-width: 0;'):
                        for ser in series_list:
                            with ui.row().classes('w-full flex-nowrap items-center').style('gap: 8px;'):
                                # THE SERIES CELL: the masthead wordmark
                                mast = next((i for i in (ser.title_images or {}).values()
                                             if i and os.path.exists(i)), None)
                                with ui.card().classes('soft-card p-1 cursor-pointer relative') \
                                        .style('width: 168px; flex-shrink: 0;') as sc:
                                    # THE MASTHEAD CELL prints at 3x2, like a plate
                                    if mast:
                                        ui.image(source=mast) \
                                            .style('width: 100%; aspect-ratio: 3/2;') \
                                            .props('fit=contain')
                                    else:
                                        def _ink_mast(_=None, p=pub, x=ser, st=st):
                                            _sid = getattr(x, 'style_id', None) or 'vintage-four-color'
                                            _open_mark(st, x.series_id, 'masthead',
                                                       f"{x.name} masthead",
                                                       [SelectionItem(name=p.name, id=p.publisher_id,
                                                                      kind=SelectedKind.PUBLISHER),
                                                        SelectionItem(name=x.name, id=x.series_id,
                                                                      kind=SelectedKind.SERIES)],
                                                       style_id=_sid)
                                        ui.button(icon='brush').props('flat round dense size=xs') \
                                            .classes('absolute top-1 right-1 z-10') \
                                            .tooltip('No masthead yet — describe the lettering') \
                                            .on('click.stop', _ink_mast)
                                        ui.label(ser.name.upper()).classes('comic-title-sm') \
                                            .style('font-size: 1.05rem; line-height: 1.15; '
                                                   'width: 100%; aspect-ratio: 3/2; display: flex; '
                                                   'align-items: center; justify-content: center; '
                                                   'text-align: center;')
                                sc.tooltip(f'{ser.name} — the series room')
                                sc.on('click', lambda _, p=pub, x=ser: _goto([
                                    SelectionItem(name=p.name, id=p.publisher_id, kind=SelectedKind.PUBLISHER),
                                    SelectionItem(name=x.name, id=x.series_id, kind=SelectedKind.SERIES)]))

                                # THE ISSUE TILES
                                issues = sorted(st.read_all_objects(Issue, {"series_id": ser.series_id}),
                                                key=lambda i: i.issue_number or 0)
                                for iss in issues:
                                    face = st.find_issue_image(series_id=ser.series_id,
                                                               issue_id=iss.issue_id)
                                    with ui.card().classes('soft-card p-1 cursor-pointer relative') \
                                            .style('width: 74px; flex-shrink: 0;') as ic:
                                        if face and os.path.exists(face):
                                            ui.image(source=face).style('height: 96px;').props('fit=cover')
                                        else:
                                            ui.label(f"№ {iss.issue_number}").classes('text-xs text-center w-full') \
                                                .style('height: 96px; display: flex; align-items: center; justify-content: center;')
                                        # THE BANNER SPEAKS PUBLICATION:
                                        # a dated issue wears PUBLISHED —
                                        # the wall is a catalog, not a desk
                                        if iss.publication_date:
                                            ui.label('PUBLISHED').classes('board-ribbon board-ribbon--pub')
                                    _tip = f"Issue {iss.issue_number}: {iss.name}"
                                    if iss.publication_date:
                                        _tip += f" — published {iss.publication_date}"
                                    elif iss.issue_id == live_issue:
                                        try:
                                            from helpers.ledger import issue_ledger
                                            _tip += " — on the board: " + issue_ledger(
                                                st, ser.series_id, iss.issue_id).summary()
                                        except Exception:
                                            pass
                                    ic.tooltip(_tip)
                                    ic.on('click', lambda _, p=pub, x=ser, i=iss: _goto([
                                        SelectionItem(name=p.name, id=p.publisher_id, kind=SelectedKind.PUBLISHER),
                                        SelectionItem(name=x.name, id=x.series_id, kind=SelectedKind.SERIES),
                                        SelectionItem(name=i.name, id=i.issue_id, kind=SelectedKind.ISSUE)]))

                                # ghost door: the next issue
                                gi = ui.card().classes('soft-card p-1 cursor-pointer ghost-tile') \
                                    .style('width: 74px; flex-shrink: 0;')
                                with gi:
                                    ui.label('+').classes('text-xl text-center w-full') \
                                        .style('height: 96px; display: flex; align-items: center; justify-content: center; opacity: .45;')
                                gi.tooltip(f'Start the next issue of {ser.name}')
                                gi.on('click', lambda _, x=ser: (
                                    state.user_input.__setattr__('value',
                                        f"Create the next issue of {x.name}: "),
                                    state.user_input.run_method('focus')))
                        # every house column ends in the new-series door
                        gs = ui.card().classes('soft-card p-1 cursor-pointer ghost-tile') \
                            .style('width: 168px;')
                        with gs:
                            ui.label('+ new series' if series_list else '+ first series') \
                                .classes('text-sm text-center w-full').style('opacity: .55;')
                        gs.tooltip(f'Start a new series at {pub.name}')
                        gs.on('click', lambda _, p=pub: (
                            state.user_input.__setattr__('value',
                                f"Create a new series for {p.name}: "),
                            state.user_input.run_method('focus')))

            # the wall closes with the founding door
            gh = ui.card().classes('soft-card p-2 cursor-pointer ghost-tile').style('width: 128px;')
            with gh:
                ui.label('+ found a house').classes('text-xs text-center w-full').style('opacity: .55;')
            gh.on('click', lambda _: found_house_dialog(state))


def adopt_demo_house(state):
    """THE DEMO HOUSE: Foglamp Press — a lighthouse keeper's one-sheet
    newspaper, told as a small comic.  Original work, founded like any
    real house (git repo, default styles), yours to walk through and
    remake.  STAY PUT: the wall repaints; nothing redirects."""
    import os as _os
    from storage import registry as _reg
    from schema import Series, Issue

    target = _os.path.expanduser("~/git/foglamp-press-comics")
    if _os.path.isdir(_os.path.join(target, "publishers")):
        ui.notify("The demo house already stands at ~/git/foglamp-press-comics — "
                  "it hangs on the wall.", type="info")
        return
    try:
        slug = _reg.found_house("Foglamp Press", target)
    except Exception as ex:
        ui.notify(f"Couldn't found the demo house: {ex}", type="warning")
        return
    st = _reg.storage_for(slug)
    from schema import Publisher as _Pub
    pubs = st.read_all_objects(_Pub)
    if pubs:
        pub = pubs[0]
        pub.description = ("Foglamp Press prints small, warm stories from the "
                           "edge of the map — comics about keepers, harbors and "
                           "the news that only matters when the fog rolls in.")
        pub.logo = ("A round lamp lens glowing through stylized fog, ringed by "
                    "the words FOGLAMP PRESS in sturdy maritime lettering — "
                    "two colors, bold outline, readable at a stamp's size.")
        st.update_object(pub)
        pub_id = pub.publisher_id
    else:
        pub_id = slug
    series = Series(series_id="the-lighthouse-post", name="The Lighthouse Post",
                    description=("Edda Lumen keeps the last staffed lighthouse on "
                                 "the Gannet Shoals — and prints the town's only "
                                 "newspaper on the lamp-room's old press.  One "
                                 "sheet, once a week, and somehow always exactly "
                                 "the news the fog is about to make matter."),
                    publisher_id=pub_id)
    st.create_object(data=series, overwrite=True)
    issue = Issue(issue_id="the-fog-edition", name="The Fog Edition",
                  series_id="the-lighthouse-post",
                  style_id="vintage-four-color", issue_number=1,
                  story=("Edda Lumen climbs the lamp room before dawn and finds the "
                         "great lens cold — the first time in forty years.  She prints "
                         "a single headline: LIGHT OUT, FOG DUE, READ FAST.  The town "
                         "ignores the paper, as always, until the fog arrives at noon "
                         "like a dropped curtain.  Deliveries stop.  The ferry idles.  "
                         "One by one, townsfolk appear at the lighthouse door holding "
                         "the paper, asking what page two says.  There is no page two — "
                         "so Edda hands each visitor a lamp part and a job.  By dusk the "
                         "lens burns again, lit by everyone who finally read the news.  "
                         "The next edition runs two pages; nobody skips it."),
                  publication_date=None, price=None, writer="Edda Lumen (as told to the keeper's cat)",
                  artist=None, colorist=None, creative_minds=None)
    st.create_object(data=issue, overwrite=True)
    from gui.thread import thread_aside, thread_reply
    thread_aside(state, "🏮 adopted **Foglamp Press** — the demo house stands at "
                        "~/git/foglamp-press-comics", bench="the front desk")
    thread_reply(state, "Foglamp Press hangs on the wall now — one small series, "
                        "one foggy issue, all yours.  Open **The Fog Edition** and "
                        "we can break its script into scenes together, or start "
                        "your own house alongside it.")
    state.refresh_details()
    try:
        state.render_your_turn()
    except Exception:
        pass
