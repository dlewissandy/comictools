"""
The cover workbench — the SAME light table as the panel page.  A cover is
its own scene: it owns its style and setting directly, so it rides the
table as both the subject and the scene-role.  Cover design (the brief) up
top, then the acetate stack, the rough and the print side by side, takes
below.  Trade dress (title, issue number, price, credits) is lettered by
the Cover Artist at render time.
"""
import os
from nicegui import ui
from loguru import logger

from gui.selection import SelectionItem, SelectedKind
from schema import Cover, Setting
from gui.state import APPState
from gui.elements import (
    header, crud_button, comic_page, ccell, CrudButtonKind,
)
from gui.messaging import post_user_message
from gui.light_table import light_table, rework_take_on_table, takes_row, tear_up_take
from storage.generic import GenericStorage


def view_cover(state: APPState):
    """
    View the cover of a comic book issue, pivoted around THE LIGHT TABLE.

    Args:
        state: The GUI elements containing the details and selection.
    """
    storage: GenericStorage = state.storage
    details = state.details

    selection = state.selection
    cover_id = selection[-1].id
    issue_id = selection[-2].id
    series_id = selection[-3].id if len(selection) > 2 else None
    logger.debug(f"series: {series_id} issue: {issue_id} cover: {cover_id}")

    cover: Cover = storage.read_object(cls=Cover, primary_key={
        "series_id": series_id, "issue_id": issue_id, "cover_id": cover_id})
    if cover is None:
        details.clear()
        with details:
            ui.markdown(f"Cover with ID {cover_id} not found in issue {issue_id}.")
        return

    # a cover IS its own scene: setting and style hang off the cover itself
    setting: Setting = None
    if cover.setting_id:
        setting = storage.read_object(cls=Setting, primary_key={
            "series_id": series_id, "setting_id": cover.setting_id})

    def open_editor():
        if not cover.image:
            ui.notify("No artwork to edit yet — render the cover first.", type="warning")
            return
        new_itm = SelectionItem(name="Edit Cover Image", id=cover.image, kind=SelectedKind.IMAGE_EDITOR)
        state.change_selection(new=[*state.selection, new_itm])

    details.clear()
    with details:
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0;'):
            header(cover.location.value.replace('-', ' ').title() + " Cover", 0)

            # WALK THE COVERS: ‹ › steps front → inside-front → inside-back → back
            order = ["front", "inside-front", "inside-back", "back"]
            sibs = sorted(storage.read_all_objects(Cover, primary_key={
                "series_id": series_id, "issue_id": issue_id}),
                key=lambda c: order.index(c.location.value) if c.location.value in order else 9)
            idx = next((i for i, c in enumerate(sibs) if c.cover_id == cover_id), 0)

            def goto(delta):
                tgt = sibs[idx + delta]
                state.change_selection(new=[*selection[:-1], SelectionItem(
                    name=tgt.location.value.replace('-', ' ').title() + " Cover",
                    id=tgt.cover_id, kind=SelectedKind.COVER)])

            if len(sibs) > 1:
                with ui.row().classes('items-center flex-nowrap self-center').style('gap: 2px;'):
                    pb = ui.button(icon='chevron_left').props('flat round dense') \
                        .tooltip('Previous cover')
                    if idx <= 0:
                        pb.props('disable')
                    else:
                        pb.on('click', lambda _: goto(-1))
                    ui.label(f'{idx + 1}/{len(sibs)}').classes('text-xs text-gray-500')
                    nb = ui.button(icon='chevron_right').props('flat round dense') \
                        .tooltip('Next cover')
                    if idx >= len(sibs) - 1:
                        nb.props('disable')
                    else:
                        nb.on('click', lambda _: goto(1))

            ui.space()
            from gui.strike import strike
            from agentic.tools.deleter import delete_cover as _del_cover
            crud_button(kind=CrudButtonKind.DELETE, size=1,
                        action=lambda _: strike(state, _del_cover,
                            {"series_id": series_id, "issue_id": issue_id,
                             "cover_id": cover_id},
                            f"the {cover.location.value.replace('-', ' ')} cover"))

        page = comic_page()
        page.__enter__()

        # THE LIGHT TABLE: same table as panels — the cover doubles as its
        # own scene (it owns style_id and setting_id).  The cover design
        # brief rides under the rough as the table's margin notes.
        with ccell(12):
            featured = storage.find_image(obj=cover, locator=cover.image) if cover.image else None
            if featured and not os.path.exists(featured):
                featured = None
            light_table(
                state, cover, cover, setting,
                featured=featured,
                actions=[
                    ('edit', 'Open this artwork in the image editor', lambda _: open_editor()),
                    ('layers', 'Rework this take on the table — it becomes the background layer',
                     lambda _: rework_take_on_table(state, cover, featured)),
                    ('brush', 'Render a new take', lambda _: post_user_message(state, "I would like to render this cover.")),
                    ('delete', 'Tear up this take (the receipt can bring it back)',
                     lambda _: tear_up_take(state, cover, featured)),
                ])

        # TAKES: every render; click one to feature it on the table.
        with ccell(12):
            takes_row(state, cover, featured)

        page.__exit__(None, None, None)
