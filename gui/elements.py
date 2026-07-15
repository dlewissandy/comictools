import os
import contextlib
from typing import Optional, TypedDict, Callable
from nicegui import ui
from nicegui.events import UploadEventArguments
from gui.constants import TAILWIND_CARD
from gui.messaging import post_user_message
from gui.state import APPState
from gui.selection import SelectionItem, SelectedKind
from pydantic import BaseModel
from loguru import logger
from enum import StrEnum

# Comic type scale: 0-1 display lettering, 2-3 narrator caption boxes,
# 4-5 small production labels.  Styled centrally in main.py's CSS.
HEADER_CLASSES = {
    0: 'comic-title',
    1: 'comic-title comic-title-sm',
    2: 'caption-box',
    3: 'caption-box caption-box-sm',
    4: 'comic-label',
    5: 'comic-label comic-label-sm',
}

class CrudButtonKind(StrEnum):
    """Enum for the kinds of CRUD buttons."""
    CREATE = 'create'
    READ = 'read'
    UPDATE = 'update'
    DELETE = 'delete'
    RENDER = 'render'

CRUD_ICON = {
    'create': 'add',
    'read': 'sync',
    'update': 'edit',
    'delete': 'delete',
    'render': 'brush'
}

DARK_MODE_STYLES = "soft-card"

CRUD_BUTTON_STYLES = {
     "1": "font-size: 1.25em; height: 1.25em; aspect-ratio: 1/1; padding: 0; line-height: inherit; margin: 0;",
     "2": 'font-size: 1em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit; margin: 0;',
     "3": 'font-size: 0.75em; height: 1em; aspect-ratio: 1/1; padding: 0; line-height: inherit; margin: 0;'
}

_GRID_MIN = {2: '300px', 3: '230px', 4: '180px'}

def init_cardwall(columns: int = 4):
    return ui.element('div').classes('w-full').style(
        f"display: grid; grid-template-columns: repeat(auto-fill, minmax({_GRID_MIN.get(columns, '180px')}, 1fr)); gap: 10px;")

def swatch_rack(items, on_pick, *, width: int = 130, img_h: int = 70,
                fit: str = 'contain', empty_text: str | None = None):
    """A RACK OF SWATCHES: the one look for every picker's card grid —
    (label, image, payload) in, a click out.  Sites with per-card extras
    keep bespoke loops; everything plain rides this."""
    with ui.row().classes('w-full q-mt-sm').style('gap: 8px;'):
        if not items and empty_text:
            ui.label(empty_text).classes('text-sm text-gray-500')
        for label, img, payload in items:
            with ui.card().classes('soft-card p-1 cursor-pointer') \
                    .style(f'width: {width}px;') as card:
                if img and os.path.exists(img):
                    ui.image(source=img).style(f'height: {img_h}px;').props(f'fit={fit}')
                ui.label(label).classes('text-xs text-center w-full')
            card.on('click', lambda _, pl=payload: on_pick(pl))


async def confirm_dialog(title: str, body: str, *, go_label: str,
                         go_icon: str = 'check', keep_label: str = 'Keep it',
                         danger: bool = True) -> bool:
    """THE ONE CONFIRM: friction proportional to irreversibility — a plain
    question, the safe door first, the destructive verb wearing its color.
    Awaitable: True when the author says go."""
    from gui.elements import studio_dialog
    with studio_dialog(title, min_w=440) as dlg:
        ui.label(body).classes('text-sm q-mt-sm')
        with ui.row().classes('w-full justify-end q-mt-sm').style('gap: 8px;'):
            ui.button(keep_label).props('flat dense no-caps') \
                .on('click', lambda _: dlg.submit(False))
            ui.button(go_label, icon=go_icon, color='negative' if danger else None) \
                .props('unelevated dense no-caps') \
                .on('click', lambda _: dlg.submit(True))
    dlg.open()
    return bool(await dlg)


@contextlib.contextmanager
def studio_dialog(title: str, *, min_w: int = 420, max_w: int | None = None,
                  scroll: bool = False):
    """THE ONE DIALOG SHELL: studio paper, a caption-box title and, with
    scroll=True, a bounded body (84vh) that keeps every option reachable
    in a short window.  Yields the dialog; the caller fills the body and
    opens it — exactly the hand-rolled shape it replaces, in one hand."""
    style = f'min-width: {min_w}px;'
    if max_w:
        style += f' max-width: {max_w}px;'
    if scroll:
        style += ' max-height: 84vh; display: flex; flex-direction: column;'
    with ui.dialog() as dlg:
        with ui.card().classes('soft-card').style(style):
            ui.label(title).classes('caption-box caption-box-sm')
            if scroll:
                with ui.element('div').classes('w-full q-mt-sm') \
                        .style('overflow-y: auto; min-height: 0; flex: 1;'):
                    yield dlg
            else:
                yield dlg


