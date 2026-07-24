import os
import json
import shutil
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
from loguru import logger
from nicegui import ui

from gui.elements import header, TAILWIND_CARD
from gui.selection import SelectedKind
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
        with ui.row().classes("w-full flex-nowrap items-center").style("padding: 0; margin: 0; gap: 12px;"):
            header("The choices sheet", 0)
            ui.space()
            ui.button(icon="logout").props("flat round") \
                .tooltip("Leave the bench — the original stays; unpicked takes go to the wastebasket") \
                .on("click", lambda _: _cancel(state))

        ui.markdown("Every take is the same heal, tried four ways — pick the one that "
                    "reads best and **paste it down**.  The original is pinned first; "
                    "choosing it leaves the acetate exactly as it was.")

        selected = state.image_editor_choice_selected

        with ui.element().classes("grid grid-cols-2 gap-3 w-full"):
            # THE ORIGINAL, PINNED: the sheet always shows what you'd be
            # giving up — and keeping it is a first-class pick
            if original and os.path.exists(original):
                card = ui.card().classes(TAILWIND_CARD).style("aspect-ratio: 3/2")
                with card:
                    url = _image_path_to_url(original)
                    ui.image(source=f"{url}{'&' if '?' in url else '?'}v={uuid4().hex[:8]}") \
                        .style("top-padding: 0; bottom-padding:0")
                    ui.badge("THE ORIGINAL", color="grey-8").props("floating") \
                        .classes("absolute top-0 left-0 z-10")
                    if selected is None:
                        ui.badge("✓", color="green").props("floating").classes("absolute top-0 right-0 z-10")
                card.tooltip("Keep it as it was — no take is pasted down")
                card.on("click", lambda _: _select_choice(state, None))

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
            ui.markdown("No takes on the sheet — run the heal again.").style("color: red;")

        with ui.row().classes("w-full gap-2 q-mt-sm"):
            if selected is None:
                ui.button("Keep the original", icon="verified").classes("w-1/2") \
                    .props("no-caps") \
                    .tooltip("The acetate stays exactly as it was; the takes wait in the wastebasket") \
                    .on("click", lambda _: _cancel(state))
            else:
                ui.button("Paste it down", icon="check").classes("w-1/2") \
                    .props("no-caps") \
                    .tooltip("Lay this take down as NEW art beside the original — "
                             "the original is never overwritten, it keeps its "
                             "place on the wall") \
                    .on("click", lambda _: _apply(state))
            ui.button("Leave the bench", icon="logout").classes("w-1/2") \
                .props("flat no-caps") \
                .on("click", lambda _: _cancel(state))
        ui.label("Unpicked takes wait in the wastebasket — nothing paid-for burns.") \
            .classes("text-xs text-gray-500")


def _select_choice(state: APPState, path: str):
    state.image_editor_choice_selected = path
    state.refresh_details()


def _swap_trail_references(state: APPState, original: str, healed: str) -> bool:
    """Every object on the selection trail that pointed at the original now
    points at the healed art — a featured cover stays featured, an acetate
    stays in its layer, a setting master stays keyed to its style — while
    the ORIGINAL FILE is never touched.  Returns True when anything moved."""
    from gui.selection import selection_to_context, SelectedKind as _SK
    storage = getattr(state, "storage", None)
    if storage is None:
        return False
    contexts = []
    try:
        contexts = list(selection_to_context(state.selection))
    except Exception as ex:
        logger.debug(f"trail context walk failed: {ex}")
    # the mark board rides outside selection_to_context — add it by hand
    scope = None
    for s in state.selection:
        if s.kind in (_SK.PUBLISHER, _SK.SERIES):
            scope = s.id
        elif s.kind == _SK.ARTBOARD and scope:
            from schema import ArtBoard
            contexts.append((ArtBoard, {"scope_id": scope, "board_id": s.id}))
    swapped = False
    for cls, pk in contexts:
        try:
            obj = storage.read_object(cls=cls, primary_key=pk)
        except Exception:
            obj = None
        if obj is None:
            continue
        changed = False
        for name in type(obj).model_fields:
            val = getattr(obj, name, None)
            if isinstance(val, str) and val == original:
                setattr(obj, name, healed)
                changed = True
            elif isinstance(val, dict):
                for k, v in list(val.items()):
                    if isinstance(v, str) and v == original:
                        val[k] = healed
                        changed = True
        if changed:
            try:
                storage.update_object(obj)
                swapped = True
            except Exception as ex:
                logger.warning(f"reference swap failed for {cls.__name__}: {ex}")
    return swapped


