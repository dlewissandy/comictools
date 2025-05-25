import os
from typing import Optional, TypedDict
from loguru import logger
from typing import Callable
from nicegui import ui
from gui.constants import TAILWIND_CARD
from gui.messaging import post_user_message
from gui.state import GUIState
from gui.selection import SelectionItem, change_selection

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
}

CRUD_BUTTON_STYLES = {
     "1": "font-size: 1.25em; height: 1.25em; aspect-ratio: 1/1; padding: 0; line-height: inherit",
     "2": 'font-size: 1em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit'
}

def init_cardwall(columns: int = 4):
    return ui.element('div').classes(f'columns-{columns} w-full gap-2')

def crud_button(kind: str, action: Callable, size: int = 2):
    """Create a button with a specific style and action.

    Args:
        text (str): The text to display on the button.
        kind (str): The kind of action (e.g., 'create', 'read', 'update', 'delete').
        action (Callable): The function to call when the button is clicked.
    """
    if size not in [1, 2]:
        raise ValueError("Size must be 1 or 2.")
    if kind not in ['create', 'read', 'update', 'delete']:
        raise ValueError("Kind must be one of: create, read, update, delete.")
    
    button = ui.button(icon=CRUD_ICON[kind]).classes('text-base rounded-md').style(CRUD_BUTTON_STYLES[str(size)])
    button.on('click', action)
    return button

def markdown_field_editor(state: GUIState, name: str, value: str | None):
    with ui.row().classes('w-full flex-nowrap'):
        header(name.title(),2)
        ui.space()
        if value is not None:
            crud_button(kind="update", action=lambda _: post_user_message(state, f"I would like to edit the {name}"))
            crud_button(kind="delete", action=lambda _: post_user_message(state, f"I would like to delete the {name}."))
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
     return ui.label(text).style(HEADER_STYLES[level])

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

def full_width_image_selector_grid(state: GUIState, kind: str, images_path: str, get_images, get_selection, set_selection, title: str = "IMAGES" ):
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
    def render_image_cards(state, get_images, get_selection, set_selection, cardwall):
        all_images = get_images()
        with cardwall:
            for image in all_images:
                def on_click(image: str):
                    set_selection(image)
                    cardwall.clear()
                    render_image_cards(state, get_images=get_images, get_selection=get_selection, set_selection=set_selection, cardwall=cardwall)


                card = ui.card().classes(TAILWIND_CARD).style('aspect-ratio: 1/1').on('click', lambda _,image=image: on_click(image))       
                card.classes('relative overflow-visible')
                with card:
                    header(image,4)
                    image_filepath = os.path.join(images_path, f"{image}.jpg")
                    logger.debug(f"image_filepath: {image_filepath}")
                    if os.path.exists(image_filepath):
                        ui.image(source=image_filepath).style('top-padding: 0; bottom-padding:0')
                        if image == get_selection(None):
                            ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10').style('aspect-ratio: 1/1;')
                    else:
                        ui.label(f"Image {image} not found.").style('color: red;')

    with ui.row().classes('w-full flex-nowrap'):
        header(f"Images",2)
        ui.space()
        crud_button(kind="create", action = lambda _: post_user_message(state, f"I would like to render the {kind}."))

    all_images = get_images()
    logger.debug(f"all_images: {all_images}")
    
    cardwall = init_cardwall()
    render_image_cards(
            state=state, 
            get_images=get_images,
            get_selection=get_selection,
            set_selection=set_selection,
            cardwall=cardwall
        )        

def image_field_editor(state: GUIState, kind, caption, get_name, get_id, get_image_filepath, aspect_ratio: str = "1/1"):
    with ui.row().classes('w-full flex-nowrap'):
        value = get_name()
        id = get_id()
        image_filepath = get_image_filepath()
        header(caption.title(),2)
        ui.space()
        if value is not None:
            crud_button(kind="delete", action=lambda _: post_user_message(state, f"I would like to delete the {caption}."))
        else:
            crud_button(kind="create", action = lambda _: post_user_message(state, f"I would like to add a {caption}."))


    card = ui.card().classes(TAILWIND_CARD).style(f'aspect-ratio: {aspect_ratio}')
    with card:
        if value is not None and value !="":
            header(value,4)
            if os.path.exists(image_filepath):
                ui.image(source=image_filepath).style('top-padding: 0; bottom-padding:0')
            else:
                ui.label(f"Image {value} not found.").style('color: red;')
        else:
            ui.label(f"No image available.")
    new_itm = SelectionItem(name=kind.replace('-',' ').title(), id=id, kind=kind)
    new_sel = [s for s in state.get("selection")]+[new_itm]
    card.on('click', lambda _, new_sel=new_sel: change_selection(state, new=new_sel))

def render_object_choices(state, instances, get_selection, set_selection, cardwall, aspect_ratio: str = "1/1", get_name: Callable = lambda i,x: x.name):
    with cardwall:
        for i,instance in enumerate(instances):
            def on_click(id: str):
                set_selection(id)
                cardwall.clear()
                render_object_choices(state, instances=instances, get_selection=get_selection, set_selection=set_selection, cardwall=cardwall)
            
            card = ui.card().classes(TAILWIND_CARD).style('aspect-ratio: 1/1').on('click', lambda _,id=instance.id: on_click(id=id))       
            card.classes('relative overflow-visible')
            with card:
                header(get_name(i,instance),4)
                image_filepath = instance.image_filepath()
                if os.path.exists(image_filepath):
                    ui.image(source=image_filepath).style('top-padding: 0; bottom-padding:0')
                    if instance.id == get_selection():
                        ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10').style('aspect-ratio: 1/1;')
                else:
                    ui.label(f"Image {image_filepath} not found.").style('color: red;')


def render_object_cards(state: GUIState, instances, kind: str | Callable, cardwall, aspect_ratio: str = "1/1", get_name: Callable = lambda i,x: x.name, get_markdown: Optional[Callable] = None, number_of_columns: int = 4):
    selection = state.get("selection")
    with ui.element().classes(f'grid grid-cols-{number_of_columns} gap-2 w-full'):
        for i,instance in enumerate(instances):
            name = get_name(i,instance)
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
            card.on('click', lambda _, new_sel=new_sel: change_selection(state, new_sel))


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
    selection = state.get("selection")
    with state.get("details"):
            if get_choice is not None:
                render_object_choices(
                    state=state, 
                    instances=instances, 
                    get_name=get_name,
                    get_selection=get_choice, 
                    set_selection=set_choice, 
                    cardwall=init_cardwall(), 
                    aspect_ratio=aspect_ratio
                )
            else:
                render_object_cards(
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


def view_attributes(state: GUIState, caption: str, attributes: list[Attribute] ):
    
    with ui.expansion().classes('w-full').classes('border border-gray-300 dark:border-gray-700 rounded-md bg-gray-100 dark:bg-gray-800') as expansion:
        with expansion.add_slot('header'):
            header(caption, 2)
        with ui.grid(rows=len(attributes), columns=3).style('grid-template-columns: auto auto auto;'):
            for attr in attributes:
                caption = attr["caption"]
                value = attr.get("get_value")()
                ui.button(icon='edit').classes('text-base rounded-md').style('font-size: 0.75em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit').on('click', lambda _: post_user_message(state, f"I would like to edit the {caption} date."))
                header(caption,4)
                value = attr.get("get_value")()
                if value is None: 
                    value = ""
                ui.label(value)