def crud_button(kind: CrudButtonKind, action: Callable, size: int = 2):
    """Create a button with a specific style and action.

    Args:
        text (str): The text to display on the button.
        kind (str): The kind of action (e.g., 'create', 'read', 'update', 'delete').
        action (Callable): The function to call when the button is clicked.
    """
    if size not in [1, 2]:
        raise ValueError("Size must be 1 or 2.")

    # THE NARRATOR-BOX GLYPH, not a chunky blue slab: a small flat inked
    # icon button, the same hand as the caption boxes' + and ✏️ glyphs
    button = ui.button(icon=CRUD_ICON[kind.value]) \
        .props('flat round dense size=' + ('md' if size == 1 else 'sm')) \
        .classes('crud-glyph')
    button.on('click', action)
    return button

def caption_action(text: str, kind: CrudButtonKind, action: Callable, level: int = 2):
    """
    A narrator box with its action INSIDE it — the button is part of the
    caption, a printed glyph in the box, not chrome floating beside it.
    """
    with ui.element('div').classes(HEADER_CLASSES[min(level, 3)] + ' caption-flex') as box:
        ui.label(text)
        ui.button(icon=CRUD_ICON[kind.value]).props('flat round dense size=sm') \
            .classes('caption-btn').on('click.stop', action)
    return box


def markdown_field_editor(state: APPState, name: str, value: str | None, header_size: int = 2):
    with ui.row().classes('w-full flex-nowrap').style('padding: 0; margin: 0;'):
        if value is not None:
            caption_action(name.title(), CrudButtonKind.UPDATE,
                           lambda _: post_user_message(state, f"I would like to edit the {name}"), header_size)
        else:
            caption_action(name.title(), CrudButtonKind.CREATE,
                           lambda _: post_user_message(state, f"I would like to add a {name}."), header_size)

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
     return ui.label(text).classes(HEADER_CLASSES[level]).style('margin-top: 0px; margin-bottom: 0px')

def markdown(body: str) -> None:
    """Markdown content that wraps properly — the stylesheet rides in
    main.py's one head include, not a per-call injection."""
    with ui.element().classes('w-full q-pa-md'):
        ui.markdown(body).classes('w-full markdown-content')


def full_width_image_selector_grid(
    state: APPState,
    image_kind_name: str,
    upload_image: Callable,
    get_images: Callable[[], list[str]],
    get_selection: Callable[[], str],
    set_selection: Callable[[str], None],
    aspect_ratio="1/1",
    caption: str = "Images",
    columns: int = 4,
    header_size: int = 2,
    include_delete_button: bool = True,
    include_render_button: bool = True,
    include_edit_button: bool = True,
    uploader: Optional[Callable[[UploadEventArguments], None]] = None,
    ):
    """
    Create a grid of full-width image selectors.

    Args:
        state: The GUI elements containing the details and selection.
        kind: The kind of images (e.g., 'publisher', 'series', 'logo').
        get_images: A function to get the list of image locators.
        get_selection: A function to get image locator of the current selection.
        set_selection: A function to set the current selection.
        title: The title for the image selector grid.
    """
    def on_upload(e: UploadEventArguments):
            if e.name and e.type.startswith('image/'):
                name = e.name
                data = e.content
                mime_type = e.type
                locator = upload_image(name, data, mime_type)
                set_selection(locator)
                cardwall.clear()
                render_image_cards(state, get_images=get_images, get_selection=get_selection, set_selection=set_selection, cardwall=cardwall, aspect_ratio=aspect_ratio)

    if not uploader:
        uploader = on_upload

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
                    current_selection = get_selection()
                    if os.path.exists(image):
                        ui.image(source=image).style(f'top-padding: 0; bottom-padding:0; aspect-ratio: {aspect_ratio};')
                        if image == current_selection:
                            ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10').style('aspect-ratio: 1/1;')
                    else:
                        ui.label(f"Image {image} not found.").style('color: red;')
            uploader_card(
                state=state, 
                on_upload=uploader, 
                aspect_ratio=aspect_ratio
            )

    with ui.row().classes('w-full flex-nowrap').style('padding-left: 2ex; padding-right: 2ex;'):
        header(caption,header_size)
        ui.space()
        if include_edit_button:
            def open_editor():
                image_locator = get_selection()
                if not image_locator:
                    ui.notify("Select an image to edit first.", type="warning")
                    return
                new_itm = SelectionItem(
                    name=f"Edit {image_kind_name.title()}",
                    id=image_locator,
                    kind=SelectedKind.IMAGE_EDITOR
                )
                state.change_selection(new=[*state.selection, new_itm])
            crud_button(kind=CrudButtonKind.UPDATE, action=lambda _: open_editor())
        if include_render_button:
            crud_button(kind=CrudButtonKind.RENDER, action = lambda _: post_user_message(state, f"I would like to render the {image_kind_name}."))
        if include_delete_button:
            crud_button(kind=CrudButtonKind.DELETE, action=lambda _: post_user_message(state, f"I would like to delete the currently selected {image_kind_name}."))

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

