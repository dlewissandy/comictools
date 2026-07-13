"""
First-class studio assets: props and outfits (wardrobe).

Props dress settings, are carried by variants, and appear in panels.  Outfits
are worn by variants.  Both carry style-keyed reference art and provenance,
and both composite into renders exactly like every other reference object.

A character variant is CONSTRUCTED, like a panel: base character + outfit +
props (compose_character_variant), never re-described from scratch.
"""
import os
from agents import function_tool, RunContextWrapper
from loguru import logger

from gui.state import APPState
from storage.generic import GenericStorage
from schema import CharacterModel, CharacterVariant, ComicStyle, Outfit, PropAsset, Series
from agentic.tools.normalization import normalize_id
from agentic.tools.creator import creator


# ---------------------------------------------------------------- props
@function_tool
def create_prop(wrapper: RunContextWrapper[APPState], series_id: str, name: str, description: str) -> PropAsset | str:
    """
    Create a prop as a first-class studio asset: reusable in settings, carried
    by character variants, and shown in panels.   Check the catalog first
    (read_all_props / list_library_assets) so props are reused, not duplicated.

    Args:
        series_id: The series that will own the prop.
        name: A short (1-4 word) name, e.g. 'cracked crystal ball'.
        description: A visual description detailed enough for consistent
            depiction: size, materials, colors, wear.

    Returns:
        The created PropAsset, or an error message.
    """
    state: APPState = wrapper.context
    if state.storage.read_object(cls=Series, primary_key={"series_id": series_id}) is None:
        return f"Series '{series_id}' not found."
    prop = PropAsset(prop_id=normalize_id(name), series_id=series_id, name=name, description=description)
    result = creator(wrapper=wrapper, obj=prop, overwrite=True)
    return result


@function_tool
def read_all_props(wrapper: RunContextWrapper[APPState], series_id: str) -> list[PropAsset]:
    """
    List the prop assets of a series.

    Args:
        series_id: The series to list props for.
    """
    return wrapper.context.storage.read_all_objects(PropAsset, {"series_id": series_id}, order_by="name")


@function_tool
def update_prop_description(wrapper: RunContextWrapper[APPState], series_id: str, prop_id: str, description: str) -> str:
    """
    Update a prop's visual description.  NOTE: existing reference art becomes
    stale and should be re-rendered (generate_prop_reference).

    Args:
        series_id: The series that owns the prop.
        prop_id: The prop to update.
        description: The new visual description.
    """
    from agentic.tools.updater import update_attribute
    return update_attribute(wrapper, PropAsset, {"series_id": series_id, "prop_id": prop_id}, "description", description)


@function_tool
def delete_prop(wrapper: RunContextWrapper[APPState], series_id: str, prop_id: str) -> str:
    """
    Delete a prop asset.  You MUST ask for confirmation before using this tool.
    Settings/variants referencing it will keep a dangling id.

    Args:
        series_id: The series that owns the prop.
        prop_id: The prop to delete.
    """
    from agentic.tools.deleter import deleter
    return deleter(wrapper=wrapper, cls=PropAsset, primary_key={"series_id": series_id, "prop_id": prop_id})


# ---------------------------------------------------------------- outfits
@function_tool
def create_outfit(wrapper: RunContextWrapper[APPState], series_id: str, name: str, description: str) -> Outfit | str:
    """
    Create an outfit (wardrobe) as a first-class studio asset, wearable by any
    character variant.   Check the catalog first so wardrobe is reused.

    Args:
        series_id: The series that will own the outfit.
        name: A short (1-4 word) name, e.g. 'gnome disguise'.
        description: 1-2 paragraphs describing the attire: garments, materials,
            colors, condition, accessories.

    Returns:
        The created Outfit, or an error message.
    """
    state: APPState = wrapper.context
    if state.storage.read_object(cls=Series, primary_key={"series_id": series_id}) is None:
        return f"Series '{series_id}' not found."
    outfit = Outfit(outfit_id=normalize_id(name), series_id=series_id, name=name, description=description)
    return creator(wrapper=wrapper, obj=outfit, overwrite=True)


@function_tool
def read_all_outfits(wrapper: RunContextWrapper[APPState], series_id: str) -> list[Outfit]:
    """
    List the outfits (wardrobe) of a series.

    Args:
        series_id: The series to list outfits for.
    """
    return wrapper.context.storage.read_all_objects(Outfit, {"series_id": series_id}, order_by="name")


