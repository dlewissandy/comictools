import os
from typing import Optional, TypedDict
from loguru import logger
from typing import Callable
from nicegui import ui
from nicegui.events import UploadEventArguments
from gui.constants import TAILWIND_CARD
from gui.messaging import post_user_message
from gui.state import APPState
from gui.selection import SelectionItem
from models.panel import FrameLayout

HEADER_STYLES = {
    0: 'font-size: 3rem; font-weight: bold;',
    1: 'font-size: 2.5rem; font-weight: bold;',
    2: 'font-size: 2rem; font-weight: bold;',
    3: 'font-size: 1.5rem; font-weight: bold;',
    4: 'font-size: 1rem; font-weight: bold;',
    5: 'font-size: 0.75rem; font-weight: bold;',
}

CRUD_ICON = {
    'create': 'add',
    'read': 'sync',
    'update': 'edit',
    'delete': 'delete',
    'render': 'brush'
}

DARK_MODE_STYLES = "border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800"

CRUD_BUTTON_STYLES = {
     "1": "font-size: 1.25em; height: 1.25em; aspect-ratio: 1/1; padding: 0; line-height: inherit",
     "2": 'font-size: 1em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit'
}

def init_cardwall(columns: int = 4):
    return ui.element('div').classes(f'columns-{columns} w-full gap-2 ')

def crud_button(kind: str, action: Callable, size: int = 2):
    """Create a button with a specific style and action.

    Args:
        text (str): The text to display on the button.
        kind (str): The kind of action (e.g., 'create', 'read', 'update', 'delete').
        action (Callable): The function to call when the button is clicked.
    """
    if size not in [1, 2]:
        raise ValueError("Size must be 1 or 2.")
    if kind not in CRUD_ICON.keys():
        raise ValueError("Kind must be one of: create, read, update, delete.")
    
    button = ui.button(icon=CRUD_ICON[kind]).classes('text-base rounded-md').style(CRUD_BUTTON_STYLES[str(size)])
    button.on('click', action)
    return button

def markdown_field_editor(state: APPState, name: str, value: str | None, header_size: int = 2):
    with ui.row().classes('w-full flex-nowrap'):
        header(name.title(),header_size)
        ui.space()
        if value is not None:
            crud_button(kind="update", action=lambda _: post_user_message(state, f"I would like to edit the {name}"))
        else:
            crud_button(kind="create", action = lambda _: post_user_message(state, f"I would like to add a {name}."))

    if value is not None and value !="":
        markdown(value)
     

def header(text: str, level: int = 1) -> None:
     """Create a label with a specific style

        Args:
            text (str): The text to display.
            level (int): The header level (0-5).  Larger numbers are smaller headers.
    """
     if level < 0 or level > 5:
        raise ValueError("Header level must be between 0 and 5.")
     return ui.label(text).style(HEADER_STYLES[level]).style('margin-top: 0px; margin-bottom: 0px')

def markdown(body: str) -> None:
    with ui.element().classes('w-full q-pa-md'):
            # Add custom CSS to ensure markdown content wraps properly
            ui.add_head_html('''
                <style>
                    .markdown-content {
                        width: 100%;
                        max-width: 100%;
                        overflow-wrap: break-word;
                        word-wrap: break-word;
                        word-break: normal;
                        hyphens: auto;
                    }
                    .markdown-content * {
                        white-space: normal !important;
                        max-width: 100%;
                    }
                    .markdown-content pre {
                        white-space: pre-wrap !important;
                        max-width: 100%;
                        overflow-x: auto;
                    }
                    .markdown-content code {
                        white-space: pre-wrap !important;
                    }
                    .markdown-content p, .markdown-content li {
                        overflow-wrap: break-word;
                        word-wrap: break-word;
                        word-break: normal;
                    }
                </style>
            ''')
            
            # Apply the custom class to the markdown container
            with ui.element('div').classes('markdown-content'):
                ui.markdown(body)

