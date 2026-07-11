import os
from loguru import logger
from nicegui import ui
from gui.elements import (
    markdown, header, image_field_editor, view_all_instances, markdown_field_editor, Attribute, view_attributes, crud_button, post_user_message,
    CrudButtonKind, comic_page, cpanel, ccell
    )
from schema import ComicStyle, Issue, Cover, Panel, SceneModel, StyleExample
from gui.state import APPState
from gui.messaging import post_user_message
from gui.selection import SelectionItem, SelectedKind

def view_issue(state:APPState):
    """
    View the details of an issue.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    from gui.messaging import new_item_messager
    selection = state.selection
    storage = state.storage

    series_id = selection[-2].id if len(selection) > 1 else None
    issue_id = selection[-1].id
    
    issue = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id}) if series_id else None
    details = state.details
    if issue is None:
        state.clear_details()
        message = f"Issue with ID {issue_id} not found."
        with details:
            ui.markdown(message)
        return
    
    if issue.style_id is None:
        logger.debug(f"Issue {issue.id} has no style set.")
        style = None
    else:
        style = storage.read_object(cls=ComicStyle, primary_key={"style_id": issue.style_id}) if issue.style_id else None
        if style is None:
            logger.warning(f"Issue {issue.id} has style set to {issue.style_id  } but style not found.")

    
    # Production pulse: rendered/total panels across the issue's scenes.
    def _scene_counts(scene_id):
        panels = storage.read_all_objects(Panel, primary_key={"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
        done = sum(1 for p in panels if p.image and os.path.exists(p.image))
        return done, len(panels)

    scenes_all = storage.read_all_objects(SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id})
    done_total = total = 0
    for sc in scenes_all:
        d, t = _scene_counts(sc.scene_id)
        done_total += d; total += t

    # ---- the production dashboard: what stands between here and a bound book
    from schema import Page
    covers_all = storage.read_all_objects(Cover, primary_key={"series_id": series_id, "issue_id": issue_id})
    front_ok = any(c.location.value == "front" and c.image and os.path.exists(c.image) for c in covers_all)
    pages_all = storage.read_all_objects(Page, primary_key={"series_id": series_id, "issue_id": issue_id})
    export_path = os.path.join("data", "series", series_id, "issues", issue_id, "exports", f"{issue_id}.pdf")

    def _pill(ok: bool, label: str, fix_message: str | None = None):
        """A dashboard step: green when done; amber and CLICKABLE when it isn't."""
        if ok:
            ui.chip(label, icon='check_circle', color='green').props('dense outline')
        else:
            chip = ui.chip(label, icon='radio_button_unchecked', color='orange').props('dense clickable')
            if fix_message:
                chip.tooltip('Click and I\'ll get started')
                chip.on('click', lambda _, m=fix_message: post_user_message(state, m))

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"ISSUE {issue.issue_number}: {issue.name}", 0)
            ui.space()
            ui.button('Read', icon='menu_book').props('rounded') \
                .tooltip('Read the issue front to back') \
                .on('click', lambda _: ui.run_javascript(
                    f"window.open('/series/{series_id}/issue/{issue_id}/read', '_blank');"))
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current issue."))

        # THE PAGE: everything below stitches into a 12-column comic page.
        page = comic_page()
        page.__enter__()

        # Production dashboard: a slim full-width panel of pills.
        with cpanel(12), ui.row().classes('w-full items-center').style('gap: 8px;'):
            ui.label('Production').classes('comic-label-sm')
            _pill(bool(issue.story), 'story', 'Help me write the story for this issue.')
            _pill(len(scenes_all) > 0, 'scenes', 'Break my story into scenes.')
            _pill(total > 0, 'panels', 'Break the scenes into panels.')
            _pill(total > 0 and done_total == total,
                  f'artwork {done_total}/{total}' if total else 'artwork',
                  'Render the missing panels.')
            _pill(front_ok, 'front cover', 'Create and render a front cover.')
            _pill(len(pages_all) > 0, 'page layout', 'Lay out the pages for this issue.')
            everything = bool(issue.story) and total > 0 and done_total == total and front_ok
            _pill(everything and os.path.exists(export_path), 'bound PDF', 'Export the issue as a PDF.')

        
        with cpanel(8):
            markdown_field_editor(state, "Story", issue.story)
        with cpanel(4):
            image_field_editor(
                    state=state, 
                    kind=SelectedKind.PICK_STYLE, 
                    get_caption=lambda: "Style", 
                    get_id =lambda: style.style_id if style else None, 
                    get_image_filepath=lambda: storage.find_image(
                        StyleExample(
                            style_id=style.style_id,
                            example_type="art",
                            image_id=style.image.get("art"),
                            mime_type="image/jpeg"
                        ), style.image.get("art", None)) if style else None
                )


        def _set(field):
            # click-to-edit: write the scalar directly, receipt lands in chat
            def setter(value):
                setattr(issue, field, value or None)
                storage.update_object(data=issue)
            return setter

        with ccell(12):
            view_attributes(
                    state = state,
                    caption="Attributes",
                    attributes = [
                        Attribute(caption="publication date", get_value=lambda: issue.publication_date, set_value=_set("publication_date")),
                        Attribute(caption="price", get_value=lambda: issue.price, set_value=lambda v: (setattr(issue, "price", float(v) if v else None), storage.update_object(data=issue))),
                        Attribute(caption="writer", get_value=lambda: issue.writer, set_value=_set("writer")),
                        Attribute(caption="artist", get_value=lambda: issue.artist, set_value=_set("artist")),
                        Attribute(caption="colorist", get_value=lambda: issue.colorist, set_value=_set("colorist")),
                        Attribute(caption="creative minds", get_value=lambda: issue.creative_minds, set_value=_set("creative_minds"))
                    ],
                    individual_icons=False,
                )

        COVER_ORDER = ["front", "inside-front", "inside-back", "back"]
        order_by = lambda cover: COVER_ORDER.index(cover.location.value) if cover.location.value in COVER_ORDER else -1

        from gui.elements import caption_action, CrudButtonKind as _CK
        def _cap(text, msg):
            return lambda: caption_action(text, _CK.CREATE, lambda _, m=msg: post_user_message(state, m), 3)
        from gui.elements import PagePacker
        packer = PagePacker(12)
        mosaic = ui.element('div').classes('comic-mosaic cspan-12')
        mosaic.__enter__()
        if True:
            view_all_instances(
                state=state,
                get_instances = lambda: storage.read_all_objects(Cover, primary_key={"series_id": series_id, "issue_id": issue_id}, order_by=order_by),
                get_image_locator=lambda cover: cover.image,
                kind=SelectedKind.COVER,
                get_name=lambda _,cover: f"{cover.location.replace('_', ' ').title()} Cover",
                aspect_ratio="6/9",
                packer=packer, variants=[(2, 3), (4, 6)],
                overlap_caption=_cap("Covers", "I would like to create a new cover for this issue.")
            )

        if True:
            view_all_instances(
                state=state,
                get_instances = lambda: storage.read_all_objects(SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id}, order_by="scene_number"),
                get_image_locator=lambda scene: storage.find_scene_image(series_id=series_id, issue_id=issue_id, scene_id=scene.scene_id),
                kind=SelectedKind.SCENE,
                aspect_ratio="16/9",
                get_name=lambda i,scene: (lambda d,t: f"Scene {i+1}: {scene.name}" + (f"  ·  {d}/{t} 🎨" if t else "  ·  no panels"))(*_scene_counts(scene.scene_id)),
                get_markdown=lambda scene: scene.story,
                number_of_columns=3,
                packer=packer, variants=[(3, 2), (6, 4)],
                overlap_caption=_cap("Scenes", "I would like to create a new scene for this issue.")
            )
        packer.finalize()
        mosaic.__exit__(None, None, None)
        page.__exit__(None, None, None)                
        