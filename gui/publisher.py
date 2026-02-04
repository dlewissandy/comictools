import os
from loguru import logger
from typing import BinaryIO
from nicegui import ui
from gui.elements import header, crud_button, markdown_field_editor, full_width_image_selector_grid, view_all_instances, view_attributes, Attribute, CrudButtonKind
from gui.messaging import post_user_message
from gui.state import APPState
from storage.generic import GenericStorage
from schema import Publisher, Series


def view_publisher(state: APPState):
    """
    View the details of a publisher.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    storage = state.storage
    logger.debug("view_publisher")
    selection = state.selection
    publisher_id = selection[-1].id
    publisher = storage.read_object(Publisher, primary_key={"publisher_id": publisher_id}) if publisher_id else None
    details = state.details

    if publisher is None:
        details.clear()
        header(f"Publisher {publisher_id} not found", 0)
        return
    
    def set_image(image_id: str):
        """
        Set the image for the publisher.
        
        Args:
            image_id: The ID of the image to set.
        """
        publisher.image = image_id
        storage.update_object(data=publisher)

    def upload_image(name: str, data: BinaryIO, mime_type: str):
        """
        Upload an image for the publisher.
        
        Args:
            name: The name of the image.
            data: The binary data of the image.
            mime_type: The MIME type of the image.
        """
        # Create a new image in the storage
        file_locator = storage.upload_image(obj=publisher, name=name, data=data, mime_type=mime_type)
        # Set the image for the publisher
        publisher.image = file_locator
        storage.update_object(data=publisher)

    with details:
        # The title for the viewer is the Publisher name
        with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
            header(publisher.name.title(), 0)
            ui.space()
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, "I would like to delete the current publisher."),size=1)


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
                image_kind_name="logo image",
                get_images=lambda: storage.list_images(publisher),
                get_selection=lambda : publisher.image,
                set_selection=set_image,
                upload_image=upload_image
            )        
                
def view_pick_publisher(state:APPState):
    """
    View the publisher picker.
    
    Args:
        state: The GUI elements containing the details and selection.
    """
    storage: GenericStorage = state.storage
    logger.debug("view_pick_publisher")

    # Dereference the state to get the selection and details.
    selection = state.selection
    series_id = selection[-2].id
    series = storage.read_object(cls=Series, primary_key={"series_id": series_id}) if series_id else None
    pub_id = selection[-1].id
    pub = storage.read_object(cls=Publisher, primary_key={"publisher_id": pub_id}) if pub_id else None

    # Create a setter function for the publisher choice
    def set_publisher(publisher_id):
        if series is not None:
            series.publisher_id = publisher_id
            storage.update_object(series)

    with state.details:
        header("Pick a Publisher", 1)

        view_all_instances(
            state=state,
            get_instances=lambda: storage.read_all_objects(cls=Publisher, order_by="name"),
            kind="publisher",
            aspect_ratio="1/1",
            get_name=lambda i,x: x.name,
            get_choice=lambda : series.publisher_id if series else None,
            set_choice=set_publisher,
            get_image_locator=lambda publisher: publisher.image,
        )            

            
        