def full_width_image_selector_grid(state: APPState, kind: str, images_path: str, get_images, get_selection, set_selection, aspect_ratio="1/1", caption: str = "Images", columns: int = 4, header_size: int = 2):
    """
    Create a grid of full-width image selectors.

    Args:
        state: The GUI elements containing the details and selection.
        kind: The kind of images (e.g., 'publisher', 'series', 'logo').
        images_path: The path where the images are stored.
        get_images: A function to get the list of images.
        get_selection: A function to get the current selection.
        set_selection: A function to set the current selection.
        title: The title for the image selector grid.
    """
    def on_upload(e: UploadEventArguments):
            if e.name and e.type.startswith('image/'):
                file_name = e.name
                save_filepath = os.path.join(images_path, file_name)
                # recursively create the directory if it doesn't exist
                os.makedirs(images_path, exist_ok=True)
                
                with open(save_filepath, 'wb') as f:
                    f.write(e.content.read())
                logger.debug(f"Saved uploaded file to {save_filepath}")
                set_selection(file_name[:-4])  # Remove file extension for selection
                cardwall.clear()
                render_image_cards(state, get_images=get_images, get_selection=get_selection, set_selection=set_selection, cardwall=cardwall, aspect_ratio=aspect_ratio)

    def render_image_cards(state, get_images, get_selection, set_selection, cardwall, aspect_ratio="1/1"):
        all_images = get_images()
        with cardwall:
            for image in all_images:
                def on_click(image: str):
                    set_selection(image)
                    cardwall.clear()
                    render_image_cards(state, get_images=get_images, get_selection=get_selection, set_selection=set_selection, cardwall=cardwall, aspect_ratio=aspect_ratio)


                card = ui.card().classes(TAILWIND_CARD).style(f'aspect-ratio: {aspect_ratio}').on('click', lambda _,image=image: on_click(image))       
                card.classes('relative overflow-visible')
                with card:
                    # if it is a full path, then use it as, else construct a filepath
                    if image.startswith(images_path):
                        image_filepath = image
                    else:
                        image_filepath = os.path.join(images_path, f"{image}.jpg")
                    logger.critical(f"image_filepath: {image_filepath}")
                    current_selection = get_selection()
                    if os.path.exists(image_filepath):
                        logger.debug(f"Image {image} exists at {image_filepath}")
                        ui.image(source=image_filepath).style(f'top-padding: 0; bottom-padding:0; aspect-ratio: {aspect_ratio};')
                        if image == current_selection:
                            ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10').style('aspect-ratio: 1/1;')
                    else:
                        ui.label(f"Image {image} not found.").style('color: red;')
            with ui.card().classes(TAILWIND_CARD + ' relative overflow-hidden').style(f'aspect-ratio: {aspect_ratio}'):
                uploader = ui.upload(on_upload=on_upload, auto_upload=True, max_files=1)
                uploader.classes('absolute inset-0 opacity-0 cursor-pointer z-10')

                # Visible caption in center
                with ui.row().classes('absolute inset-0 flex items-center justify-center z-0'):
                    ui.label('Drop image to upload').classes('text-lg text-gray-600')

    with ui.row().classes('w-full flex-nowrap').style('padding-left: 2ex; padding-right: 2ex;'):
        header(caption,header_size)
        ui.space()
        crud_button(kind="render", action = lambda _: post_user_message(state, f"I would like to render the {kind}."))
        crud_button(kind="delete", action=lambda _: post_user_message(state, f"I would like to delete the currently selected {kind}."))

    all_images = get_images()
    logger.debug(f"all_images: {all_images}")
    
    cardwall = init_cardwall(columns=columns)
    render_image_cards(
            state=state, 
            get_images=get_images,
            get_selection=get_selection,
            set_selection=set_selection,
            cardwall=cardwall,
            aspect_ratio=aspect_ratio
        )     