def render_object_choices(
        state: APPState, 
        instances: list[BaseModel], 
        get_image_locator: Callable[[BaseModel], Optional[str]],
        get_selection: Callable[[],str], 
        set_selection: Callable[[str],None], 
        cardwall: ui.element, 
        aspect_ratio: str = "1/1",
        get_name: Callable = lambda i,x: x.name,
        number_of_columns: int = 4,
        variants: Optional[list[tuple[float, float]]] = None):
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
        render_object_choices(
            state=state, 
            instances=instances, 
            get_image_locator=get_image_locator,
            get_selection=get_selection, 
            set_selection=set_selection,
            cardwall=cardwall,
            aspect_ratio=aspect_ratio,
            number_of_columns=number_of_columns,
            get_name=get_name,
            variants=variants,
            )

    def _choice_card(i, instance, packed: bool):
        card = ui.card().classes(TAILWIND_CARD).on('click', lambda _, id=instance.id: on_click(id=id))
        if packed:
            card.classes('mosaic-card')
        else:
            card.style('aspect-ratio: 1/1')
        with card:
            card.classes('relative overflow-visible')
            image_filepath = get_image_locator(instance)
            has_image = image_filepath is not None and os.path.exists(image_filepath)
            if has_image:
                ui.label(get_name(i, instance)).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                ui.image(source=image_filepath).props('fit=contain').style('top-padding: 0; bottom-padding:0')
            else:
                header(get_name(i, instance), 4)
                ui.label('no artwork yet').classes('text-xs text-gray-500')
            if instance.id == get_selection():
                ui.badge('✓', color='green').props('floating').classes('absolute top-0 right-0 z-10').style('aspect-ratio: 1/1;')

    with cardwall:
        if variants:
            # THE RULED PAGE: choices pack into blocks like any other panels
            with ruled_page() as packer:
                for i, instance in enumerate(instances):
                    with packer.place_cell(list(variants), fudge=False):
                        _choice_card(i, instance, packed=True)
        else:
            for i, instance in enumerate(instances):
                _choice_card(i, instance, packed=False)
    return cardwall


