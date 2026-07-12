import os
from nicegui import ui
from gui.elements import view_all_instances
from gui.state import APPState
from schema.series import Series
from schema.publisher import Publisher
from schema.style.comic import ComicStyle
from storage.generic import GenericStorage
        

def view_all_styles(state: APPState):
    from gui.messaging import new_item_messager
    storage: GenericStorage = state.storage
    with state.details:
        new_item_messager(state, "STYLES", "I would like to create a new comic book style.")
        from gui.elements import ruled_page
        with ruled_page() as packer:
            view_all_instances(
                state=state,
                get_image_locator=lambda style: style.image.get('art', None) if style.image else None,
                get_instances=lambda: storage.read_all_objects(ComicStyle),
                kind="style",
                aspect_ratio="1/1",
                packer=packer, variants=[(3, 3)],
                # a style's art is abstract — its NAME must be readable
                # without hovering
                card_overlay=lambda style: ui.label(style.name.title())
                    .classes('caption-box caption-box-sm')
                    .style('position: absolute; bottom: 6px; left: 6px; z-index: 6;'))
        
def view_all_publishers(state: APPState):
    from gui.elements import PagePacker, caption_action, CrudButtonKind as _CK
    from gui.messaging import post_user_message
    from storage import registry
    storage: GenericStorage = state.storage
    houses = registry.registered()
    if houses:
        # THE RACK OF HOUSES: every publisher is its own git repo; the
        # studio opens one house at a time (./data points at it)
        open_slug = registry.open_slug()
        with state.details:
            with ui.row().classes('items-center q-mt-md').style('gap: 8px;'):
                ui.label('PUBLISHING HOUSES').classes('caption-box')
                ui.label('each house is its own repository — open one and the '
                         'whole studio works inside it') \
                    .classes('text-xs text-gray-500 italic')
            with ui.row().classes('q-mt-md').style('gap: 14px; flex-wrap: wrap;'):
                for h in houses:
                    from storage.local import LocalStorage as _LS
                    pubs = _LS(base_path=h['path']).read_all_objects(Publisher)
                    pub = pubs[0] if pubs else None
                    is_open = h['slug'] == open_slug
                    card = ui.element('div').classes(
                        'resume-card' + ('' if is_open else ' cursor-pointer'))
                    with card:
                        with ui.column().style('gap: 2px; min-width: 0;'):
                            ui.label((pub.name if pub else h['slug']).upper()) \
                                .classes('caption-box caption-box-sm')
                            if pub is not None and pub.description:
                                ui.label(pub.description[:90]).classes('text-xs') \
                                    .style('opacity: .8;')
                            ui.label(h['path']).classes('text-xs text-gray-500') \
                                .style('font-family: monospace;')
                            if is_open:
                                ui.label('OPEN — the studio is working in this house') \
                                    .classes('text-xs text-bold')
                    if is_open:
                        card.tooltip('This house is open')
                    else:
                        def open_house(slug=h['slug'], name=(pub.name if pub else h['slug'])):
                            if registry.set_open(slug):
                                # a selection from the OLD house resolves to
                                # nothing here — land in the new house's lobby
                                try:
                                    import json as _json
                                    from gui.state import STATE_FILEPATH
                                    try:
                                        data = _json.load(open(STATE_FILEPATH))
                                    except Exception:
                                        data = {}
                                    data['selection'] = [{"kind": "all-series",
                                                          "name": "Series", "id": None}]
                                    _json.dump(data, open(STATE_FILEPATH, 'w'))
                                except Exception:
                                    pass
                                ui.notify(f'Opening {name} — the studio moves houses…',
                                          type='info')
                                ui.run_javascript("setTimeout(() => location.href = '/', 600);")
                            else:
                                ui.notify('Could not open that house.', type='warning')
                        card.tooltip('Open this house — the studio works in one at a time')
                        card.on('click', lambda _, s=h['slug'],
                                n=(pub.name if pub else h['slug']): open_house(s, n))
        return
    with state.details:
        packer = PagePacker(12)
        with ui.element('div').classes('mosaic-host q-mt-md'), ui.element('div').classes('comic-mosaic w-full'):
            view_all_instances(
                state=state,
                get_image_locator=lambda publisher: publisher.image,
                get_instances=lambda: storage.read_all_objects(Publisher),
                kind="publisher",
                aspect_ratio="1/1",
                packer=packer, variants=[(2, 2)],
                overlap_caption=lambda: caption_action("Publishers", _CK.CREATE,
                    lambda _: post_user_message(state, "I would like to create a new comic book publisher."), 3))
            packer.finalize()
        
def _last_bench(storage):
    """(series, issue) most recently touched anywhere under its issue dir —
    the bench the author left their pencils on."""
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
        return None, None
    issue = storage.read_object(cls=Issue, primary_key={"series_id": newest[0],
                                                        "issue_id": newest[1]})
    return (newest[0], issue) if issue else (None, None)


def view_all_series(state: APPState):
    from gui.messaging import new_item_messager
    storage: GenericStorage = state.storage
    with state.details:
        new_item_messager(state, "SERIES", "I would like to create a new comic book series.")

        # THE RESUME CARD: the lobby's front door — the bench you left your
        # pencils on, badged by the one production ledger
        series_id, issue = _last_bench(storage)
        if issue is not None:
            from gui.selection import SelectionItem, SelectedKind
            series = storage.read_object(cls=Series, primary_key={"series_id": series_id})
            cover = storage.find_series_image(series_id=series_id)
            try:
                from helpers.ledger import issue_ledger
                summary = issue_ledger(storage, series_id, issue.issue_id).summary()
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
        with ruled_page() as packer:
            view_all_instances(
                state=state,
                get_image_locator=lambda x: storage.find_series_image(series_id=x.series_id),
                get_instances=lambda: storage.read_all_objects(Series),
                kind="series",
                aspect_ratio="16/27",
                packer=packer, variants=[(2, 3), (8/3, 4), (4, 6)])