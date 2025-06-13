from loguru import logger
from gui.state import APPState
from gui.elements import header, view_all_instances, markdown_field_editor, view_attributes, Attribute, image_drop_field_editor, full_width_image_selector_grid, crud_button
from gui.messaging import post_user_message
from style.comic import ComicStyle
from gui.constants import TAILWIND_CARD
from nicegui import ui
from gui.state import APPState

def view_style(state: APPState):
    """
    Editor for comic styles.
    """
    
    # Read in the state
    selection = state.selection
    style = ComicStyle.read(id=selection[-1].id)

    # Sanity check
    if style is None:
        msg = f"Style with ID {selection[-1].id} not found."
        logger.error(msg)
        header("Error", 0)
        header(msg, 2).style("color: red;")
        return

    # Render the information about the style
    with state.details:
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(style.name.title(), 0)
            ui.space()
            crud_button(kind="delete", action=lambda _: post_user_message(state, "I would like to delete the current style."),size=1)

        markdown_field_editor(
            state=state,
            name = "Description",
            value = style.description,
            header_size=2
        )

        # If there is an image, display it here

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
            full_width_image_selector_grid(
                state=state,
                kind="art-style-image",
                images_path=style.image_path(img_type="art"),
                get_selection=lambda: style.image["art"] if isinstance(style.image, dict) else None,
                set_selection=lambda img_id: style.set_image(image_type="art", id=img_id),
                get_images=style.all_images,
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
            full_width_image_selector_grid(
                state=state,
                kind="character-style-image",
                images_path=style.image_path(img_type="character"),
                get_selection=lambda: style.image.get("character",None) if isinstance(style.image, dict) else None,
                set_selection=lambda img_id: style.set_image(image_type="character", id=img_id),
                get_images=lambda: style.all_images(img_type="character"),
                aspect_ratio="3/2"
            )



        with ui.expansion(value=True).classes('w-full border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
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
                        full_width_image_selector_grid(
                            state=state,
                            kind=f"{k}-style-example-image",
                            images_path=style.image_path(img_type=f"{k}"),
                            get_selection=lambda k=k: style.image.get(k.lower().replace("_", "-"),None),
                            set_selection=lambda img_id, k=k: style.set_image(image_type=f"{k}", id=img_id),
                            get_images=lambda k=k: style.all_images(img_type=f"{k}"),
                            aspect_ratio="1/1",
                            columns=2,
                            header_size=3
                        )
                        

def view_pick_style(state):
    """
    View the style picker.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    from models.series import Series
    from models.issue import Issue
    from models.scene import SceneModel
    from models.panel import TitleBoardModel,CoverLocation
    logger.debug("view_pick_style")

    # Dereference the state to get the selection and details.
    selection = state.selection
    
    parent_kind = selection[-2].kind
    if parent_kind == "issue":
        issue_id = selection[-2].id
        series_id = selection[-3].id
        parent = Issue.read(series_id=series_id, id=issue_id)
    elif parent_kind == "scene":
        scene_id = selection[-2].id
        issue_id = selection[-3].id
        series_id = selection[-4].id
        parent = SceneModel.read()
    elif parent_kind == "front-cover":
        issue_id = selection[-2].id
        series_id = selection[-3].id
        parent = TitleBoardModel.read(series=series_id, issue=issue_id, location=CoverLocation.FRONT_COVER)
    elif parent_kind == "back-cover":
        issue_id = selection[-2].id
        series_id = selection[-3].id
        parent = TitleBoardModel.read(series=series_id, issue=issue_id, location=CoverLocation.BACK_COVER)
    elif parent_kind == "inside-front-cover":
        gissue_id = selection[-2].id
        series_id = selection[-3].id
        parent = TitleBoardModel.read(series=series_id, issue=issue_id, location=CoverLocation.INSIDE_FRONT_COVER)
    elif parent_kind == "inside-back-cover":
        issue_id = selection[-2].id
        series_id = selection[-3].id
        parent = TitleBoardModel.read(series=series_id, issue=issue_id, location=CoverLocation.INSIDE_BACK_COVER)
    
    style_id = selection[-1].id
    style = ComicStyle.read(id=style_id) if style_id else None

    # Create a setter function for the publisher choice
    def set_style(style_id):
        if parent is not None:
            parent.style = style_id
            parent.write()

    with state.details:
        header("Pick a Style", 1)
    view_all_instances(
        state=state,
        get_instances=style.read_all,
        kind="style",
        aspect_ratio="1/1",
        get_name=lambda x: x.name,
        get_choice=lambda : parent.style if parent else None,
        set_choice=set_style,
    )           


def view_pick_art_style_image(
    state: APPState
):
    from gui.elements import full_width_image_selector_grid
    selection = state.selection
    style_id = selection[-2].id
    style = ComicStyle.read(id=style_id)
    if style is None:
        msg = f"Style with ID {style_id} not found."
        logger.error(msg)
        header("Error", 0)
        header(msg, 2).style("color: red;")
        return

    def get_selection():
        style = ComicStyle.read(id=style_id)
        return style.image_filepath(img_type="art")
    
    def set_selection(id: str):
        style = ComicStyle.read(id=style_id)
        style.set_image(img_type="art", image_id=id)
        style.write()
        state["is_dirty"] = True

    def get_images():
        style = ComicStyle.read(id=style_id)
        return style.all_images(img_type="art")
    
    image_path = style.image_path(img_type="art")

    with state.details:
        header(f"Art Style Image for {style.name}", 1)
    full_width_image_selector_grid(
        state=state,
        kind ="art-style-image",
        images_path = image_path,
        get_selection=get_selection,
        set_selection=set_selection,
        get_images=get_images,
    )
    