def render_object_cards(
        state: APPState, 
        instances: list[BaseModel], 
        kind: SelectedKind | Callable, # TODO: Do I use both Callable and literal?   Simplify?
        cardwall: ui.element, 
        aspect_ratio: str = "1/1",
        get_image_locator: Callable[[BaseModel], Optional[str]] = lambda x: x.image_filepath(),
        get_name: Callable[[int,BaseModel], str] = lambda i,x: x.name, 
        get_markdown: Optional[Callable] = None, 
        number_of_columns: int = 4,
        on_remove: Optional[Callable] = None,
        flow_span: Optional[int] = None,
        overlap_caption: Optional[Callable] = None,
        packer: Optional["PagePacker"] = None,
        variants: Optional[list[tuple[int, int]]] = None,
        card_overlay: Optional[Callable] = None):
    
    selection = state.selection
    if (packer is not None and variants) or flow_span:
        # PACKED/FLOW MODE: no private grid — every card cell is a DIRECT
        # child of the surrounding comic page, so its grid-area resolves
        # against the page's ruled units and groups pack together.
        grid = ui.element('div').classes('hidden')  # placeholder return
        container = None
    else:
        container = ui.element().classes('w-full').style(
            f"display: grid; grid-template-columns: repeat(auto-fill, minmax({_GRID_MIN.get(number_of_columns, '180px')}, 1fr)); gap: 10px;")
        grid = container
    import contextlib
    with (container if container is not None else contextlib.nullcontext()):
        for i,instance in enumerate(instances):
            name = get_name(i,instance)
            logger.debug(f"Rendering card for {name} with kind {kind}")
            id = instance.id
            logger.debug(f"Creating card for {id}")
            if packer is not None and variants:
                # THE RULED PAGE: the packer places this card left-to-right,
                # top-to-bottom, choosing among the card type's fixed sizes.
                # Only text callouts may be fudged taller — an art panel's
                # frame keeps its legal aspect, always.
                is_text = get_image_locator(instance) is None
                cell = packer.place_cell(variants, fudge=is_text)
            elif flow_span:
                cell = ui.element('div').classes(f'cspan-{flow_span}')
            else:
                cell = contextlib.nullcontext()
            with cell:
                card = ui.card().classes(TAILWIND_CARD)
                if (packer is not None and variants) or flow_span:
                    # frame fills its ruled region; art contains inside
                    card.classes('mosaic-card')
                else:
                    card.style(f'aspect-ratio: {aspect_ratio}')
            card.classes('relative overflow-visible')
            if i == 0 and overlap_caption is not None:
                # the group's narrator box overlaps its first panel, comic-style
                with card:
                    with ui.element('div').classes('panel-caption'):
                        overlap_caption()
            with card:
                if on_remove is not None:
                    def _detach(instance=instance, name=name):
                        try:
                            on_remove(instance)
                        except Exception as ex:
                            ui.notify(f"Couldn't remove {name}: {ex}", type='warning')
                            return
                        from gui.thread import thread_aside
                        thread_aside(state, f"✂️ removed **{name}**")
                        state.refresh_details()
                    ui.button(icon='close').props('flat round dense size=xs') \
                        .classes('absolute top-0 right-0 z-10 bg-white/70 dark:bg-black/50') \
                        .tooltip(f'Remove {name}') \
                        .on('click.stop', lambda _, inst=instance, n=name: _detach(inst, n))
                if callable(kind):
                    kind_value = kind(instance)
                else:
                    kind_value = kind
                sel_itm = SelectionItem(name=name, id=id, kind=kind_value)
                new_sel = [s for s in selection]+[sel_itm]
                image = get_image_locator(instance)
                if image:
                    # the panel is ALL art — the caption slides in on hover,
                    # so every frame stays a consistent ruled size
                    ui.label(name).classes(HEADER_CLASSES[3] + ' panel-hover-caption')
                    ui.image(source=image).props('fit=contain').style('top-padding: 0; bottom-padding:0')
                else:
                    header(name, 4)
                    if get_markdown is None:
                        ui.label('no artwork yet').classes('text-xs text-gray-500')
                    else:
                        markdown(get_markdown(instance)).classes('text-sm').style(
                            'display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;')
                if card_overlay is not None:
                    # per-card controls riding ON the art (reorder, copy, ...)
                    card_overlay(instance)
                
            # Fix lambda by creating a closure with the current value of new_sel
            card.on('click', lambda _, new_sel=new_sel: state.change_selection( new_sel))
        if not instances and overlap_caption is not None:
            if packer is not None:
                with packer.place_cell([(3, 1)], fudge=False).classes('flow-caption'):
                    overlap_caption()
            else:
                with (ui.element('div').classes(f'cspan-{flow_span} flow-caption') if flow_span
                      else contextlib.nullcontext()):
                    overlap_caption()
    return grid


def view_all_instances(
        state, 
        get_instances, 
        kind: SelectedKind | Callable,  # DO I use both Callable and literal?   Simplify?
        get_name = lambda i,x: x.name, 
        get_image_locator: Callable[[BaseModel], Optional[str]] = lambda x: x.image_filepath(),
        get_choice: Optional[Callable] = None, 
        set_choice: Optional[Callable] = None, 
        get_markdown: Optional[Callable] = None,
        number_of_columns: int=4,
        aspect_ratio: str = "1/1",
        on_remove: Optional[Callable] = None,
        flow_span: Optional[int] = None,
        overlap_caption: Optional[Callable] = None,
        packer: Optional["PagePacker"] = None,
        variants: Optional[list[tuple[int, int]]] = None,
        card_overlay: Optional[Callable] = None): 
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
            get_image_locator=get_image_locator,
            get_selection=get_choice, 
            set_selection=set_choice, 
            cardwall=ui.element('div').classes('w-full') if variants else init_cardwall(), 
            aspect_ratio=aspect_ratio,
            variants=variants
        )
    else:
        return render_object_cards(
            state=state, 
            instances=instances, 
            get_name=get_name,
            get_markdown=get_markdown,
            kind=kind, 
            cardwall=init_cardwall(),
            get_image_locator=get_image_locator, 
            number_of_columns=number_of_columns,
            aspect_ratio=aspect_ratio,
            on_remove=on_remove,
            flow_span=flow_span,
            overlap_caption=overlap_caption,
            packer=packer,
            variants=variants,
            card_overlay=card_overlay
        )