def image_field_editor(
        state: APPState, 
        kind: str, 
        get_caption: Callable[[], str|None], 
        get_id: Callable[[], str|None], 
        get_image_filepath: Callable[[], str|None], 
        aspect_ratio: str = "1/1",
        caption_size: int = 2
        ) -> ui.element:
        
    """
    Display a field by a representative image.

    Args:
        state: The GUI elements containing the details and selection.
        kind: The kind of image (e.g., 'publisher', 'series', 'logo').
        get_caption: A function to get the caption of the item.
        get_id: A function to get the ID of the item.
        get_image_filepath: A function to get the file path of the image.
        aspect_ratio: The aspect ratio of the image (default is "1/1").

    """
    caption = get_caption()
    id = get_id()
    image_filepath = get_image_filepath()

    with ui.row().classes('w-full flex-nowrap') as row:
        with ui.card().classes(TAILWIND_CARD+ " w-24%").style(f'aspect-ratio: {aspect_ratio}') as card:
            if caption is not None and caption !="":
                header(caption,2)
            if image_filepath is None:
                ui.label(f"Click to select").classes('text-gray-500').style('text-align: center;')
            elif not os.path.exists(image_filepath):
                ui.label(f"Image for {caption} not found.").style('color: red;')
            else:
                ui.image(source=image_filepath).style('top-padding: 0; bottom-padding:0')
        new_itm = SelectionItem(name=kind.replace('-',' ').title(), id=id, kind=kind)
        new_sel = [s for s in state.selection]+[new_itm]
        card.on('click', lambda _, new_sel=new_sel: state.change_selection(new=new_sel))

        return row

def render_object_choices(state, instances, get_selection, set_selection, cardwall, aspect_ratio: str = "1/1", get_name: Callable = lambda i,x: x.name, number_of_columns: int = 4):    
    """
    Render a list of choices for a given object type.   Clicking on a choice will set the selection to that choice.

    Args:
        state: The application state
        instances: The list of instances to render
        get_selection: A function to get the current selection
        set_selection: A function to set the current selection
        cardwall: The cardwall to render the choices in
        aspect_ratio: The aspect ratio of the cards
        get_name: A function to get the name of an instance
    """
    logger.trace("render_object_choices")

    def on_click(id: str):
        # set the selection to the clicked item
        set_selection(id)
        cardwall.clear()
        render_object_choices(state, instances=instances, get_selection=get_selection, set_selection=set_selection, cardwall=cardwall)

    logger.debug([instance.name for instance in instances])
    with cardwall:
        for i,instance in enumerate(instances):
            logger.debug(f"Rendering card for {instance.name} with id {instance.id}")
            with ui.card().classes(TAILWIND_CARD).style('aspect-ratio: 1/1').on('click', lambda _,id=instance.id: on_click(id=id)) as card:
                logger.debug(f"Creating card for {instance.id}")
                card.classes('relative overflow-visible')
                header(get_name(i,instance),4)
                image_filepath = instance.image_filepath()
                if image_filepath is not None and os.path.exists(image_filepath):
                    logger.debug(f"Image {image_filepath} exists.")
                    ui.image(source=image_filepath).style('top-padding: 0; bottom-padding:0')
                    logger.debug(f"instance.id={instance.id}, get_selection()={get_selection()}")
                else:
                    logger.debug(f"Image {image_filepath} does not exist.")
                    ui.label(f"Image {image_filepath} not found.").style('color: red;')
                if instance.id == get_selection():
                    logger.debug(f"Image {image_filepath} is selected.")
                    ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10').style('aspect-ratio: 1/1;')
                else:
                    logger.debug(f"Image {image_filepath} is not selected.")
                
    return cardwall


