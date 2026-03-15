import html
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from nicegui import ui

from gui.elements import header, TAILWIND_CARD
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
    with details:
        header("Image Editor", 0)

    if not selection or selection[-1].id is None:
        with details:
            ui.markdown("No image selected for editing.").style("color: red;")
        return

    image_locator = selection[-1].id
    if not os.path.exists(image_locator):
        with details:
            ui.markdown(f"Image not found: `{image_locator}`").style("color: red;")
        return

    state.image_editor_image = image_locator

    if state.image_editor_image != image_locator:
        state.image_editor_session_id = uuid4().hex[:8]
    image_url = _image_path_to_url(image_locator)
    cache_buster = uuid4().hex[:8]
    image_url = f"{image_url}{'&' if '?' in image_url else '?'}v={cache_buster}"
    editor_id = f"image-editor-{uuid4().hex[:8]}"
    state.image_editor_dom_id = editor_id
    image_url_safe = html.escape(image_url, quote=True)

    with details:
        with ui.row().classes("w-full gap-6"):
            with ui.column().classes("w-2/3"):
                with ui.card().classes(TAILWIND_CARD).style("padding: 1rem;"):
                    ui.markdown("**Drag to select a region (optional).**")
                    ui.html(f"""
                    <div id="{editor_id}" style="position: relative; display: inline-block; max-width: 100%; width: 100%; cursor: crosshair; user-select: none; touch-action: none;">
                      <img id="{editor_id}-img" src="{image_url_safe}" style="max-width: 100%; width: 100%; height: auto; display: block; user-select: none;" draggable="false" />
                      <div id="{editor_id}-rect" style="position: absolute; border: 2px dashed #3b82f6; background: rgba(59, 130, 246, 0.22); display: none; pointer-events: none;"></div>
                    </div>
                    """)
                async def on_clear():
                    state.image_editor_selection = None
                    await ui.run_javascript(f"window.__clearImageEditorSelection && window.__clearImageEditorSelection('{editor_id}')")

                ui.button("Clear Selection", on_click=on_clear)

            with ui.column().classes("w-1/3"):
                with ui.card().classes(TAILWIND_CARD).style("padding: 1rem;"):
                    ui.markdown("**Use the chat input below as your prompt.**")
                    ui.label("Type your instruction in the chat box, then use a shortcut.").classes("text-sm text-gray-600")
                    selection_status = ui.markdown("Selection: **none**").classes("text-sm text-gray-600")

                    async def fetch_selection():
                        js = f"window.__imageEditorSelections && window.__imageEditorSelections['{editor_id}']"
                        selection_data = await ui.run_javascript(js)
                        if selection_data:
                            selection_status.content = f"Selection: **{selection_data.get('width', 0)}x{selection_data.get('height', 0)}**"
                        else:
                            selection_status.content = "Selection: **none**"
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
                        else:
                            message = f"I would like to {mode} a region of this image."
                        post_user_message(state, message)

                    async def on_inpaint():
                        await handle_action("inpaint")

                    async def on_outpaint():
                        await handle_action("outpaint")

                    with ui.row().classes("w-full gap-2"):
                        ui.button("Inpaint", icon="auto_fix_high", on_click=on_inpaint).classes("w-1/2")
                        ui.button("Outpaint", icon="open_in_full", on_click=on_outpaint).classes("w-1/2")

    ui.run_javascript(f"""
    (() => {{
      const editorId = "{editor_id}";
      const setup = () => {{
        const container = document.getElementById(editorId);
        if (!container) return false;
        if (container.dataset.imageEditorInit === "true") return true;
        const img = document.getElementById(editorId + "-img");
        const rect = document.getElementById(editorId + "-rect");
        if (!img || !rect) return false;
        container.dataset.imageEditorInit = "true";
        const selections = window.__imageEditorSelections = window.__imageEditorSelections || {{}};
        selections[editorId] = null;
        window.__clearImageEditorSelection = (id) => {{
          if (id && id !== editorId) return;
          rect.style.display = "none";
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