class Attribute(TypedDict, total=False):
    caption: str
    get_value: str | Callable
    set_value: Callable  # optional: enables inline editing of scalar fields


def view_attributes(state: APPState, caption: str, attributes: list[Attribute], expanded: bool=False, individual_icons: bool = True, header_size: int=1):
    with ui.element().classes('w-full') as container:
        with ui.expansion( value=expanded ).classes('w-full section-flat') as expansion:
            with expansion.add_slot('header'):
                if not individual_icons:
                    caption_action(caption, CrudButtonKind.UPDATE,
                                   lambda _: post_user_message(
                                       state, f"I would like to edit the {caption or 'details in this section'}."), header_size)
                    cols = 2
                    col_style = 'grid-template-columns: auto auto;'
                else:
                    header(caption, header_size)
                    cols = 3
                    col_style = 'grid-template-columns: auto auto auto;'
            with ui.grid(rows=len(attributes), columns=cols).style(col_style):
                for attr in attributes:
                    attr_name = attr["caption"]
                    value = attr.get("get_value")()
                    if individual_icons:
                        # the pencil edits THIS attribute — bound per row, not
                        # the section caption with a stray 'date' bolted on
                        ui.button(icon='edit').props('flat round dense size=xs') \
                            .tooltip(f'Rewrite {attr_name} with the coauthor') \
                            .on('click', lambda _, n=attr_name: post_user_message(state, f"I would like to edit the {n}."))
                    header(attr_name,4)
                    value = attr.get("get_value")()
                    if value is None:
                        value = ""
                    setter = attr.get("set_value")
                    if setter is None:
                        ui.label(value)
                    else:
                        _inline_editable(state, attr_name, str(value), setter)
    return container


def _inline_editable(state: APPState, name: str, value: str, setter: Callable):
    """
    A scalar value you can edit in place: click the text, type, Enter saves.
    The change is echoed into the conversation as a receipt so the coauthor
    stays aware — direct manipulation for trivial fields, conversation for
    everything substantive.
    """
    holder = ui.element('div')

    def show_label():
        holder.clear()
        with holder:
            ui.label(value if value else '—').classes('cursor-pointer border-b border-dashed border-gray-400') \
                .tooltip(f'Click to edit {name}') \
                .on('click', lambda _: show_input())

    def show_input():
        holder.clear()
        with holder:
            box = ui.input(value=value).props('dense outlined autofocus').classes('text-sm')

            def save():
                new_value = box.value
                try:
                    setter(new_value)
                except Exception as e:
                    ui.notify(f"Couldn't set {name}: {e}", type='warning')
                    show_label()
                    return
                from gui.thread import thread_aside
                thread_aside(state, f"✏️ set **{name}** to `{new_value}`")
                state.refresh_details()

            box.on('keydown.enter', lambda _: save())
            box.on('blur', lambda _: show_label())

    show_label()
    return holder


