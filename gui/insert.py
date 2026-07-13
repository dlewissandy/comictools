"""
The insert workbench — the SAME light table as panels and covers.  A
full-page insert (a poster, an ad, a pin-up, the mailbag) is its own
scene: it owns its style and setting directly, so it rides the table as
both the subject and the scene-role.  The page's words (the mailbag's
letters, ad copy) ride under the rough as the table's margin notes.
"""
import os
from nicegui import ui
from loguru import logger

from gui.selection import SelectionItem, SelectedKind
from schema import Insert, Setting
from gui.state import APPState
from gui.elements import (
    header, crud_button, comic_page, ccell, CrudButtonKind,
)
from gui.messaging import post_user_message
from gui.light_table import light_table, rework_take_on_table, takes_row, tear_up_take
from storage.generic import GenericStorage


def view_insert(state: APPState):
    """
    View a full-page insert, pivoted around THE LIGHT TABLE.
    """
    storage: GenericStorage = state.storage
    details = state.details

    selection = state.selection
    insert_id = selection[-1].id
    issue_id = selection[-2].id
    series_id = selection[-3].id if len(selection) > 2 else None
    logger.debug(f"series: {series_id} issue: {issue_id} insert: {insert_id}")

    insert: Insert = storage.read_object(cls=Insert, primary_key={
        "series_id": series_id, "issue_id": issue_id, "insert_id": insert_id})
    if insert is None:
        details.clear()
        with details:
            ui.markdown(f"Insert with ID {insert_id} not found in issue {issue_id}.")
        return

    # an insert with no style of its own inks in the issue's style
    if not insert.style_id:
        from schema import Issue
        issue = storage.read_object(cls=Issue, primary_key={
            "series_id": series_id, "issue_id": issue_id})
        if issue is not None and issue.style_id:
            insert.style_id = issue.style_id

    setting: Setting = None
    if insert.setting_id:
        setting = storage.read_object(cls=Setting, primary_key={
            "series_id": series_id, "setting_id": insert.setting_id})

    def open_editor():
        if not insert.image:
            ui.notify("No artwork to edit yet — render the page first.", type="warning")
            return
        new_itm = SelectionItem(name="Edit Insert Art", id=insert.image, kind=SelectedKind.IMAGE_EDITOR)
        state.change_selection(new=[*state.selection, new_itm])

    details.clear()
    with details:
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0;'):
            header(f"{insert.kind.replace('-', ' ').title()}: {insert.name}", 0)

            # WALK THE INSERTS: ‹ › steps through the book's full pages
            sibs = sorted(storage.read_all_objects(Insert, primary_key={
                "series_id": series_id, "issue_id": issue_id}),
                key=lambda i: (i.after_scene_number, i.insert_id))
            idx = next((i for i, x in enumerate(sibs) if x.insert_id == insert_id), 0)

            def goto(delta):
                tgt = sibs[idx + delta]
                state.change_selection(new=[*selection[:-1], SelectionItem(
                    name=tgt.name, id=tgt.insert_id, kind=SelectedKind.INSERT)])

            if len(sibs) > 1:
                with ui.row().classes('items-center flex-nowrap self-center').style('gap: 2px;'):
                    pb = ui.button(icon='chevron_left').props('flat round dense') \
                        .tooltip('Previous insert')
                    if idx <= 0:
                        pb.props('disable')
                    else:
                        pb.on('click', lambda _: goto(-1))
                    ui.label(f'{idx + 1}/{len(sibs)}').classes('text-xs text-gray-500')
                    nb = ui.button(icon='chevron_right').props('flat round dense') \
                        .tooltip('Next insert')
                    if idx >= len(sibs) - 1:
                        nb.props('disable')
                    else:
                        nb.on('click', lambda _: goto(1))

            # ITS PLACE IN THE BOOK: one click back up, landing on this page
            def back_to_book():
                if not hasattr(state, '_book_anchor'):
                    state._book_anchor = {}
                state._book_anchor[issue_id] = f'insert-{insert_id}'
                i = next((j for j, s in enumerate(state.selection)
                          if s.kind.value == 'issue'), None)
                if i is not None:
                    state.change_selection(new=state.selection[:i + 1])
            place = (f'after scene {insert.after_scene_number}'
                     if insert.after_scene_number else 'front of the book')
            ui.chip(place, icon='menu_book').props('dense outline clickable') \
                .tooltip('Where this page sits — back up to the book') \
                .on('click', lambda _: back_to_book())

            ui.space()
            from gui.strike import strike
            from agentic.tools.deleter import delete_insert as _del_insert
            crud_button(kind=CrudButtonKind.DELETE, size=1,
                        action=lambda _: strike(state, _del_insert,
                            {"series_id": series_id, "issue_id": issue_id,
                             "insert_id": insert_id},
                            f"the '{insert.name}' {insert.kind}"))

        page = comic_page()
        page.__enter__()

        # THE LIGHT TABLE: same table as panels and covers — the insert
        # doubles as its own scene (it owns style_id and setting_id).  The
        # page's words live in THE BRIEF under the rough, same as everywhere.
        with ccell(12):
            featured = storage.find_image(obj=insert, locator=insert.image) if insert.image else None
            if featured and not os.path.exists(featured):
                featured = None
            light_table(
                state, insert, insert, setting,
                featured=featured,
                actions=[
                    ('edit', 'Take this artwork to the healing bench', lambda _: open_editor()),
                    ('layers', 'Rework this page on the table — it becomes the background layer',
                     lambda _: rework_take_on_table(state, insert, featured)),
                    ('brush', 'Render the page',
                     lambda _: post_user_message(state, f"Render the '{insert.name}' insert.")),
                    ('delete', 'Tear up this take (the receipt can bring it back)',
                     lambda _: tear_up_take(state, insert, featured)),
                ])

        # TAKES: every render; click one to feature it on the page.
        with ccell(12):
            takes_row(state, insert, featured)

        page.__exit__(None, None, None)
