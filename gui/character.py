from loguru import logger
from nicegui import ui
from nicegui.events import UploadEventArguments
from schema import CharacterModel, CharacterVariant
from gui.elements import (
    header,
    crud_button,
    markdown_field_editor,
    view_all_instances,
    CrudButtonKind,
    )

from gui.messaging import post_user_message
from gui.state import APPState
from storage.generic import GenericStorage

def view_character(state:APPState):
    """
    View the details of a character.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
    """
    # Read the state to get the selection and ui elements
    selection = state.selection
    storage = state.storage

    character_id = selection[-1].id
    series_id = selection[-2].id
    
    character = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id})
    details = state.details

    # If the character is not found, clear the details and show an error message
    if character is None:
        state.clear_details()
        header("Character Not Found", 2).style('color: red;')
        message = f"Character with ID {character_id} not found in series {series_id}."
        header(message,4)
        logger.error(message)
        return

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(character.name.title(), 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current character."),size=1)

        markdown_field_editor(state, "Description", character.description)

        # APPEARS IN: every scene casting this character — the character's
        # footprint across the series at a glance (mirrors the setting page)
        from schema import Issue, SceneModel
        from gui.selection import SelectionItem, SelectedKind
        appears = []
        for iss in storage.read_all_objects(Issue, primary_key={"series_id": series_id}):
            for sc in storage.read_all_objects(SceneModel, primary_key={
                    "series_id": series_id, "issue_id": iss.issue_id}):
                if any(c.character_id == character_id for c in (sc.cast or [])):
                    appears.append((iss, sc))
        with ui.row().classes('w-full items-center q-px-sm').style('gap: 6px;'):
            ui.label('Appears in').classes('comic-label-sm')
            if not appears:
                ui.label('not cast in any scene yet').classes('text-xs text-gray-500')
            for iss, sc in appears[:12]:
                def goto(iss=iss, sc=sc):
                    base = [s for s in state.selection
                            if s.kind.value in ('all-series', 'series')]
                    state.change_selection(new=[*base,
                        SelectionItem(name=iss.name, id=iss.issue_id, kind=SelectedKind.ISSUE),
                        SelectionItem(name=sc.name, id=sc.scene_id, kind=SelectedKind.SCENE)])
                ui.chip(f"{iss.name} · Scene {sc.scene_number}: {sc.name}", icon='theater_comedy') \
                    .props('dense clickable outline') \
                    .tooltip('Open this scene') \
                    .on('click', lambda _, iss=iss, sc=sc: goto(iss, sc))

        from gui.elements import caption_action, ruled_page, uploader_card, CrudButtonKind as _CK
        with ui.element('div').classes('w-full q-mt-md'):
            def on_upload(e: UploadEventArguments):
                locator = storage.upload_reference_image(
                    obj=character,
                    name=e.name,
                    data=e.content,
                    mime_type=e.type
                )
                post_user_message(state, "I would like to create a new variant for this character from the uploaded image: " + locator)

            with ruled_page() as packer:
                view_all_instances(
                    state=state,
                    get_instances=lambda: storage.read_all_objects(CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id}),
                    get_image_locator=lambda variant: storage.find_variant_image(series_id=series_id, character_id=character_id, variant_id=variant.id),
                    kind="variant",
                    aspect_ratio="3:2",
                    packer=packer, variants=[(3, 2), (4, 8/3), (6, 4)],
                    overlap_caption=lambda: caption_action("Variants", _CK.CREATE,
                        lambda _: post_user_message(state, "I would like to create a new variant for this character."), 3)
                    )
                # Drop an image here to create a new variant from it
                uploader_card(state, on_upload=on_upload, packer=packer,
                              label='Drop image to create a variant')
        
        
            
def view_character_reference(state: APPState):
    """
    THE WARDROBE SWAP: pick which variant a cast member wears on the current
    board (panel or cover).  The light table's figure thumbs land here; the
    pose acetate and blocking follow the figure to its new wardrobe.
    """
    from schema import Panel, Cover

    logger.trace("view_character_reference")
    storage: GenericStorage = state.storage
    sel = state.selection

    series_id, character_id, variant_id = sel[-1].id.split("/")
    host = sel[-2] if len(sel) > 1 else None

    board = None
    if host is not None and host.kind.value == "panel" and len(sel) >= 5:
        board = storage.read_object(cls=Panel, primary_key={
            "series_id": series_id, "issue_id": sel[-4].id,
            "scene_id": sel[-3].id, "panel_id": host.id})
    elif host is not None and host.kind.value == "cover" and len(sel) >= 4:
        board = storage.read_object(cls=Cover, primary_key={
            "series_id": series_id, "issue_id": sel[-3].id, "cover_id": host.id})

    character = storage.read_object(cls=CharacterModel, primary_key={
        "series_id": series_id, "character_id": character_id})
    if board is None or character is None:
        state.clear_details()
        with state.details:
            ui.markdown("This wardrobe swap lost its board — go back and "
                        "click the figure's acetate on the light table again.")
        return

    ref = next((c for c in (board.character_references or [])
                if c.character_id == character_id and c.variant_id == variant_id), None) \
        or next((c for c in (board.character_references or [])
                 if c.character_id == character_id), None)
    if ref is None:
        state.clear_details()
        with state.details:
            ui.markdown(f"**{character.name}** isn't cast on this board anymore.")
        return

    def back_to_table():
        state.change_selection(new=sel[:-1])

    def get_choice():
        return ref.variant_id

    def set_choice(new_vid: str):
        if new_vid == ref.variant_id:
            back_to_table()
            return
        old_key = f"{character_id}/{ref.variant_id}"
        new_key = f"{character_id}/{new_vid}"
        ref.variant_id = new_vid
        # the pose follows the figure: acetate, blocking and group membership
        if old_key in (board.figure_images or {}):
            board.figure_images[new_key] = board.figure_images.pop(old_key)
        if old_key in (board.figure_blocking or {}):
            board.figure_blocking[new_key] = board.figure_blocking.pop(old_key)
        for g in list(board.layer_groups or {}):
            board.layer_groups[g] = [new_key if k == old_key else k
                                     for k in board.layer_groups[g]]
        storage.update_object(board)
        from gui.light_table import table_receipt
        table_receipt(state, f"👔 **{character.name}** now wears **{new_vid.replace('-', ' ')}** — "
                             f"re-pose them if the acetate should show the new look")
        state.is_dirty = True
        back_to_table()

    with state.details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"{character.name.title()} — Wardrobe", 0)
            ui.space()
            ui.button('Back to the table', icon='arrow_back').props('outline dense') \
                .on('click', lambda _: back_to_table())
        ui.label('Pick the variant this figure wears; their pose and blocking follow.') \
            .classes('text-sm text-gray-500 q-px-sm')

        view_all_instances(
            state,
            get_instances=lambda: storage.read_all_objects(
                cls=CharacterVariant,
                primary_key={"series_id": series_id, "character_id": character_id}),
            get_image_locator=lambda variant: storage.find_variant_image(
                series_id=series_id, character_id=character_id, variant_id=variant.id),
            kind="variant",
            aspect_ratio="3/2",
            get_choice=lambda: get_choice(),
            set_choice=lambda id: set_choice(id),
            variants=[(3, 2)],
            )
                                    
            