def uploader_card(state: APPState, on_upload: Callable[[UploadEventArguments], None], aspect_ratio: str = "3/2",
                  packer: Optional["PagePacker"] = None, variants: Optional[list[tuple[float, float]]] = None,
                  label: str = 'Drop image to upload',
                  overlap_caption: Optional[Callable] = None):
    # drop boxes are n x 2: smallest-first (3 wide) so rows pack tight,
    # stretching only to close out a row, and never past 6
    cell = (packer.place_cell(variants or [(3, 2)], fudge=True, max_w=6)
            if packer is not None else contextlib.nullcontext())
    with cell:
        # 'drop-card': the page-level click rescue opens the picker from
        # anywhere on the card (the invisible uploader swallows clicks)
        card = ui.card().classes(TAILWIND_CARD + ' relative drop-card')
        if overlap_caption is None:
            card.classes('overflow-hidden')
        if packer is not None:
            card.classes('mosaic-card')
        else:
            card.style(f'aspect-ratio: {aspect_ratio}')
        if overlap_caption is not None:
            # an empty group's narrator box rides its drop box, so the
            # caption and the way to fill it stay together; overflow stays
            # visible (mosaic-card clips!) and the caption sits ABOVE the
            # invisible upload input so its button still takes the click
            card.classes('overflow-visible')
            with card:
                with ui.element('div').classes('panel-caption').style('z-index: 20;'):
                    overlap_caption()
        with card:
            uploader = ui.upload(on_upload=on_upload, auto_upload=True, max_files=1)
            uploader.classes('absolute inset-0 opacity-0 cursor-pointer z-10')

            # Visible caption in center
            with ui.row().classes('absolute inset-0 flex items-center justify-center z-0'):
                ui.label(label).classes('text-lg text-gray-600 text-center').style('padding: 0 12px;')


def removable_chips_inline(state: APPState, items: list[tuple[str, str]],
                           remover: Callable, icon: str = "sell",
                           visit: Callable | None = None):
    """removable_chips without caption or placeholder — for compact strips.
    With `visit`, the chip body is a DOOR to the thing's own room (the ✕
    still detaches — Quasar stops its click at the button)."""
    for key, label in items:
        def _remove(key=key, label=label):
            try:
                remover(key)
            except Exception as e:
                ui.notify(f"Couldn't remove {label}: {e}", type='warning')
                return
            try:
                from gui.thread import thread_aside
                thread_aside(state, f"✂️ removed **{label}**")
            except Exception:
                pass
            state.refresh_details()
        chip = ui.chip(label, removable=True, icon=icon) \
            .props('dense outline' + (' clickable' if visit else '')) \
            .tooltip(f'{label} — click to visit · ✕ detaches' if visit
                     else f'✕ detaches {label}') \
            .on('remove', lambda _, k=key: _remove(k))
        if visit:
            chip.on('click', lambda _, k=key: visit(k))


# ---------------------------------------------------------------------------
# THE PAGE GRID: views compose like comic pages — panels with column spans,
# stitched by gutters.  cpanel = inked panel; ccell = bare cell (cardwalls
# pour their own panels straight onto the paper).
# ---------------------------------------------------------------------------
def comic_page():
    return ui.element('div').classes('comic-page w-full')


def cpanel(span: int = 12):
    return ui.element('div').classes(f'cpanel cspan-{span}')


def ccell(span: int = 12):
    return ui.element('div').classes(f'cspan-{span}')


@contextlib.contextmanager
def ruled_page():
    """
    Open a ruled comic-page area and yield its PagePacker.  Every cardwall or
    cell placed through the packer lands in BLOCK bands — top and bottom
    edges ruling straight across, each band scaled to fill the page width.
    """
    packer = PagePacker(12)
    with ui.element('div').classes('mosaic-host w-full'):
        with ui.element('div').classes('comic-mosaic w-full'):
            yield packer
            packer.finalize()