def render_object_cards(state: APPState, instances, kind: str | Callable, cardwall, aspect_ratio: str = "1/1", get_name: Callable = lambda i,x: x.name, get_markdown: Optional[Callable] = None, number_of_columns: int = 4):
    selection = state.selection
    with ui.element().classes(f'grid grid-cols-{number_of_columns} gap-2 w-full') as grid:
        for i,instance in enumerate(instances):
            name = get_name(i,instance)
            logger.debug(f"Rendering card for {name} with kind {kind}")
            id = instance.id
            logger.debug(f"Creating card for {id}")
            card = ui.card().classes(TAILWIND_CARD).style(f'aspect-ratio: {aspect_ratio}')
            with card:
                if callable(kind):
                    kind_value = kind(instance)
                else:
                    kind_value = kind
                sel_itm = SelectionItem(name=name, id=id, kind=kind_value)
                new_sel = [s for s in selection]+[sel_itm]
                image = instance.image_filepath()
                header(name,4)
                if image:
                    ui.image(source=image).style('top-padding: 0; bottom-padding:0')
                else:
                    if get_markdown is None:
                        header("No image available",5)
                    else:
                        markdown(get_markdown(instance))
                
            # Fix lambda by creating a closure with the current value of new_sel
            card.on('click', lambda _, new_sel=new_sel: state.change_selection( new_sel, clear_history=False))
    return grid


def view_all_instances(
        state, 
        get_instances, 
        kind: str | Callable,  
        get_name = lambda i,x: x.name, 
        get_choice: Optional[Callable] = None, 
        set_choice: Optional[Callable] = None, 
        get_markdown: Optional[Callable] = None,
        number_of_columns: int=4,
        aspect_ratio: str = "1/1"): 
    """
    A gui shortcut to view all the instances of a given kind.

    clicking on an instance will change the selection to that instance.
    Args:
        state: The GUI elements containing the details and selection.
        get_instances: A function to get the list of instances.
        get_choice: A function to get the current choice (optional).
        set_choice: A function to set the current choice (optional).  This function should take a single
           argument, which is the chosen value.  It should change the badge to the chosen value and then
           update the parent object with the new choice.
        get_markdown: A function to get the markdown content for the instance (optional).  This is displayed
           when there is no image.
        kind: The kind of instances (e.g., 'character', 'issue', 'series').

    NOTE: Each instance should have the following properties
        - name: The name of the instance.
        - id: The ID of the instance.
        - image_filepath: A function that returns the file path of the instance's image.

    """
    logger.debug("view_all_instances")

    # Sanity checks
    if not callable(get_instances):
        raise ValueError("get_instances must be a callable function that returns a list of instances.")
    if get_choice is not None and not callable(get_choice):
        raise ValueError("get_choice must be a callable function that returns the current choice.")
    if set_choice is not None and not callable(set_choice):
        raise ValueError("set_choice must be a callable function that sets the current choice.")
    if set_choice is not None and get_choice is None:
        raise ValueError("If set_choice is provided, get_choice must also be provided.")
    if get_choice is not None and set_choice is None:
        raise ValueError("If get_choice is provided, set_choice must also be provided.")

    # get the instances
    logger.debug("Fetching instances")
    instances = get_instances()

    # Render the details with all the available choices
    if get_choice is not None:
        return render_object_choices(
            state=state, 
            instances=instances, 
            get_name=get_name,
            get_selection=get_choice, 
            set_selection=set_choice, 
            cardwall=init_cardwall(), 
            aspect_ratio=aspect_ratio
        )
    else:
        return render_object_cards(
            state=state, 
            instances=instances, 
            get_name=get_name,
            get_markdown=get_markdown,
            kind=kind, 
            cardwall=init_cardwall(), 
            number_of_columns=number_of_columns,
            aspect_ratio=aspect_ratio
        )

class Attribute(TypedDict):
    caption: str
    get_value: str | Callable


