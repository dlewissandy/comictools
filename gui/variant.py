import os
from loguru import logger
from nicegui import ui
from schema import CharacterModel, CharacterVariant, StyledVariant
from gui.elements import (
    header, 
    crud_button, 
    header,
    markdown_field_editor, 
    view_all_instances,
    full_width_image_selector_grid,
    view_attributes,
    Attribute,
    CrudButtonKind
    )

from gui.messaging import new_item_messager
from gui.messaging import post_user_message
from gui.state import APPState
from storage.generic import GenericStorage



def view_character_variant(state:APPState):
    """
    View the details of a character.
    
    Args:
        breadcrumbs: The breadcrumbs UI element.
        details: The details UI element.
        chat_history: The chat history UI element.
    """
    # Read the state to get the selection and ui elements
    selection = state.selection
    storage: GenericStorage = state.storage

    variant_id = selection[-1].id
    character_id = selection[-2].id
    series_id = selection[-3].id

    character = storage.read_object(cls=CharacterModel, primary_key={"series_id": series_id, "character_id": character_id})
    variant = storage.read_object(cls=CharacterVariant, primary_key={"series_id": series_id, "character_id": character_id, "variant_id": variant_id})
    details = state.details

    
    # If the character is not found, clear the details and show an error message
    if character is None:
        state.clear_details()
        header("Character Not Found", 2).style('color: red;')
        message = f"Character with ID {character_id} not found in series {series_id}."
        header(message,4)
        logger.error(message)
        return
    
    if variant is None:
        state.clear_details()
        header("Variant Not Found", 2).style('color: red;')
        message = f"Variant with ID {variant_id} not found for character {character_id} in series {series_id}."
        header(message,4)
        logger.error(message)
        return

    variant: CharacterVariant = variant

    with details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(f"{character.name.title()} ({variant.name.title()})", 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current character variant."), size=1)


        # Composition: what this look is built from — chips with ✕ to detach.
        from gui.elements import removable_chips
        def _save_variant():
            storage.update_object(data=variant)

        def _remove_outfit(_key):
            variant.outfit_id = None
            _save_variant()

        def _remove_prop(key):
            variant.prop_ids = [p for p in (variant.prop_ids or []) if p != key]
            _save_variant()

        if variant.outfit_id or variant.prop_ids:
            with ui.column().classes('w-full q-px-sm').style('gap: 2px;'):
                removable_chips(state, "Outfit",
                    [(variant.outfit_id, variant.outfit_id.replace('-', ' ').title())] if variant.outfit_id else [],
                    _remove_outfit, icon='checkroom')
                removable_chips(state, "Carried props",
                    [(p, p.replace('-', ' ').title()) for p in (variant.prop_ids or [])],
                    _remove_prop, icon='category')

        with view_attributes(state,caption="Description", attributes=[
                Attribute(caption ="General Description", get_value= lambda: variant.description),
                Attribute(caption="Race", get_value=lambda: variant.race),
                Attribute(caption="Gender", get_value=lambda: variant.gender),
                Attribute(caption="Age", get_value=lambda: variant.age),
                Attribute(caption="Height", get_value=lambda: variant.height),
                Attribute(caption="Physical Appearance", get_value=lambda: variant.appearance),
                Attribute(caption="Attire", get_value=lambda: variant.attire),
                Attribute(caption="Behavior", get_value=lambda: variant.behavior),
            ], individual_icons=True, header_size=2, expanded=True):
            with ui.row().classes('w-full flex-nowrap'):
                header("Styled Images", 2).classes('ml-4')
                ui.space()
                crud_button(kind=CrudButtonKind.CREATE, action=lambda _: post_user_message(state, "I would like a new styled image for the current character variant."))
            from gui.elements import ruled_page, HEADER_CLASSES, TAILWIND_CARD
            from schema import ComicStyle
            with ruled_page() as packer:
                view_all_instances(
                    state=state,
                    get_instances=lambda: [StyledVariant(style_id=style_id, series_id=series_id, character_id=character_id, variant_id=variant_id, image_id=image_id) for style_id, image_id in variant.images.items()],
                    get_image_locator=lambda styled_image: storage.find_styled_image(series_id=styled_image.series_id, character_id=styled_image.character_id, variant_id= styled_image.variant_id, style_id=styled_image.style_id, name=styled_image.image_id),
                    kind="styled-variant",
                    aspect_ratio="3/2",
                    get_name=lambda _,img: img.name,
                    packer=packer, variants=[(3, 2), (4, 8/3), (6, 4)],
                )

                # GHOST CARDS: styles this look has no sheet in yet — one
                # click sends the render to the drawing board, so panels in
                # that style stop drawing the character off-model
                def ink_sheet(st):
                    from agentic.tools.imaging import create_styled_image_body
                    from helpers.render_queue import enqueue_renders
                    ui.notify(f"Inking {character.name.title()}'s {variant.name or variant_id} sheet "
                              f"in {st.name.title()} — it lands here when done.", type='info')
                    enqueue_renders(state, [(
                        f"styled sheet — {character.name} ({variant.name or variant_id}) in {st.name}",
                        lambda: create_styled_image_body(state, series_id, character_id,
                                                         variant_id, st.style_id),
                    )], role='the Character Designer')

                have = {sid for sid, img in (variant.images or {}).items() if img}
                for st in storage.read_all_objects(ComicStyle, order_by='name'):
                    if st.style_id in have:
                        continue
                    with packer.place_cell([(3, 2), (4, 8/3), (6, 4)], fudge=False):
                        with ui.card().classes(TAILWIND_CARD + ' mosaic-card relative ghost-card'):
                            art = st.image.get('art') if isinstance(st.image, dict) else st.image
                            if art and os.path.exists(art):
                                ui.image(source=art).props('fit=contain').style('top-padding: 0; bottom-padding:0;')
                            ui.label(st.name.title()).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                            with ui.column().classes('absolute inset-0 items-center justify-center z-10'):
                                ui.button(f'Ink it in {st.name.title()}', icon='brush') \
                                    .props('unelevated dense no-caps size=sm') \
                                    .tooltip("Render this look's reference sheet in this style") \
                                    .on('click', lambda _, st=st: ink_sheet(st))

            

            


        
        
        
            
# NOTE: the wardrobe-swap view (character-reference) lives in
# gui/character.py:view_character_reference — the copy that once sat here
# used long-dead APIs and was never routed to.
                                    
            