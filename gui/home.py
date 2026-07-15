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
    with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 480px;'):
        ui.label('A NEW PUBLISHING HOUSE').classes('caption-box caption-box-sm')
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
                chosen['create'] = True
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


def view_all_publishers(state: APPState):
    from gui.elements import PagePacker, caption_action, CrudButtonKind as _CK
    storage: GenericStorage = state.storage
    with state.details:
        packer = PagePacker(12)
        with ui.element('div').classes('mosaic-host q-mt-md'), ui.element('div').classes('comic-mosaic w-full'):
            view_all_instances(
                state=state,
                get_image_locator=house_logo,
                get_instances=lambda: all_house_publishers(storage),
                kind="publisher",
                aspect_ratio="1/1",
                packer=packer, variants=[(2, 2)],
                overlap_caption=lambda: caption_action("Publishers", _CK.CREATE,
                    lambda _: found_house_dialog(state), 3))
            packer.finalize()
        
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
            return

        # DOOR 1 — THE BENCH YOU LEFT (dominant): the stashed selection,
        # falling back to the last-touched issue
        resume_sel = getattr(state, 'resume_selection', None)
        series_id = issue = bench_storage = None
        if resume_sel:
            sid = next((it.id for it in resume_sel if it.kind == SelectedKind.SERIES), None)
            iid = next((it.id for it in resume_sel if it.kind == SelectedKind.ISSUE), None)
            if sid:
                series_id = sid
                slug = _reg.house_of_series(sid) if _reg.registered() else None
                bench_storage = _reg.storage_for(slug) if slug else storage
                if iid:
                    issue = bench_storage.read_object(cls=Issue, primary_key={
                        "series_id": sid, "issue_id": iid})
        if issue is None:
            series_id, issue, bench_storage = _last_bench(storage)
            resume_sel = None
        if issue is not None:
            series = bench_storage.read_object(cls=Series, primary_key={"series_id": series_id})
            cover = bench_storage.find_series_image(series_id=series_id)
            try:
                from helpers.ledger import issue_ledger
                led = issue_ledger(bench_storage, series_id, issue.issue_id)
                summary = led.summary()
                first_todo = led.todos[0].text if led.todos else None
            except Exception:
                summary, first_todo = None, None

            def resume(_=None, rs=resume_sel, sid=series_id, iss=issue, ser=series):
                if rs:
                    state.change_selection(new=rs)
                else:
                    state.change_selection(new=[
                        SelectionItem(name="Studio", id=None, kind=SelectedKind.LOBBY),
                        SelectionItem(name=(ser.name if ser else sid), id=sid,
                                      kind=SelectedKind.SERIES),
                        SelectionItem(name=iss.name, id=iss.issue_id, kind=SelectedKind.ISSUE)])
            card = ui.element('div').classes('resume-card cursor-pointer q-mt-md')
            with card:
                if cover and os.path.exists(cover):
                    ui.image(source=cover).classes('resume-card__art').props('fit=cover')
                with ui.column().style('gap: 2px; min-width: 0;'):
                    ui.label('STILL ON THE DRAWING BOARD').classes('caption-box caption-box-sm')
                    ui.label(f"{(series.name if series else series_id).title()} — "
                             f"issue {issue.issue_number}: {issue.name}") \
                        .classes('text-lg font-bold').style('line-height: 1.2;')
                    if summary:
                        badge = summary + (f" — next: {first_todo}" if first_todo else "")
                        ui.label(badge).classes('text-xs text-gray-500 italic')
            card.tooltip('Pick up exactly where you left off')
            card.on('click', resume)

        # DOOR 2 — THE RACK: every house on one strip; each logo a door
        from gui.elements import caption_action, CrudButtonKind as _CK
        caption_action('The publishing houses', _CK.READ,
                       lambda _: state.change_selection(new=[SelectionItem(
                           name='Publishers', id=None, kind=SelectedKind.ALL_PUBLISHERS)]), 3)
        with ui.row().classes('w-full q-mt-xs').style('gap: 10px;'):
            for pub in pubs:
                logo = house_logo(pub)
                with ui.card().classes('soft-card p-2 cursor-pointer') \
                        .style('width: 130px;') as pc:
                    if logo and os.path.exists(logo):
                        ui.image(source=logo).style('height: 72px;').props('fit=contain')
                    ui.label(pub.name.title()).classes('text-xs text-center w-full')
                pc.tooltip(f'Open the {pub.name} house')
                pc.on('click', lambda _, p=pub: state.change_selection(new=[
                    SelectionItem(name='Publishers', id=None, kind=SelectedKind.ALL_PUBLISHERS),
                    SelectionItem(name=p.name, id=p.publisher_id, kind=SelectedKind.PUBLISHER)]))

        # DOOR 3 — THE LIBRARY
        with ui.row().classes('items-center q-mt-md cursor-pointer').style('gap: 8px;') as lib:
            ui.icon('local_library').classes('text-xl')
            ui.label('The Library — every reusable character, setting, prop and '
                     'wardrobe across the houses').classes('text-sm')
        lib.on('click', lambda _: state.change_selection(new=[SelectionItem(
            name='Library', id=None, kind=SelectedKind.LIBRARY)]))


