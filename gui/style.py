from loguru import logger
from gui.state import APPState
from gui.elements import (
    header, view_all_instances, markdown_field_editor, view_attributes, Attribute, image_drop_field_editor, full_width_image_selector_grid, crud_button,
    CrudButtonKind)
from gui.messaging import post_user_message
from gui.constants import TAILWIND_CARD
from nicegui import ui
from gui.state import APPState
from storage.generic import GenericStorage
from gui.selection import SelectedKind
from schema import ComicStyle, StyleExample

def view_style(state: APPState):
    """
    Editor for comic styles.
    """

    # Read in the state
    selection = state.selection
    storage: GenericStorage = state.storage
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": selection[-1].id}) if selection and selection[-1].id else None

    if style is None and selection and selection[-1].id:
        # the style may live in ANOTHER house — open it and carry on, the
        # same silent switch every publisher link makes
        from gui.home import open_house_holding
        style = open_house_holding(storage, ComicStyle, {"style_id": selection[-1].id})
        if style is not None:
            try:
                ui.notify(f"Opened the house that holds {style.name}", type='info')
            except Exception:
                pass

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

            # RENAME, right where the name is: one field, saved on the spot
            def rename_dialog(_=None):
                with ui.dialog() as dlg, ui.card().classes('soft-card').style('min-width: 420px;'):
                    ui.label('Rename this style').classes('caption-box caption-box-sm')
                    field = ui.input(value=style.name).classes('w-full q-mt-sm') \
                        .props('outlined dense autofocus')

                    def save():
                        new_name = (field.value or '').strip()
                        if not new_name:
                            ui.notify('A style needs a name.', type='warning')
                            return
                        old_name, style.name = style.name, new_name
                        storage.update_object(style)
                        dlg.close()
                        # the coauthor hears about it — a silent rename would
                        # leave the Art Director speaking the old name
                        from gui.light_table import table_receipt
                        table_receipt(state, f"🏷 renamed the **{old_name}** style "
                                             f"to **{new_name}**")
                        from gui.selection import SelectionItem
                        state.change_selection(new=[*state.selection[:-1],
                            SelectionItem(name=new_name, id=style.style_id,
                                          kind=state.selection[-1].kind)])
                    field.on('keydown.enter', lambda _: save())
                    ui.button('Save', icon='save').props('unelevated dense no-caps') \
                        .classes('q-mt-sm').on('click', lambda _: save())
                dlg.open()
            crud_button(kind=CrudButtonKind.UPDATE, action=rename_dialog, size=1)
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
                        

def view_pick_style(state: APPState):
    """
    View the style picker.
    
    Args:
        state: The GUI elements containing the details and selection.
    """

    from schema import Cover,CoverLocation, SceneModel, Series, Issue
    logger.debug("view_pick_style")

    # Dereference the state to get the selection and details.
    selection = state.selection
    storage: GenericStorage = state.storage
    
    parent_kind = selection[-2].kind
    if parent_kind == SelectedKind.ISSUE:
        issue_id = selection[-2].id
        series_id = selection[-3].id
        parent = storage.read_object(cls=Issue, primary_key={"series_id": series_id, "issue_id": issue_id})
        writer = lambda: storage.update_object(data=parent)
    elif parent_kind == SelectedKind.SCENE:
        scene_id = selection[-2].id
        issue_id = selection[-3].id
        series_id = selection[-4].id
        parent = storage.read_object(cls=SceneModel, primary_key={"series_id": series_id, "issue_id": issue_id, "scene_id": scene_id})
        writer = lambda: storage.update_object(data=parent)
    elif parent_kind == SelectedKind.COVER:
        issue_id = selection[-3].id
        series_id = selection[-4].id
        cover_id = selection[-2].id
        parent = storage.read_object(cls=Cover, primary_key={"series_id": series_id, "issue_id": issue_id, "cover_id": cover_id})
        writer = lambda: storage.update_object(data=parent)

    style_id = selection[-1].id
    style = storage.read_object(cls=ComicStyle, primary_key={"style_id": style_id})

    # Create a setter function for the publisher choice
    def set_style(style_id):
        if parent is not None:
            parent.style_id = style_id
            writer()

    with state.details:
        header("Pick a Style", 1)
        view_all_instances(
            state=state,
            get_instances=lambda: storage.read_all_objects(ComicStyle),
            get_image_locator=lambda x: storage.find_image(StyleExample(style_id=x.style_id, example_type="art", mime_type="image/jpeg", image_id="art"), x.image.get('art',None)) if isinstance(x.image, dict) and x.image.get('art', None) else None,
            kind="style",
            aspect_ratio="1/1",
            get_name=lambda _,x: x.name,
            get_choice=lambda : parent.style_id if parent else None,
            set_choice=set_style,
            variants=[(3, 3)],
        )           

    