def _apply(state: APPState):
    chosen = state.image_editor_choice_selected
    original = state.image_editor_original_image or state.image_editor_image

    if not chosen or not original:
        ui.notify("Pick a take first — or keep the original.", type="warning")
        return
    if not os.path.exists(chosen):
        ui.notify("That take has gone missing — pick another.", type="negative")
        return
    if not os.path.exists(original):
        ui.notify("The original acetate is missing.", type="negative")
        return

    # NOTHING THE AUTHOR MADE IS OVERWRITTEN: the heal lands as a NEW file
    # beside the original — on a board that means the pre-heal art keeps
    # its place in the takes list, and there is no last-copy moment at all.
    folder = os.path.dirname(original)
    ext = (os.path.splitext(original)[1] or os.path.splitext(chosen)[1] or ".png")
    healed = os.path.join(folder, f"healed-{uuid4().hex[:8]}{ext}")
    try:
        # CLEAR ACETATE: healing a transparent image must never paste an
        # opaque card into the layered composite — outside the healed
        # patch, the ORIGINAL's alpha survives verbatim
        applied = False
        try:
            from PIL import Image
            # the heal's manifest knows the REGION and the MODE — an
            # extend-take's grown paper must never be squashed back to the
            # original trim by the alpha-preserving heal path
            region = None
            heal_mode = None
            try:
                import json as _json
                manifest = os.path.join(
                    os.path.dirname(original),
                    f".choices-{state.image_editor_session_id}.json")
                if os.path.exists(manifest):
                    payload = _json.load(open(manifest))
                    region = payload.get('region')
                    heal_mode = payload.get('mode')
            except Exception:
                region, heal_mode = None, None
            src = Image.open(original)
            if heal_mode != 'outpaint' and (
                    src.mode in ('RGBA', 'LA') or 'transparency' in src.info):
                src = src.convert('RGBA')
                a_min, _ = src.getchannel('A').getextrema()
                if a_min < 250:
                    new = Image.open(chosen).convert('RGBA').resize(src.size)
                    alpha = src.getchannel('A').copy()
                    if region and all(k in region for k in ('x', 'y', 'width', 'height')):
                        # inside the healed patch, the take's own alpha rules
                        box = (int(region['x']), int(region['y']),
                               int(region['x'] + region['width']),
                               int(region['y'] + region['height']))
                        alpha.paste(new.getchannel('A').crop(box), box)
                    new.putalpha(alpha)
                    new.save(healed, 'PNG')
                    applied = True
        except Exception as ex:
            logger.warning(f"alpha-preserving apply fell back to plain copy: {ex}")
        if not applied:
            shutil.copyfile(chosen, healed)
    except Exception as e:
        logger.exception("Failed to lay down the healed take")
        ui.notify(f"Failed to apply edit: {e}", type="negative")
        return

    # whatever featured or layered the original now shows the heal; the
    # original file itself stands untouched on the wall
    swapped = _swap_trail_references(state, original, healed)

    _cleanup_choices(state, keep_original=True)
    state.image_editor_image = healed
    state.is_dirty = True

    from gui.light_table import table_receipt
    table_receipt(state, "🖌 pasted the take down as NEW art beside the original — "
                         "nothing was overwritten"
                         + (", and everything that showed the original now shows the heal"
                            if swapped else
                            ".  Click the new take on the wall to feature it") + ".")

    # Return to the bench, now standing at the healed art
    new_sel = []
    for s in state.selection:
        if s.kind == SelectedKind.IMAGE_EDITOR_CHOICES:
            continue
        if s.kind == SelectedKind.IMAGE_EDITOR and s.id == original:
            from gui.selection import SelectionItem
            s = SelectionItem(name=s.name, id=healed, kind=s.kind)
        new_sel.append(s)
    state.change_selection(new=new_sel)


def _cancel(state: APPState):
    _cleanup_choices(state, keep_original=True)
    new_sel = [s for s in state.selection if s.kind != SelectedKind.IMAGE_EDITOR_CHOICES]
    state.change_selection(new=new_sel)


def _cleanup_choices(state: APPState, keep_original: bool = True):
    # NOTHING PAID-FOR BURNS: unpicked takes go to the ONE wastebasket,
    # not to os.remove — apply and cancel both leave a way back
    from storage.trash import soft_delete
    base = str(getattr(getattr(state, "storage", None), "base_path", "data"))
    origin = state.image_editor_original_image or state.image_editor_image or ""
    for path in state.image_editor_choices or []:
        try:
            if keep_original and path == state.image_editor_original_image:
                continue
            if os.path.exists(path):
                soft_delete(base, path,
                            note=f"an unpicked take from a heal of {os.path.basename(origin)}")
        except Exception:
            logger.debug(f"Failed to wastebasket choice file {path}")
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
