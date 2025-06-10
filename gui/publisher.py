import os
from loguru import logger
from nicegui import ui
from models.publisher import Publisher
from gui.elements import header, crud_button, markdown_field_editor, full_width_image_selector_grid, view_all_instances, view_attributes, Attribute
from gui.messaging import post_user_message
from gui.elements import init_cardwall
from gui.constants import TAILWIND_CARD


def view_publisher(state):
    """
    View the details of a publisher.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    logger.debug("view_publisher")
    selection = state.get("selection")
    publisher_id = selection[-1].id
    publisher = Publisher.read(id=publisher_id)
    details = state.get("details")

    if publisher is None:
        header("Publisher not found", 0).style('text-red-500')
        return
    
    with details:
        # The title for the viewer is the Publisher name
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(publisher.name.title(), 0)
            ui.space()
            crud_button(kind="delete", action=lambda _: post_user_message(state, "I would like to delete the current publisher."),size=1)


        # Below that we have a full width row for editing the publisher's description
        # and a button to save the changes
        markdown_field_editor(state, "Description", publisher.description)

        # Below that we have a full width row for editing the description of the
        # publisher's logo
        with view_attributes(
            state=state, 
            caption="Logo",
            attributes=[
                Attribute(caption="description", get_value=lambda: publisher.logo)
            ], 
            expanded=False, 
            individual_icons = False,
            header_size = 2
            ):

            # Below that we have a series of full width rows for selecting the
            # preferred image for the publisher's logo.
            full_width_image_selector_grid(
                state=state,
                kind="logo image",
                images_path=os.path.join(publisher.path(), "images"),
                get_images=publisher.all_images,
                get_selection=lambda : publisher.image,
                set_selection=publisher.set_image,
            )        
                
def view_pick_publisher(state):
    """
    View the publisher picker.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    from models.series import Series
    logger.debug("view_pick_publisher")

    # Dereference the state to get the selection and details.
    selection = state.get("selection")
    series_id = selection[-2].id
    series = Series.read(id=series_id)
    pub_id = selection[-1].id
    pub = Publisher.read(id=pub_id) if pub_id else None

    # Create a setter function for the publisher choice
    def set_publisher(publisher_id):
        if series is not None:
            series.publisher = publisher_id
            series.write()

    with state.get("details"):
        header("Pick a Publisher", 1)
    view_all_instances(
        state=state,
        get_instances=Publisher.read_all,
        kind="publisher",
        aspect_ratio="1/1",
        get_name=lambda i,x: x.name,
        get_choice=lambda : series.publisher if series else None,
        set_choice=set_publisher,
    )            

            
        
