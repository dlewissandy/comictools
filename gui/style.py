from loguru import logger
from gui.state import APPState
from gui.elements import (
    header, markdown_field_editor, view_attributes, Attribute, full_width_image_selector_grid, crud_button,
    CrudButtonKind)
from nicegui import ui
from gui.state import APPState
from storage.generic import GenericStorage
from schema import ComicStyle, StyleExample

def view_style(state: APPState):
    """
    Editor for comic styles.
    """

    # Read in the state
    selection = state.selection
    storage: GenericStorage = state.storage

    # THE TRAIL NAMES THE HOUSE: default styles are COPIES sharing ids in
    # every repo, and state.storage is already scoped to the trail's own
    # house (publisher first, series second, style holder last) — so this
    # read edits the RIGHT copy, and a miss is a genuine not-found
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": selection[-1].id}) if selection and selection[-1].id else None

    # Sanity check
    if style is None:
        msg = f"Style with ID {selection[-1].id} not found."
        logger.error(msg)
        header("Error", 0)
        header(msg, 2).style("color: red;")
        return

    # Render the information about the style
    with state.details:
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0;'):
            header(style.name.title(), 0)

            # RENAME rides the conversation box (the author's ruling: no
            # modals for text entry) — Enter saves on the spot
            def rename_via_conversation(_=None):
                prefix = f"Rename the {style.name} style to: "

                def _do(new_name):
                    if not new_name:
                        ui.notify('A style needs a name.', type='warning')
                        return
                    old_name, style.name = style.name, new_name
                    storage.update_object(style)
                    from gui.light_table import table_receipt
                    table_receipt(state, f"🏷 renamed the **{old_name}** style "
                                         f"to **{new_name}**")
                    from gui.selection import SelectionItem
                    state.change_selection(new=[*state.selection[:-1],
                        SelectionItem(name=new_name, id=style.style_id,
                                      kind=state.selection[-1].kind)])
                state.user_input.value = prefix
                state._input_intercept = (prefix, _do, None)
                try:
                    state.user_input.run_method('focus')
                except Exception:
                    pass
            crud_button(kind=CrudButtonKind.UPDATE, action=rename_via_conversation, size=1)
            ui.space()

            # STRIKE, not a chat errand: the style goes to the wastebasket
            # with a way back (the deleter walks the room up to the house
            # itself — the struck style is the current selection)
            from gui.strike import strike
            from agentic.tools.deleter import delete_style as _del_style
            crud_button(kind=CrudButtonKind.DELETE, size=1,
                        action=lambda _: strike(state, _del_style,
                            {"style_id": style.style_id},
                            f"the style '{style.name}'"))

        markdown_field_editor(
            state=state,
            name = "Description",
            value = style.description,
            header_size=2
        )

        # If there is an image, display it here

        def set_image(image_locator: str, example_type: str = "art"):
            """
            Set the image for the style.
            """
            if not isinstance(style.image, dict):
                style.image = {}
            style.image[example_type] = image_locator
            storage.update_object(style)

        art_style = style.art_style
        with view_attributes(state,caption="Art Style", attributes=[
                Attribute(caption ="line style", get_value= lambda: art_style.line_styles),
                Attribute(caption="inking tools", get_value=lambda: art_style.inking_tools),
                Attribute(caption="shading style", get_value=lambda: art_style.shading_style),
                Attribute(caption="color palette", get_value=lambda: art_style.color_palette),
                Attribute(caption="spot colors", get_value=lambda: art_style.spot_colors),
                Attribute(caption="registration", get_value=lambda: art_style.registration),
                Attribute(caption="lettering style", get_value=lambda: art_style.lettering_style),
            ], individual_icons=False, header_size=2):
            example = StyleExample(style_id=style.id, example_type="art", image_id="art", mime_type="image/jpeg")
            full_width_image_selector_grid(
                state=state,
                image_kind_name="art style image",
                get_images = lambda example=example: storage.list_images(example),
                get_selection=lambda: style.image["art"] if isinstance(style.image, dict) else None,
                set_selection=lambda img_id: set_image(image_locator=img_id, example_type="art"),
                upload_image=lambda name, data, mime_type: storage.upload_image(
                    obj=example,
                    name=name,
                    data=data,
                    mime_type=mime_type
                ),
                aspect_ratio="3/2"
            )
        
        character_style = style.character_style
        with view_attributes(state, caption="Character Style", attributes=[
            Attribute(caption="head to body ratio", get_value=lambda: character_style.head_to_body_ratio),
            Attribute(caption="limb proportions", get_value=lambda: character_style.limb_proportions),
            Attribute(caption="anatomy detail", get_value=lambda: character_style.anatomy_detail),
            Attribute(caption="eye style", get_value=lambda: character_style.eye_style),
            Attribute(caption="nose style", get_value=lambda: character_style.nose_style),
            Attribute(caption="mouth style", get_value=lambda: character_style.mouth_style),
            Attribute(caption="expression exaggeration", get_value=lambda: character_style.expression_exaggeration),
            Attribute(caption="silhouette clarity", get_value=lambda: character_style.silhouette_clarity),
            Attribute(caption="silhouette shape language", get_value=lambda: character_style.silhouette_shape_language),
            Attribute(caption="detail complexity", get_value=lambda: character_style.detail_complexity),
            Attribute(caption="texture accents", get_value=lambda: character_style.texture_accents),
        ],individual_icons=False, header_size=2):
            example = StyleExample(style_id=style.id, example_type="character", image_id="character", mime_type="image/jpeg")
            full_width_image_selector_grid(
                state=state,
                image_kind_name="character style image",
                get_images=lambda example=example: storage.list_images(example),
                get_selection=lambda: style.image.get("character",None) if isinstance(style.image, dict) else None,
                set_selection=lambda img_id: set_image(image_locator=img_id, example_type="character"),
                upload_image=lambda name, data, mime_type: storage.upload_image(
                    obj=example,
                    name=name,
                    data=data,
                    mime_type=mime_type),
                aspect_ratio="3/2"
            )



        with ui.expansion(value=True).classes('w-full section-flat') as expansion:
            with expansion.add_slot('header'):
                header("Dialog Style", 2)     

            with ui.element().classes('grid grid-cols-2 gap-2 w-full'):
                for key in ["chat", "whisper", "shout", "thought", "sound_effect", "narration"]:
                    dialog_style = getattr(style.bubble_styles, key, None)
                    logger.debug(f"key={key}, dialog_style={dialog_style}")
                    with view_attributes(state, caption=key.replace('_',' ').title() + " Bubble Style", attributes=[
                        Attribute(caption="shape", get_value=lambda: dialog_style.shape),
                        Attribute(caption="border", get_value=lambda: dialog_style.border),
                        Attribute(caption="fill color", get_value=lambda: dialog_style.fill_color),
                        Attribute(caption="font", get_value=lambda: dialog_style.font)], expanded=False, individual_icons=False, header_size=3):
                        k = key.replace('_','-')
                        example = StyleExample(style_id=style.id, example_type=k, image_id=k, mime_type="image/jpeg")
                        full_width_image_selector_grid(
                            state=state,
                            image_kind_name=f"{k} style example image",
                            
                            get_selection=lambda k=k: style.image.get(k.lower().replace("_", "-"),None),
                            set_selection=lambda img_id, example_type=k: set_image(image_locator=img_id, example_type=example_type),
                            get_images=lambda example=example: storage.list_images(example),
                            upload_image=lambda name, data, mime_type, k=k, example=example: storage.upload_image(
                                obj=example,
                                name=name,
                                data=data,
                                mime_type=mime_type),
                            aspect_ratio="1/1",
                            columns=2,
                            header_size=3
                        )
                        