def view_all_series(state: APPState):
    from gui.messaging import new_item_messager
    storage: GenericStorage = state.storage
    with state.details:
        new_item_messager(state, "SERIES", "I would like to create a new comic book series.")

        # THE RESUME CARD: the lobby's front door — the bench you left your
        # pencils on, badged by the one production ledger
        series_id, issue, bench_storage = _last_bench(storage)
        if issue is not None:
            from gui.selection import SelectionItem, SelectedKind
            series = bench_storage.read_object(cls=Series, primary_key={"series_id": series_id})
            cover = bench_storage.find_series_image(series_id=series_id)
            try:
                from helpers.ledger import issue_ledger
                summary = issue_ledger(bench_storage, series_id, issue.issue_id).summary()
            except Exception:
                summary = None

            def resume():
                state.change_selection(new=[
                    SelectionItem(name="Series", id=None, kind=SelectedKind.ALL_SERIES),
                    SelectionItem(name=(series.name if series else series_id),
                                  id=series_id, kind=SelectedKind.SERIES),
                    SelectionItem(name=issue.name, id=issue.issue_id, kind=SelectedKind.ISSUE)])
            card = ui.element('div').classes('resume-card cursor-pointer')
            with card:
                if cover and os.path.exists(cover):
                    ui.image(source=cover).classes('resume-card__art').props('fit=cover')
                with ui.column().style('gap: 2px; min-width: 0;'):
                    ui.label('STILL ON THE DRAWING BOARD').classes('caption-box caption-box-sm')
                    ui.label(f"{(series.name if series else series_id).title()} — "
                             f"issue {issue.issue_number}: {issue.name}") \
                        .classes('text-lg font-bold').style('line-height: 1.2;')
                    if summary:
                        ui.label(summary).classes('text-xs text-gray-500 italic')
            card.tooltip('Open the book where you left it')
            card.on('click', lambda _: resume())

        from gui.elements import ruled_page
        from storage import registry as _reg

        _rooted = (str(getattr(storage, 'base_path', '')) == _reg.DATA_DIR
                   and _reg.registered())

        def _all_series():
            # THE LOBBY SEES EVERY HOUSE: the wall unions the mounted repos
            if not _rooted:
                return storage.read_all_objects(Series, order_by="name")
            out = []
            for _slug, st in _reg.mounted_storages():
                out.extend(st.read_all_objects(Series))
            return sorted(out, key=lambda x: x.name)

        def _series_face(x):
            slug = _reg.house_of_series(x.series_id) if _rooted else None
            st = _reg.storage_for(slug) if slug else storage
            return st.find_series_image(series_id=x.series_id)

        with ruled_page() as packer:
            view_all_instances(
                state=state,
                get_image_locator=_series_face,
                get_instances=_all_series,
                kind="series",
                aspect_ratio="16/27",
                packer=packer, variants=[(2, 3), (8/3, 4), (4, 6)])