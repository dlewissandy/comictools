"""
THE CREATE DIALOG: one door, three paths, for every reusable asset —
characters, settings, props and wardrobe.

An author builds a new asset three ways, and the dialog offers all three:
  • DESCRIBE IT — a name and a description, from scratch.
  • FROM AN IMAGE — drop or browse a reference; the studio reads the look
    off the picture (plus any notes on what to change).
  • COPY AN EXISTING ONE — start from one you already have, name the new
    one, and say what's different.

Each path collects structured input and hands the coauthor ONE well-formed
instruction, so the thread, the receipts and the reference render all flow
the way they do everywhere else in the studio.
"""
import os
from uuid import uuid4

from nicegui import ui
from nicegui.events import UploadEventArguments

from gui.state import APPState
from gui.messaging import post_user_message


# per-kind vocabulary — the dialog speaks the asset's own name everywhere
_KIND = {
    "character": {
        "title": "character",
        "describe_hint": "Who are they?  Their role, their look, what makes them recognizable.",
        "copy_verb": "derive",
        "copy_hint": "a sibling, a rival from the same clan, the same face in a new role",
        "reads": "the studio reads their look off the picture",
    },
    "setting": {
        "title": "setting",
        "describe_hint": "Where is it?  Architecture, light, mood, the props that dress it.",
        "copy_verb": "vary",
        "copy_hint": "the same place at night, or ruined, or a season later",
        "reads": "the studio reads the place off the picture",
    },
    "prop": {
        "title": "prop",
        "describe_hint": "What is it?  Size, materials, colors, wear, where it usually sits.",
        "copy_verb": "vary",
        "copy_hint": "a battered version, a different color, a matching pair",
        "reads": "the studio reads the object off the picture",
    },
    "outfit": {
        "title": "outfit",
        "describe_hint": "The garments, materials, colors, condition, accessories.",
        "copy_verb": "vary",
        "copy_hint": "the same outfit travel-worn, or in another palette",
        "reads": "the studio reads the wardrobe off the picture",
    },
}


def _asset_class(kind):
    from schema import CharacterModel, Setting, PropAsset, Outfit
    return {"character": CharacterModel, "setting": Setting,
            "prop": PropAsset, "outfit": Outfit}[kind]


def _existing(storage, series_id, kind):
    cls = _asset_class(kind)
    objs = storage.read_all_objects(cls, {"series_id": series_id})
    return sorted(objs, key=lambda o: (o.name or "").lower())


