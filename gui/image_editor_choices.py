import os
import json
import shutil
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
from loguru import logger
from nicegui import ui

from gui.elements import header, TAILWIND_CARD
from gui.selection import SelectionItem, SelectedKind
from gui.state import APPState


def view_image_editor_choices(state: APPState):
    details = state.details
    details.clear()

    selection = state.selection
    session_id = state.image_editor_session_id
    original = state.image_editor_original_image or state.image_editor_image

    if selection and selection[-1].id:
        raw_id = selection[-1].id
        if isinstance(raw_id, str) and "|" in raw_id:
            session_id, original_from_id = raw_id.split("|", 1)
            if original_from_id:
                original = original_from_id
        else:
            session_id = session_id or raw_id

    if session_id:
        state.image_editor_session_id = session_id
    if original:
        state.image_editor_original_image = original

    choices = state.image_editor_choices or []

    # Fallback: load choices from manifest when needed
    if (not choices) and original and os.path.exists(original) and session_id:
        try:
            manifest = os.path.join(os.path.dirname(original), f".choices-{session_id}.json")
            if os.path.exists(manifest):
                with open(manifest, "r") as f:
                    payload = json.load(f)
                choices = payload.get("choices", [])
                state.image_editor_choices = choices
                if choices and not state.image_editor_choice_selected:
                    state.image_editor_choice_selected = choices[0]
        except Exception as e:
            logger.debug(f"Failed to scan choice files: {e}")

    # Fallback: scan for session-prefixed files
    if (not choices) and original and os.path.exists(original) and session_id:
        try:
            folder = os.path.dirname(original)
            candidates = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.startswith(f"choice-{session_id}-") and os.path.isfile(os.path.join(folder, f))
            ]
            candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            choices = candidates[:4]
            state.image_editor_choices = choices
            if choices and not state.image_editor_choice_selected:
                state.image_editor_choice_selected = choices[0]
        except Exception as e:
            logger.debug(f"Failed to scan choice files: {e}")

    with details:
        with ui.row().classes("w-full flex-nowrap").style("padding: 0; margin: 0;"):
            header("Choose an Edit", 0)
            ui.space()
            ui.button("Cancel", icon="close", on_click=lambda: _cancel(state)).classes("text-base")

        ui.markdown("Pick one option to replace the current image.")

        selected = state.image_editor_choice_selected

        with ui.element().classes("grid grid-cols-2 gap-3 w-full"):
            for path in choices:
                card = ui.card().classes(TAILWIND_CARD).style("aspect-ratio: 3/2")
                with card:
                    if os.path.exists(path):
                        url = _image_path_to_url(path)
                        url = f"{url}{'&' if '?' in url else '?'}v={uuid4().hex[:8]}"
                        ui.image(source=url).style("top-padding: 0; bottom-padding:0")
                    else:
                        ui.label(f"Missing: {path}").style("color: red;")
                    if path == selected:
                        ui.badge("✓", color="green").props("floating").classes("absolute top-0 right-0 z-10")
                card.on("click", lambda _, p=path: _select_choice(state, p))

        if not choices:
            ui.markdown("No choices found. Try the edit again.").style("color: red;")

        with ui.row().classes("w-full gap-2"):
            ui.button("Apply Selection", icon="check", on_click=lambda: _apply(state)).classes("w-1/2")
            ui.button("Cancel", icon="close", on_click=lambda: _cancel(state)).classes("w-1/2")


def _select_choice(state: APPState, path: str):
    state.image_editor_choice_selected = path
    state.refresh_details()


def _apply(state: APPState):
    chosen = state.image_editor_choice_selected
    original = state.image_editor_original_image or state.image_editor_image

    if not chosen or not original:
        ui.notify("No choice selected.", type="warning")
        return
    if not os.path.exists(chosen):
        ui.notify("Selected file is missing.", type="negative")
        return
    if not os.path.exists(original):
        ui.notify("Original image is missing.", type="negative")
        return

    try:
        shutil.copyfile(chosen, original)
    except Exception as e:
        logger.exception("Failed to overwrite original image")
        ui.notify(f"Failed to apply edit: {e}", type="negative")
        return

    _cleanup_choices(state, keep_original=True)
    state.image_editor_image = original
    state.is_dirty = True

    # Return to editor view
    new_sel = [s for s in state.selection if s.kind != SelectedKind.IMAGE_EDITOR_CHOICES]
    state.change_selection(new=new_sel)


def _cancel(state: APPState):
    _cleanup_choices(state, keep_original=True)
    new_sel = [s for s in state.selection if s.kind != SelectedKind.IMAGE_EDITOR_CHOICES]
    state.change_selection(new=new_sel)


def _cleanup_choices(state: APPState, keep_original: bool = True):
    for path in state.image_editor_choices or []:
        try:
            if keep_original and path == state.image_editor_original_image:
                continue
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            logger.debug(f"Failed to delete choice file {path}")
    if state.image_editor_original_image and state.image_editor_session_id:
        manifest = os.path.join(os.path.dirname(state.image_editor_original_image), f".choices-{state.image_editor_session_id}.json")
        if os.path.exists(manifest):
            try:
                os.remove(manifest)
            except Exception:
                logger.debug(f"Failed to delete manifest {manifest}")
    state.image_editor_choices = []
    state.image_editor_choice_selected = None
    state.image_editor_original_image = None
    state.image_editor_session_id = None


def _image_path_to_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    normalized = path.replace("\\", "/")
    if normalized.startswith("/data/"):
        url = normalized
    elif normalized.startswith("data/"):
        url = "/" + normalized
    else:
        base = Path("data").resolve()
        try:
            rel = Path(path).resolve().relative_to(base)
            url = "/data/" + rel.as_posix()
        except ValueError:
            url = normalized
    return quote(url, safe="/:")