@function_tool
def update_outfit_description(wrapper: RunContextWrapper[APPState], series_id: str, outfit_id: str, description: str) -> str:
    """
    Update an outfit's attire description.  NOTE: existing reference art and
    variants wearing it become stale (re-render their reference sheets).

    Args:
        series_id: The series that owns the outfit.
        outfit_id: The outfit to update.
        description: The new attire description.
    """
    from agentic.tools.updater import update_attribute
    return update_attribute(wrapper, Outfit, {"series_id": series_id, "outfit_id": outfit_id}, "description", description)


@function_tool
def delete_outfit(wrapper: RunContextWrapper[APPState], series_id: str, outfit_id: str) -> str:
    """
    Delete an outfit asset.  You MUST ask for confirmation before using this
    tool.  Variants wearing it will keep a dangling id.

    Args:
        series_id: The series that owns the outfit.
        outfit_id: The outfit to delete.
    """
    from agentic.tools.deleter import deleter
    return deleter(wrapper=wrapper, cls=Outfit, primary_key={"series_id": series_id, "outfit_id": outfit_id})


# ------------------------------------------------------- composed variants
@function_tool
def compose_character_variant(wrapper: RunContextWrapper[APPState],
        series_id: str,
        character_id: str,
        name: str,
        outfit_id: str,
        prop_ids: list[str] = [],
        base_variant_id: str = "base",
        description: str = "",
    ) -> str:
    """
    Construct a character variant the way panels are constructed: from the
    BASE character plus wardrobe plus props.   Identity (race, gender, age,
    height, appearance, behavior) is inherited from the base variant; the
    outfit asset supplies the attire; props ride along.   Never re-describe a
    character to make a new look — compose it.

    Args:
        series_id: The series the character belongs to.
        character_id: The character to compose a variant for.
        name: The variant's name, e.g. 'gnome disguise', 'Sunday best'.
        outfit_id: The Outfit asset this variant wears (create_outfit first if
            it doesn't exist).
        prop_ids: Prop assets the variant carries.
        base_variant_id: The variant to inherit identity from (default 'base').
        description: Optional 1-2 sentences on what this look represents.

    Returns:
        A status message.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage

    base = storage.read_object(CharacterVariant, {"series_id": series_id, "character_id": character_id, "variant_id": base_variant_id})
    if base is None:
        return f"Base variant '{base_variant_id}' of '{character_id}' not found — create the character's base look first."
    outfit = storage.read_object(Outfit, {"series_id": series_id, "outfit_id": outfit_id})
    if outfit is None:
        return f"Outfit '{outfit_id}' not found in series '{series_id}' (create_outfit, or import it)."
    missing_props = [p for p in prop_ids if storage.read_object(PropAsset, {"series_id": series_id, "prop_id": p}) is None]
    if missing_props:
        return f"Prop(s) not found in series '{series_id}': {', '.join(missing_props)} (create_prop, or import them)."

    variant = CharacterVariant(
        variant_id=normalize_id(name),
        series_id=series_id,
        character_id=character_id,
        name=name,
        description=description or f"{base.description}  Wearing: {outfit.name}.",
        race=base.race, gender=base.gender, age=base.age, height=base.height,
        appearance=base.appearance, behavior=base.behavior,
        attire=outfit.description,
        images={},
        outfit_id=outfit_id,
        prop_ids=prop_ids,
    )
    result = creator(wrapper=wrapper, obj=variant, overwrite=True)
    if isinstance(result, str):
        return result
    state.is_dirty = True
    props_note = f", carrying {', '.join(prop_ids)}" if prop_ids else ""
    return (f"Composed variant '{name}' of {character_id}: base '{base_variant_id}' identity + "
            f"outfit '{outfit.name}'{props_note}.  Render its reference sheet with "
            f"create_styled_image_for_character_variant.")


@function_tool
def extract_outfit_from_variant(wrapper: RunContextWrapper[APPState],
        series_id: str, character_id: str, variant_id: str, outfit_name: str = "") -> str:
    """
    Retrofit an older variant into the composition model: lift its attire
    description out into a reusable Outfit asset and link the variant to it.
    The variant keeps looking exactly the same; its wardrobe just becomes a
    studio asset any character can wear.

    Args:
        series_id: The series the character belongs to.
        character_id: The character.
        variant_id: The variant whose attire to extract.
        outfit_name: Name for the new outfit (defaults to the variant's name).

    Returns:
        A status message.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    variant = storage.read_object(CharacterVariant, {"series_id": series_id, "character_id": character_id, "variant_id": variant_id})
    if variant is None:
        return f"Variant '{variant_id}' of '{character_id}' not found."
    if variant.outfit_id:
        return f"This variant already wears the outfit '{variant.outfit_id}'."
    if not (variant.attire or "").strip():
        return "This variant has no attire description to extract."

    # a nameless look falls back to its id — never an outfit named 'None';
    # and a name collision auto-suffixes instead of silently clobbering
    # another character's wardrobe
    base_name = (outfit_name or variant.name or variant_id).strip()
    name, nth = base_name, 2
    while storage.read_object(Outfit, {"series_id": series_id,
                                       "outfit_id": normalize_id(name)}) is not None:
        name = f"{base_name} {nth}"
        nth += 1
    outfit = Outfit(outfit_id=normalize_id(name), series_id=series_id, name=name, description=variant.attire)
    result = creator(wrapper=wrapper, obj=outfit, overwrite=True)
    if isinstance(result, str):
        return result
    variant.outfit_id = outfit.outfit_id
    storage.update_object(data=variant)
    state.is_dirty = True
    return (f"Extracted outfit '{name}' from {character_id}'s '{variant.name}' and linked it.  "
            f"Render its reference art with generate_outfit_reference so composites can use it.")


@function_tool
def dedupe_props(wrapper: RunContextWrapper[APPState], series_id: str,
                 confirm: bool = False) -> str:
    """
    Tidy the prop shop: find props that are the SAME THING under the same
    name (duplicates from repeated conjuring), keep the richest one, re-point
    every wardrobe look at the keeper, and strike the copies (they go to the
    wastebasket, restorable).   The first call only REPORTS the duplicates;
    call again with confirm=true to merge.

    Args:
        series_id: The series whose props to tidy.
        confirm: False to report; true to merge.

    Returns:
        The duplicate report, or a summary of the merge.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    props = storage.read_all_objects(PropAsset, {"series_id": series_id})
    groups: dict[str, list] = {}
    for p in props:
        groups.setdefault(normalize_id(p.name), []).append(p)
    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    if not dupes:
        return "The prop shop is tidy — no duplicate props."

    def richness(p):
        return (sum(1 for i in (p.images or {}).values() if i and os.path.exists(i)),
                len(p.description or ""))

    if not confirm:
        lines = [f"{len(dupes)} duplicated prop name(s):"]
        for k, group in dupes.items():
            keeper = max(group, key=richness)
            lines.append(f"  - '{group[0].name}' x{len(group)} — would keep "
                         f"{keeper.prop_id} ({richness(keeper)[0]} render(s)), "
                         f"strike {', '.join(p.prop_id for p in group if p is not keeper)}")
        lines.append("Call dedupe_props again with confirm=true to merge them "
                     "(struck copies go to the wastebasket).")
        return "\n".join(lines)

    merged, struck = 0, 0
    for k, group in dupes.items():
        keeper = max(group, key=richness)
        losers = [p for p in group if p is not keeper]
        loser_ids = {p.prop_id for p in losers}
        # every wardrobe look that carried a copy now carries the keeper
        for ch in storage.read_all_objects(CharacterModel, {"series_id": series_id}):
            for v in storage.read_all_objects(CharacterVariant, {
                    "series_id": series_id, "character_id": ch.character_id}):
                if any(pid in loser_ids for pid in (v.prop_ids or [])):
                    v.prop_ids = list(dict.fromkeys(
                        keeper.prop_id if pid in loser_ids else pid
                        for pid in (v.prop_ids or [])))
                    storage.update_object(data=v)
        for p in losers:
            storage.delete_object(cls=PropAsset, primary_key=p.primary_key)
            struck += 1
        merged += 1
    state.is_dirty = True
    return (f"Tidied the prop shop: {merged} name(s) merged, {struck} duplicate "
            f"prop(s) struck to the wastebasket (restorable).")