def create_asset_dialog(state: APPState, series_id: str, kind: str):
    """Open the three-path Create dialog for one asset kind."""
    meta = _KIND[kind]
    storage = state.storage

    def _save_upload(e: UploadEventArguments) -> str | None:
        """Land a dropped/browsed image in the series uploads; return its path."""
        if not (e.type or "").startswith("image/"):
            ui.notify("That isn't an image.", type="warning")
            return None
        from schema import Series
        series = storage.read_object(Series, {"series_id": series_id})
        updir = os.path.join(series.path() if series else os.path.join("data", "series", series_id),
                             "uploads")
        os.makedirs(updir, exist_ok=True)
        safe = f"{uuid4().hex[:8]}-{os.path.basename(e.name or 'dropped.png')}"
        path = os.path.join(updir, safe)
        with open(path, "wb") as f:
            f.write(e.content.read())
        return path

    with ui.dialog() as dlg, ui.card().classes("soft-card") \
            .style("min-width: 560px; max-width: 760px;"):
        ui.label(f"New {meta['title']}").classes("caption-box caption-box-sm")

        with ui.tabs().classes("w-full") as tabs:
            t_describe = ui.tab("Describe it", icon="edit_note")
            t_image = ui.tab("From an image", icon="image")
            t_copy = ui.tab("Copy an existing one", icon="content_copy")

        with ui.tab_panels(tabs, value=t_describe).classes("w-full"):

            # ---- PATH 1: describe it -------------------------------------
            with ui.tab_panel(t_describe):
                d_name = ui.input("Name").props("outlined dense autofocus").classes("w-full")
                d_desc = ui.textarea("Description").props("outlined autogrow") \
                    .classes("w-full q-mt-sm")
                ui.label(meta["describe_hint"]).classes("text-xs text-gray-500")

                def go_describe():
                    name = (d_name.value or "").strip()
                    if not name:
                        ui.notify("Give it a name.", type="warning")
                        return
                    desc = (d_desc.value or "").strip()
                    _create_from_scratch(state, kind, name, desc)
                    dlg.close()
                ui.button("Create", icon="add").props("unelevated no-caps") \
                    .classes("q-mt-md").on("click", lambda _: go_describe())

            # ---- PATH 2: from an image -----------------------------------
            with ui.tab_panel(t_image):
                dropped = {"path": None}
                i_name = ui.input("Name").props("outlined dense").classes("w-full")
                preview = ui.image().classes("q-mt-sm rounded-md") \
                    .style("max-height: 220px; display: none;")

                def on_up(e: UploadEventArguments):
                    p = _save_upload(e)
                    if p:
                        dropped["path"] = p
                        preview.set_source(p)
                        preview.style("max-height: 220px; display: block;")
                        ui.notify("Reference image ready.", type="positive")
                up = ui.upload(on_upload=on_up, auto_upload=True, max_files=1) \
                    .props('accept="image/*" flat bordered').classes("w-full q-mt-sm")
                up.classes("create-drop")
                ui.label(f"Drop or browse a reference image — {meta['reads']}.") \
                    .classes("text-xs text-gray-500")
                i_notes = ui.textarea("What should change from the picture? (optional)") \
                    .props("outlined autogrow").classes("w-full q-mt-sm")

                def go_image():
                    name = (i_name.value or "").strip()
                    if not name:
                        ui.notify("Give it a name.", type="warning")
                        return
                    if not dropped["path"]:
                        ui.notify("Drop or browse a reference image first.", type="warning")
                        return
                    _create_from_image(state, kind, name, dropped["path"],
                                       (i_notes.value or "").strip())
                    dlg.close()
                ui.button("Create from image", icon="add_photo_alternate") \
                    .props("unelevated no-caps").classes("q-mt-md") \
                    .on("click", lambda _: go_image())

            # ---- PATH 3: copy an existing one ----------------------------
            with ui.tab_panel(t_copy):
                sources = _existing(storage, series_id, kind)
                if not sources:
                    ui.label(f"No {meta['title']}s to copy yet — describe your first one, "
                             f"or start it from an image.").classes("text-sm q-mt-sm")
                else:
                    opts = {o.id: (o.name or o.id) for o in sources}
                    c_source = ui.select(opts, label=f"Copy which {meta['title']}?") \
                        .props("outlined dense").classes("w-full")
                    c_name = ui.input("New name").props("outlined dense").classes("w-full q-mt-sm")
                    c_diff = ui.textarea("What's different?").props("outlined autogrow") \
                        .classes("w-full q-mt-sm")
                    ui.label(meta["copy_hint"]).classes("text-xs text-gray-500")

                    def go_copy():
                        src = c_source.value
                        name = (c_name.value or "").strip()
                        if not src or not name:
                            ui.notify("Pick a source and give the copy a name.", type="warning")
                            return
                        _create_by_copy(state, kind, src, opts.get(src, src), name,
                                        (c_diff.value or "").strip())
                        dlg.close()
                    ui.button(f"Copy this {meta['title']}", icon="content_copy") \
                        .props("unelevated no-caps").classes("q-mt-md") \
                        .on("click", lambda _: go_copy())

        with ui.row().classes("w-full justify-end q-mt-sm"):
            ui.button("Cancel", icon="close").props("flat no-caps") \
                .on("click", lambda _: dlg.close())
    dlg.open()


# ---------------------------------------------------------------------------
# each path hands the coauthor one clear instruction
# ---------------------------------------------------------------------------
def _create_from_scratch(state, kind, name, description):
    if kind == "character":
        post_user_message(state,
            f"Create a new character named '{name}'.  Description: {description}  "
            f"Then create their BASE look (the identity every other look is built from) "
            f"and render its reference sheet.")
    elif kind == "setting":
        post_user_message(state,
            f"Create a new setting named '{name}'.  Description: {description}  "
            f"Then render a master background for it.")
    elif kind == "prop":
        post_user_message(state,
            f"Create a new prop named '{name}'.  Description: {description}  "
            f"Then render its reference art.")
    else:
        post_user_message(state,
            f"Create a new outfit (wardrobe) named '{name}'.  Description: {description}  "
            f"Then render its reference art.")


def _create_from_image(state, kind, name, image_path, notes):
    change = f"  Change from the picture: {notes}" if notes else ""
    ref = f"![reference]({image_path})"
    if kind == "character":
        post_user_message(state,
            f"Create a new character named '{name}' from this reference image: {ref}.  "
            f"Read their look off the picture as their BASE identity.{change}")
    elif kind == "setting":
        post_user_message(state,
            f"Create a new setting named '{name}' from this reference image: {ref}.{change}  "
            f"Use it as the master background.")
    elif kind == "prop":
        post_user_message(state,
            f"Create a new prop named '{name}' from this reference image: {ref}.{change}  "
            f"Use it as the prop's reference art.")
    else:
        post_user_message(state,
            f"Create a new outfit (wardrobe) named '{name}' from this reference image: {ref}.{change}  "
            f"Use it as the outfit's reference art.")