# ---------------------------------------------------------------------------
# THE PAGE PACKER: the page is a stack of BLOCKS — bands of cards whose top
# and bottom edges rule straight across.  Cards fill each band left-to-right,
# top-to-bottom in slices; scalable art picks among its legal sizes
# (portrait 2:3 -> 2x3, 8/3x4, 4x6; landscape 3:2 -> 3x2, 4x8/3, 6x4;
# characters always 3x2; logos 2x2; text takes whatever its slice needs).
# Each band then scales UNIFORMLY so it fills the full 12-unit page width —
# the unit is arbitrary, so every band picks its own.
# ---------------------------------------------------------------------------
class PagePacker:
    SUB = 6          # subcolumns per unit: thirds (8/3-wide covers) stay on-grid
    MAX_SCALE = 1.5  # never blow a sparse band up more than this

    def __init__(self, width: int = 12):
        self.width = width
        self.requests: list[list] = []  # [cell, variants, flexible]

    def place_cell(self, variants: list[tuple[float, float]], fudge: bool = True,
                   max_w: Optional[float] = None):
        """Register a card cell; actual placement happens in finalize().
        fudge: the cell may stretch wider to close out its row.
        max_w: cap on that stretch (None = unlimited)."""
        cell = ui.element('div')
        self.requests.append([cell, list(variants), fudge, max_w])
        return cell

    # -- classification ------------------------------------------------
    @staticmethod
    def _is_portrait(variants) -> bool:
        """A 2:3 cover/issue card — scalable to 2x3, 8/3x4, 4x6."""
        return any(abs(w / h - 2 / 3) < 0.01 for w, h in variants)

    @staticmethod
    def _is_landscape_scalable(variants) -> bool:
        """3:2 art that ships more than one size — scalable to 3x2, 4x8/3, 6x4."""
        return (len(set(variants)) > 1
                and all(abs(w / h - 1.5) < 0.01 for w, h in variants))

    @staticmethod
    def _nominal(variants) -> tuple[float, float]:
        return variants[0]

    @staticmethod
    def _stretch_row(row, target):
        """Widen a row's flexible cells (capped ones last) so it spans
        `target`; row items are [cell, x, y, w, h, flex, max_w]."""
        for capped in (False, True):
            leftover = target - sum(r[3] for r in row)
            if leftover <= 1e-6:
                break
            flexes = [r for r in row
                      if r[5] and (r[6] is None) == (not capped)
                      and (r[6] is None or r[3] < r[6] - 1e-6)]
            if not flexes:
                continue
            extra = leftover / len(flexes)
            for r in flexes:
                r[3] += min(extra, (r[6] - r[3]) if r[6] is not None else extra)
        # reflow x positions
        x = row[0][1]
        for r in row:
            r[1] = x
            x += r[3]
        return x

    # -- band construction ----------------------------------------------
    def _row_band(self, reqs, i):
        """A simple one-slice band: consecutive same-height cards, reading
        left to right; flexible cards stretch to close the right margin
        (uncapped text first, capped cells like drop boxes last)."""
        cell, variants, flex, mw = reqs[i]
        w0, h0 = self._nominal(variants)
        row = [[cell, 0.0, 0.0, float(w0), float(h0), flex, mw]]
        x = float(w0)
        j = i + 1
        while j < len(reqs) and x < self.width - 1e-6:
            c2, v2, f2, m2 = reqs[j]
            if self._is_portrait(v2):
                # a portrait card joins the row ONLY at the row's own height
                pv = next(((w, h) for w, h in v2 if abs(h - h0) < 1e-6), None)
                if pv is None:
                    break
                w2, h2 = pv
            else:
                w2, h2 = self._nominal(v2)
            if h2 != h0 or x + w2 > self.width + 1e-6:
                break
            row.append([c2, x, 0.0, float(w2), float(h2), f2, m2])
            x += w2
            j += 1
        if x < self.width - 1e-6 and any(r[5] for r in row):
            x = self._stretch_row(row, self.width)
        return {'W': x, 'cells': [tuple(r[:5]) for r in row], 'next': j}

    def _try_cover_band(self, reqs, i, H):
        """A band led by cover(s) at height H, the region beside them filled
        with slices: rows of nominal cards, or one landscape card scaled to
        take the whole remaining slice."""
        w0 = 2 * H / 3
        cells = []
        x = 0.0
        j = i
        # the run of covers, side by side
        while (j < len(reqs) and self._is_portrait(reqs[j][1])
               and (j == i or x + w0 <= self.width + 1 / 3 + 1e-6)):
            cells.append((reqs[j][0], x, 0.0, w0, float(H)))
            x += w0
            j += 1
        budget = self.width + 1 / 3 - x
        if H == 3:
            # height-3 covers rule in a simple row with other 3-tall cards
            row = []
            R3 = 0.0
            while j < len(reqs):
                c2, v2, f2, m2 = reqs[j]
                if self._is_portrait(v2):
                    pv = next(((w, h) for w, h in v2 if abs(h - 3) < 1e-6), None)
                    if pv is None:
                        break
                    w2, h2 = pv
                else:
                    w2, h2 = self._nominal(v2)
                if h2 != 3 or x + R3 + w2 > self.width + 1e-6:
                    break
                row.append([c2, x + R3, 0.0, float(w2), 3.0, f2, m2])
                R3 += w2
                j += 1
            if row:
                if x + R3 < self.width - 1e-6 and any(r[5] for r in row):
                    self._stretch_row(row, self.width - x)
                    R3 = sum(r[3] for r in row)
                cells += [tuple(r[:5]) for r in row]
            return {'W': x + R3, 'cells': cells, 'next': j}
        # the region beside the covers, filled slice by slice
        R = 0.0
        first_slice = []
        while H > 3 and j < len(reqs):
            c2, v2, f2, m2 = reqs[j]
            if self._is_portrait(v2):
                break
            w2, h2 = self._nominal(v2)
            if h2 != 2 or R + w2 > budget + 1e-6:
                break
            first_slice.append([c2, x + R, 0.0, float(w2), 2.0, f2, m2])
            R += w2
            j += 1
        if first_slice:
            cells += [tuple(r[:5]) for r in first_slice]
            y = 2.0
            while y < H - 1e-6 and j < len(reqs):
                left = H - y
                c2, v2, f2, m2 = reqs[j]
                if self._is_portrait(v2):
                    break
                # a landscape card may scale to take the whole slice
                if self._is_landscape_scalable(v2) and abs(left - R * 2 / 3) < 1e-6:
                    cells.append((c2, x, y, R, left))
                    y = H
                    j += 1
                    continue
                w2, h2 = self._nominal(v2)
                if h2 > left + 1e-6:
                    break
                rx = 0.0
                row = []
                jj = j
                while jj < len(reqs) and rx < R - 1e-6:
                    c3, v3, f3, m3 = reqs[jj]
                    w3, h3 = self._nominal(v3)
                    if self._is_portrait(v3) or h3 != h2 or rx + w3 > R + 1e-6:
                        break
                    row.append([c3, x + rx, y, float(w3), float(h3), f3, m3])
                    rx += w3
                    jj += 1
                if row and rx < R - 1e-6 and any(r[5] for r in row):
                    rx = self._stretch_row(row, R) - row[0][1] + 0.0
                    rx = sum(r[3] for r in row)
                if not row or rx < R - 1e-6:
                    break  # can't close this slice — the band ends here
                cells += [tuple(r[:5]) for r in row]
                y += h2
                j = jj
        return {'W': x + R, 'cells': cells, 'next': j}

    def _cover_band(self, reqs, i):
        """Pick the cover height whose band comes closest to a full page width."""
        best = None
        for H in (6, 4, 3):
            cand = self._try_cover_band(reqs, i, H)
            score = abs(cand['W'] - self.width)
            if best is None or score < best[0]:
                best = (score, cand)
        return best[1]

    def finalize(self):
        """Build the bands and emit them: each band is its own grid whose
        unit is sized so the band spans the full page width."""
        reqs = self.requests
        i = 0
        while i < len(reqs):
            if self._is_portrait(reqs[i][1]):
                band = self._cover_band(reqs, i)
            else:
                band = self._row_band(reqs, i)
            cols = max(round(band['W'] * self.SUB),
                       round(self.width * self.SUB / self.MAX_SCALE))
            wrap = ui.element('div').classes('comic-block').style(
                f'grid-template-columns: repeat({cols}, 1fr); '
                f'grid-auto-rows: calc(100cqw / {cols});')
            for cell, x, y, w, h in band['cells']:
                cell.move(wrap)
                cell.style(
                    f'grid-column: {round(x * self.SUB) + 1} / span {round(w * self.SUB)}; '
                    f'grid-row: {round(y * self.SUB) + 1} / span {round(h * self.SUB)};')
            i = band['next']


