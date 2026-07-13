"""
THE HEALING BENCH: where one acetate comes to be repainted.

The art lies on a lit stage in a dark room — transparency shows as
checkered glass, because a CLEAR ACETATE must stay clear through a heal.
Drag a marquee over what needs fixing and the readout follows your hand;
speak the change in the chat ('heal the scratched sky'); then press the
tool.  HEAL THE PATCH repaints only what the marquee holds.  EXTEND THE
PAPER grows the sheet past its edges — the art keeps its place.
"""
import html
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from nicegui import ui

from gui.elements import header
from gui.messaging import post_user_message
from gui.state import APPState


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


def view_image_editor(state: APPState):
    selection = state.selection
    details = state.details

    details.clear()

    # whose acetate is on the bench?  the bench's own selection item carries
    # the true subject ('Edit Vera', 'Edit <setting> background'); generic
    # labels fall back to the board the trail came through, then the filename
    subject = None
    if selection and selection[-1].name:
        cand = str(selection[-1].name).strip()
        if cand.lower().startswith('edit '):
            cand = cand[5:]
        if cand.lower().endswith(' background'):
            cand = cand[:-11]
        if cand.strip().lower() not in ('healing', 'image editor', 'panel image',
                                        'cover image', 'insert image', 'image',
                                        'artwork', 'choices', 'edit', ''):
            subject = cand.strip()
    if not subject and len(selection) > 1 and selection[-2].name:
        subject = str(selection[-2].name)
    if not subject and selection and selection[-1].id:
        subject = os.path.splitext(os.path.basename(str(selection[-1].id)))[0]

    if not selection or selection[-1].id is None:
        with details:
            header("The healing bench", 0)
            ui.markdown("No acetate on the bench — walk in from an image's Heal door.").style("color: red;")
        return

    image_locator = selection[-1].id
    if not os.path.exists(image_locator):
        with details:
            header("The healing bench", 0)
            ui.markdown(f"That acetate is gone: `{image_locator}`").style("color: red;")
        return

    if getattr(state, 'image_editor_image', None) != image_locator:
        # a NEW image on the bench gets a fresh session (compare BEFORE
        # assigning — the old order made this check dead code) — and the
        # previous acetate's marquee and mode must never aim THIS heal
        state.image_editor_session_id = uuid4().hex[:8]
        state.image_editor_selection = None
        state.image_editor_mode = None
    state.image_editor_image = image_locator

    # THE RECOVERY DOOR: takes from an earlier heal that were never claimed
    # (a crash, a reload) wait in their manifest — offer them back instead
    # of letting paid work rot invisibly beside the image
    def _unclaimed_manifests():
        import json as _json
        out = []
        folder = os.path.dirname(image_locator)
        try:
            for f in os.listdir(folder):
                if not (f.startswith('.choices-') and f.endswith('.json')):
                    continue
                try:
                    payload = _json.load(open(os.path.join(folder, f)))
                except Exception:
                    continue
                if payload.get('image') != image_locator:
                    continue
                alive = [c for c in payload.get('choices', []) if os.path.exists(c)]
                if alive:
                    out.append((payload.get('written_at', 0),
                                payload.get('session_id'), alive))
        except OSError:
            pass
        out.sort()          # oldest first; [-1] is the newest heal
        return out

    image_url = _image_path_to_url(image_locator)
    cache_buster = uuid4().hex[:8]
    image_url = f"{image_url}{'&' if '?' in image_url else '?'}v={cache_buster}"
    editor_id = f"image-editor-{uuid4().hex[:8]}"
    state.image_editor_dom_id = editor_id
    image_url_safe = html.escape(image_url, quote=True)

    with details:
        with ui.row().classes('w-full flex-nowrap items-center').style('padding: 0; margin: 0; gap: 12px;'):
            header(f"Healing the {subject} acetate" if subject else "The healing bench", 0)
            ui.space()

            def leave_bench(_=None):
                # the bench forgets its marquee and mode on the way out — a
                # later chat message must never inherit them
                state.image_editor_selection = None
                state.image_editor_mode = None
                from gui.selection import SelectedKind
                state.change_selection(new=[s for s in state.selection
                                            if s.kind != SelectedKind.IMAGE_EDITOR])
            ui.button(icon='logout').props('flat round') \
                .tooltip('Leave the bench — the acetate stays as it is') \
                .on('click', leave_bench)

        unclaimed = _unclaimed_manifests()
        if unclaimed:
            _at, session_id, takes = unclaimed[-1]

            def _reopen(sid=session_id, tk=takes):
                state.image_editor_choices = tk
                state.image_editor_choice_selected = tk[0]
                state.image_editor_original_image = image_locator
                from gui.selection import SelectionItem as _SI, SelectedKind as _SK
                state.change_selection(new=[*state.selection, _SI(
                    name="Choices", id=f"{sid}|{image_locator}",
                    kind=_SK.IMAGE_EDITOR_CHOICES)])
            ui.chip(f"{len(takes)} unclaimed take{'s' if len(takes) != 1 else ''} "
                    f"from an earlier heal — open the choices sheet",
                    icon='inventory').props('outline clickable') \
                .tooltip('Paid work from a heal that was never picked — nothing is lost') \
                .on('click', lambda _: _reopen())

        # ---- ONE SCREEN: the lit stage with the tool rail docked beside --
        with ui.row().classes('w-full flex-nowrap q-mt-sm').style('gap: 14px; align-items: stretch;'):

            # THE STAGE: dark room, lit paper — transparency reads as
            # checkered glass so a clear acetate visibly STAYS clear
            with ui.element('div').style(
                    'flex: 1 1 auto; min-width: 0; border-radius: 10px; '
                    'background: radial-gradient(ellipse at 50% 42%, #2c2925 0%, #16140f 75%); '
                    'display: flex; align-items: center; justify-content: center; '
                    'padding: 22px; height: 70vh;'):
                ui.html(f"""
                <div id="{editor_id}" style="position: relative; display: inline-block; max-width: 100%; max-height: 100%; cursor: crosshair; user-select: none; touch-action: none;
                            background: repeating-conic-gradient(#b9b5ad 0% 25%, #dedad2 0% 50%) 50% / 18px 18px;
                            box-shadow: 0 10px 34px rgba(0,0,0,.55); border-radius: 3px;">
                  <img id="{editor_id}-img" src="{image_url_safe}" style="max-width: 100%; max-height: calc(70vh - 44px); width: auto; height: auto; display: block; user-select: none;" draggable="false" />
                  <div id="{editor_id}-rect" style="position: absolute; border: 2px dashed #f3c14b; background: rgba(243, 193, 75, 0.16); display: none; pointer-events: none;"></div>
                  <div id="{editor_id}-size" style="position: absolute; display: none; pointer-events: none; background: #1c1a16; color: #f3c14b; font-size: 11px; padding: 1px 7px; border-radius: 3px; white-space: nowrap; font-family: ui-monospace, monospace;"></div>
                </div>
                """)

            # THE TOOL RAIL, docked beside the stage
            with ui.column().style('flex: 0 0 264px; gap: 10px;'):
                ui.label('The healing bench').classes('caption-box caption-box-sm')
                ui.markdown(
                    "Drag a **marquee** over what needs fixing — the readout "
                    "follows your hand.  Say the change in the chat below "
                    "(*“heal the scratched sky”*), then press the tool."
                ).classes('text-sm')

                marquee_status = ui.markdown('Marquee: **none — the whole acetate**') \
                    .classes('text-sm text-gray-500')

                async def fetch_selection():
                    js = f"window.__imageEditorSelections && window.__imageEditorSelections['{editor_id}']"
                    selection_data = await ui.run_javascript(js)
                    if selection_data:
                        marquee_status.content = (f"Marquee: **{selection_data.get('width', 0)} × "
                                                  f"{selection_data.get('height', 0)}px**")
                    else:
                        marquee_status.content = 'Marquee: **none — the whole acetate**'
                    return selection_data

                async def handle_action(mode: str):
                    if not state.image_editor_session_id:
                        state.image_editor_session_id = uuid4().hex[:8]
                    selection_data = await fetch_selection()
                    state.image_editor_selection = selection_data
                    state.image_editor_image = image_locator
                    state.image_editor_mode = mode

                    prompt = (state.user_input.value or "").strip()
                    if prompt:
                        message = prompt
                    elif mode == "inpaint":
                        message = "Heal the marked patch of this image."
                    else:
                        message = "Extend the paper on this image."
                    post_user_message(state, message)

                ui.button('Heal the patch', icon='healing') \
                    .props('unelevated no-caps').classes('w-full') \
                    .tooltip('The marquee AIMS the heal — the take comes back with '
                             'that patch redone, and a clear acetate keeps its '
                             'transparency outside the patch.  With no marquee, the '
                             'whole acetate is fair game.') \
                    .on('click', lambda _: handle_action('inpaint'))

                ui.button('Extend the paper', icon='open_in_full') \
                    .props('unelevated no-caps').classes('w-full') \
                    .tooltip('The paper grows about 256px on EVERY side and the art '
                             'keeps its place — the marquee plays no part here.  Say '
                             'what should fill the new margins.') \
                    .on('click', lambda _: handle_action('outpaint'))

                async def on_clear():
                    state.image_editor_selection = None
                    await ui.run_javascript(
                        f"window.__clearImageEditorSelection && window.__clearImageEditorSelection('{editor_id}')")
                    marquee_status.content = 'Marquee: **none — the whole acetate**'

                ui.button('Lift the marquee', icon='crop_free') \
                    .props('flat dense no-caps').classes('w-full') \
                    .tooltip('Clear the selection — back to the whole acetate') \
                    .on('click', on_clear)

                ui.markdown(
                    "Four takes come back on a **choices sheet** — paste one "
                    "down or keep the original.  Unpicked takes wait in the "
                    "wastebasket; nothing paid-for burns."
                ).classes('text-xs text-gray-500')

    ui.run_javascript(f"""
    (() => {{
      const editorId = "{editor_id}";
      const setup = () => {{
        const container = document.getElementById(editorId);
        if (!container) return false;
        if (container.dataset.imageEditorInit === "true") return true;
        const img = document.getElementById(editorId + "-img");
        const rect = document.getElementById(editorId + "-rect");
        const size = document.getElementById(editorId + "-size");
        if (!img || !rect) return false;
        container.dataset.imageEditorInit = "true";
        const selections = window.__imageEditorSelections = window.__imageEditorSelections || {{}};
        selections[editorId] = null;
        window.__clearImageEditorSelection = (id) => {{
          if (id && id !== editorId) return;
          rect.style.display = "none";
          if (size) size.style.display = "none";
          selections[editorId] = null;
        }};
        let start = null;
        let dragging = false;
        const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
        const toImageCoords = (x, y) => {{
          if (!img.naturalWidth || !img.naturalHeight) return {{ x: 0, y: 0 }};
          const r = img.getBoundingClientRect();
          const scaleX = img.naturalWidth / r.width;
          const scaleY = img.naturalHeight / r.height;
          return {{
            x: Math.round(x * scaleX),
            y: Math.round(y * scaleY)
          }};
        }};
        const onDown = (e) => {{
          e.preventDefault();
          if (container.setPointerCapture && e.pointerId !== undefined) {{
            container.setPointerCapture(e.pointerId);
          }}
          const r = img.getBoundingClientRect();
          const x = clamp(e.clientX - r.left, 0, r.width);
          const y = clamp(e.clientY - r.top, 0, r.height);
          start = {{ x, y }};
          dragging = true;
          rect.style.display = "block";
          rect.style.left = `${{x}}px`;
          rect.style.top = `${{y}}px`;
          rect.style.width = "0px";
          rect.style.height = "0px";
          if (size) size.style.display = "none";
          selections[editorId] = null;
        }};
        const onMove = (e) => {{
          if (!dragging || !start) return;
          const r = img.getBoundingClientRect();
          const x = clamp(e.clientX - r.left, 0, r.width);
          const y = clamp(e.clientY - r.top, 0, r.height);
          const x1 = Math.min(start.x, x);
          const y1 = Math.min(start.y, y);
          const x2 = Math.max(start.x, x);
          const y2 = Math.max(start.y, y);
          rect.style.left = `${{x1}}px`;
          rect.style.top = `${{y1}}px`;
          rect.style.width = `${{x2 - x1}}px`;
          rect.style.height = `${{y2 - y1}}px`;
          const startImg = toImageCoords(x1, y1);
          const endImg = toImageCoords(x2, y2);
          selections[editorId] = {{
            x: startImg.x,
            y: startImg.y,
            width: Math.max(1, endImg.x - startImg.x),
            height: Math.max(1, endImg.y - startImg.y),
          }};
          // THE LIVE READOUT: the marquee speaks its size as you drag
          if (size) {{
            size.textContent = `${{selections[editorId].width}} × ${{selections[editorId].height}}px`;
            size.style.display = "block";
            size.style.left = `${{x1}}px`;
            size.style.top = `${{Math.max(y1 - 20, 2)}}px`;
          }}
        }};
        const onUp = (e) => {{
          dragging = false;
          if (container.releasePointerCapture && e.pointerId !== undefined) {{
            try {{ container.releasePointerCapture(e.pointerId); }} catch (_) {{}}
          }}
        }};
        container.addEventListener("pointerdown", onDown);
        container.addEventListener("pointermove", onMove);
        container.addEventListener("pointerup", onUp);
        container.addEventListener("pointerleave", onUp);
        return true;
      }};
      if (!setup()) {{
        const timer = setInterval(() => {{
          if (setup()) clearInterval(timer);
        }}, 50);
      }}
    }})();
    """)