def view_attributes(state: APPState, caption: str, attributes: list[Attribute], expanded: bool=False, individual_icons: bool = True, header_size: int=1):
    with ui.element().classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as container:
        with ui.expansion( value=expanded ).classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
            with expansion.add_slot('header'):
                header(caption, header_size)
                if not individual_icons:
                    ui.space()
                    crud_button(kind="update", action=lambda _: post_user_message(state, f"I would like to edit the {caption}."))
                    cols = 2
                    col_style = 'grid-template-columns: auto auto;'
                else:
                    cols = 3
                    col_style = 'grid-template-columns: auto auto auto;'
            with ui.grid(rows=len(attributes), columns=cols).style(col_style):
                for attr in attributes:
                    attr_name = attr["caption"]
                    value = attr.get("get_value")()
                    if individual_icons:
                        ui.button(icon='edit').classes('text-base rounded-md').style('font-size: 0.75em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit').on('click', lambda _: post_user_message(state, f"I would like to edit the {caption} date."))
                    header(attr_name,4)
                    value = attr.get("get_value")()
                    if value is None: 
                        value = ""
                    ui.label(value)
    return container


def image_drop_field_editor(
        state: APPState,
        caption: str, 
        kind: str,
        get_image_filepath: Callable[[], str | None] = lambda: None,
        on_upload: Callable[[UploadEventArguments], None] = lambda _: None,
        aspect_ratio: str = "3/2",
        width: str = "full", 
    ):
    """
    A field editor for uploading an image.
    Args:
        state: The GUI elements containing the details and selection.
        caption: The caption for the image field.
        kind: The kind of image (e.g., 'publisher', 'series', 'logo').
        on_upload: A function to call when an image is uploaded.
        aspect_ratio: The aspect ratio of the image (default is "3/2").
        width: The width of the image field (default is "full").
    """
    with ui.card().classes(TAILWIND_CARD).classes(f'w-{width} relative overflow-hidden').style(f'aspect-ratio: {aspect_ratio}') as card:
        uploader = ui.upload(on_upload=on_upload, auto_upload=True, max_files=1)
        uploader.classes('absolute inset-0 opacity-0 cursor-pointer z-10')

        # Visible caption in center
        with ui.row().classes('absolute inset-0 flex items-center justify-center z-0'):
            ui.label('Drop image to upload').classes('text-lg text-gray-600')


def view_image_choices(
    state: APPState,
    kind: str,
    images_path: str,
    get_images: Callable[[], list[str]],
    get_selection: Callable[[], list[str]],
    set_selection: Callable[[str], None],
): 
    """
    """
    details = state.details
    state.clear_details()
    with details:
        with ui.row():
            header(1, f"Select {kind.title()} Image")
            ui.space()
            ui.button(icon="add").tooltip("Generate a new image")
        full_width_image_selector_grid(
            state=state,
            kind=kind,
            images_path=images_path,
            get_images=get_images,
            get_selection=get_selection,
            set_selection=set_selection,

        )

    

def aspect_ratio_picker(state: APPState, parent: ui.element, caption: str, get_aspect_ratio: Callable[[], str], set_aspect_ratio: Callable[[FrameLayout], None]):
    """
    A field editor for selecting an aspect ratio.
    Args:
        state: The GUI elements containing the details and selection.
        caption: The caption for the aspect ratio field.
        get_aspect_ratio: A function to get the current aspect ratio.
        set_aspect_ratio: A function to set the current aspect ratio.
    """
    raw_value:FrameLayout = get_aspect_ratio()
    text = raw_value.value.lower().replace("_", " ")
    logger.debug(f"value={text}")

    def on_click(value: FrameLayout):
        select.text = value.value.lower().replace("_", " ")
        set_aspect_ratio(value)

    with parent:
        header(caption,2)
        with ui.dropdown_button(text=text, auto_close=True).style('width: 100%;') as select:
            landscape = ui.item("landscape")
            portrait = ui.item("portrait")
            square = ui.item("square")

    landscape.on_click(lambda _: on_click(FrameLayout.LANDSCAPE))
    portrait.on_click(lambda _: on_click(FrameLayout.PORTRAIT))
    square.on_click(lambda _: on_click(FrameLayout.SQUARE))
    
    