def art_tools(state, img_path, *, on_reink=None,
              reink_tip='Re-ink this art from scratch', heal_name='this art'):
    """EVERY IMAGE IS EDITABLE WHERE YOU SEE IT: a small tool row riding the
    card — heal (repaint a patch, or extend the paper, on the healing bench) and, when offered, a
    re-ink.  The same affordance everywhere art shows: masters, sheets,
    mastheads, references."""
    from gui.selection import SelectionItem, SelectedKind
    if not img_path:
        return
    with ui.row().classes('absolute top-1 right-1 z-10 items-center').style('gap: 4px;'):
        def heal():
            itm = SelectionItem(name=f'Edit {heal_name}', id=img_path,
                                kind=SelectedKind.IMAGE_EDITOR)
            state.change_selection(new=[*state.selection, itm])
        ui.button(icon='healing').props('flat round dense size=xs') \
            .classes('bg-white/70 dark:bg-black/50') \
            .tooltip('Take this art to the healing bench — repaint a patch or extend the paper') \
            .on('click.stop', lambda _: heal())
        if on_reink:
            ui.button(icon='brush').props('flat round dense size=xs') \
                .classes('bg-white/70 dark:bg-black/50') \
                .tooltip(reink_tip) \
                .on('click.stop', lambda _: on_reink())
