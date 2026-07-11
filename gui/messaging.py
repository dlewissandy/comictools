from loguru import logger
from gui.state import APPState
from nicegui import ui
from gui.avatars import comic_chat_message

def post_user_message(state:APPState, message: str):
    logger.debug(str)
    user_input = state.user_input
    send_button = state.send_button
    user_input.value = message
    send_button.run_method('click')
    
def new_item_messager(state: APPState, caption: str, message: str, caption_size: int = 2):
    from gui.elements import caption_action, CrudButtonKind
    with ui.row().classes('w-full') as row:
        caption_action(caption, CrudButtonKind.CREATE,
                       lambda _: post_user_message(state, message), caption_size)
    # set the top and bottom margin to 0
    row.style('margin-top: 0; margin-bottom: 0;')
    return row
    


def attach_reference(state, e) -> None:
    """
    An image dropped into the conversation: file it as a reference on the
    object being worked on (nearest ancestor that accepts uploads), show it in
    the chat, and tell the coauthor about it.
    """
    import os
    from loguru import logger
    from nicegui import ui
    from gui.selection import selection_to_context
    from storage.filepath import UPLOAD_PATH_TEMPLATES

    if not (e.type or "").startswith("image/"):
        ui.notify("Only images can be attached.", type="warning")
        return

    target = None
    try:
        for cls, pk in reversed(selection_to_context(state.selection)):
            if cls.__name__ in UPLOAD_PATH_TEMPLATES:
                obj = state.storage.read_object(cls=cls, primary_key=pk)
                if obj is not None:
                    target = obj
                    break
    except Exception as ex:
        logger.debug(f"attach target resolution failed: {ex}")
    if target is None:
        ui.notify("Open a series (or something inside one) first, then attach the image.", type="warning")
        return

    locator = state.storage.upload_reference_image(obj=target, name=e.name, data=e.content, mime_type=e.type)
    kind = target.__class__.__name__.replace("Model", "").replace("Asset", "").lower()
    with state.history:
        with comic_chat_message(name='You', sent=True).classes('w-full'):
            ui.markdown(f"📎 attached a reference image to this {kind}")
            ui.image(source=locator).classes('rounded-md q-mt-xs').style('max-width: 280px;')
    state.history.scroll_to(percent=100)
    post_user_message(state, f"I attached a reference image for this {kind}: {locator}.  Use it as a visual reference here.")