def _create_by_copy(state, kind, source_id, source_name, name, diff):
    what = f"  What's different: {diff}" if diff else "  (keep it the same, just renamed for now)"
    if kind == "character":
        post_user_message(state,
            f"Derive a new character named '{name}' from '{source_name}'.{what}")
    elif kind == "setting":
        post_user_message(state,
            f"Create a new setting named '{name}' by copying the setting '{source_name}' "
            f"(id: {source_id}).{what}")
    elif kind == "prop":
        post_user_message(state,
            f"Create a new prop named '{name}' by copying the prop '{source_name}' "
            f"(id: {source_id}).{what}")
    else:
        post_user_message(state,
            f"Create a new outfit named '{name}' by copying the outfit '{source_name}' "
            f"(id: {source_id}).{what}")


# ---------------------------------------------------------------------------
# THE LOOK COMPOSER: dress the base character in wardrobe and props
# ---------------------------------------------------------------------------
def compose_look_dialog(state: APPState, series_id: str, character_id: str):
    """Dress a character's BASE look in an outfit and props to make a new
    look — the studio builds the image FROM the base reference plus the
    wardrobe and prop art, with the descriptions carried to prevent drift."""
    from schema import Outfit, PropAsset, CharacterModel
    storage = state.storage
    character = storage.read_object(CharacterModel, {"series_id": series_id,
                                                     "character_id": character_id})
    outfits = _existing(storage, series_id, "outfit")
    props = _existing(storage, series_id, "prop")

    with ui.dialog() as dlg, ui.card().classes("soft-card") \
            .style("min-width: 560px; max-width: 760px;"):
        ui.label(f"Compose a look for {character.name if character else character_id}") \
            .classes("caption-box caption-box-sm")
        ui.markdown("Pick the wardrobe and props, name the look, and I'll build it "
                    "from the base character — the reference sheet, the outfit and "
                    "prop art, and their descriptions so nothing drifts.") \
            .classes("text-sm")

        name_in = ui.input("Look name").props("outlined dense autofocus") \
            .classes("w-full q-mt-sm")

        if not outfits:
            ui.label("No wardrobe yet — create an outfit first (the + on Wardrobe).") \
                .classes("text-sm text-amber-8 q-mt-sm")
        outfit_opts = {"": "— no outfit (keep the base look's clothes) —",
                       **{o.outfit_id: (o.name or o.outfit_id) for o in outfits}}
        outfit_sel = ui.select(outfit_opts, label="Wardrobe", value="") \
            .props("outlined dense").classes("w-full q-mt-sm")

        prop_opts = {p.prop_id: (p.name or p.prop_id) for p in props}
        prop_sel = ui.select(prop_opts, label="Props (carried in this look)",
                             multiple=True).props("outlined dense use-chips") \
            .classes("w-full q-mt-sm") if props else None
        if not props:
            ui.label("No props yet — that's fine, a look doesn't need one.") \
                .classes("text-xs text-gray-500")

        def go():
            name = (name_in.value or "").strip()
            if not name:
                ui.notify("Name the look.", type="warning")
                return
            outfit_id = outfit_sel.value or ""
            chosen_props = list(prop_sel.value) if (prop_sel and prop_sel.value) else []
            outfit_name = outfit_opts.get(outfit_id, "").strip("— ")
            prop_names = [prop_opts[p] for p in chosen_props]
            wearing = []
            if outfit_id:
                wearing.append(f"wearing the '{outfit_name}' outfit")
            if prop_names:
                wearing.append("carrying " + ", ".join(f"'{n}'" for n in prop_names))
            wearing_txt = " ".join(wearing) or "in a new look"
            post_user_message(state,
                f"Compose a new look named '{name}' for {character.name if character else character_id}, "
                f"{wearing_txt}.  Build it from the base look as the reference, dressed in the "
                f"chosen wardrobe and props, then render its reference sheet in the series style.")
            dlg.close()

        with ui.row().classes("w-full justify-end q-mt-md").style("gap: 8px;"):
            ui.button("Cancel", icon="close").props("flat no-caps") \
                .on("click", lambda _: dlg.close())
            ui.button("Compose the look", icon="checkroom").props("unelevated no-caps") \
                .on("click", lambda _: go())
    dlg.open()
