"""
The studio asset library: browse every reusable asset across all series
(grouped by publisher) and import assets into another series.

Imports are copy-on-import with provenance (docs/asset-library.md): the copy
becomes a normal native asset of the target series, stamped with its origin so
drift can later be detected or reconciled.
"""
import json
import os
import shutil
from datetime import datetime, timezone

from agents import function_tool, RunContextWrapper
from loguru import logger

from gui.state import APPState
from storage.generic import GenericStorage
from storage.filepath import obj_to_path
from schema import CharacterModel, Setting, Series, AssetOrigin


def _copy_asset_tree(src_dir: str, dst_dir: str, source_series: str, target_series: str):
    """
    Copy an asset's folder tree and rewrite every JSON file inside so that
    series ids and stored image locators point at the target series.
    """
    shutil.copytree(src_dir, dst_dir)
    for root, _dirs, files in os.walk(dst_dir):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            path = os.path.join(root, fn)
            text = open(path).read()
            text = text.replace(f"series/{source_series}/", f"series/{target_series}/")
            text = text.replace(f'"{source_series}"', f'"{target_series}"')
            open(path, "w").write(text)


def _stamp_origin(json_path: str, source_series: str, asset_id: str):
    data = json.load(open(json_path))
    data["origin"] = {
        "series_id": source_series,
        "asset_id": asset_id,
        "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    json.dump(data, open(json_path, "w"), indent=2)


@function_tool
def list_library_assets(wrapper: RunContextWrapper[APPState], kind: str = "all") -> list[dict]:
    """
    Browse the studio's asset library: every character and setting across every
    series, with publisher attribution.   Use this to find assets worth reusing
    before creating new ones, and before importing.

    Args:
        kind: 'character', 'setting', or 'all' (default).

    Returns:
        A list of assets: {kind, id, name, description, series_id, series_name,
        publisher_id, origin}.
    """
    state: APPState = wrapper.context
    storage: GenericStorage = state.storage
    assets = []
    for series in storage.read_all_objects(Series):
        if kind in ("all", "character"):
            for c in storage.read_all_objects(CharacterModel, {"series_id": series.series_id}):
                assets.append({"kind": "character", "id": c.character_id, "name": c.name,
                               "description": c.description, "series_id": series.series_id,
                               "series_name": series.name, "publisher_id": series.publisher_id,
                               "origin": c.origin.model_dump() if c.origin else None})
        if kind in ("all", "setting"):
            for s in storage.read_all_objects(Setting, {"series_id": series.series_id}):
                assets.append({"kind": "setting", "id": s.setting_id, "name": s.name,
                               "description": s.description, "series_id": series.series_id,
                               "series_name": series.name, "publisher_id": series.publisher_id,
                               "origin": s.origin.model_dump() if s.origin else None})
    return assets


def _import_asset(storage, cls, source_series_id: str, asset_id: str, target_series_id: str, key_name: str):
    if storage.read_object(cls=Series, primary_key={"series_id": target_series_id}) is None:
        return f"Target series '{target_series_id}' not found."
    src_obj = storage.read_object(cls=cls, primary_key={"series_id": source_series_id, key_name: asset_id})
    if src_obj is None:
        return f"{cls.__name__} '{asset_id}' not found in series '{source_series_id}'."
    if storage.read_object(cls=cls, primary_key={"series_id": target_series_id, key_name: asset_id}) is not None:
        return f"'{asset_id}' already exists in '{target_series_id}'.  Delete or rename it first."

    src_dir = obj_to_path(src_obj, base_path=str(storage.base_path))
    tgt_obj = src_obj.model_copy(update={"series_id": target_series_id})
    dst_dir = obj_to_path(tgt_obj, base_path=str(storage.base_path))
    _copy_asset_tree(src_dir, dst_dir, source_series_id, target_series_id)

    # stamp provenance on the asset's own json (character.json / setting.json)
    json_name = "character.json" if cls is CharacterModel else "setting.json"
    _stamp_origin(os.path.join(dst_dir, json_name), source_series_id, asset_id)
    logger.info(f"Imported {cls.__name__} {asset_id} from {source_series_id} into {target_series_id}")
    return None  # success


@function_tool
def import_character(wrapper: RunContextWrapper[APPState], source_series_id: str, character_id: str, target_series_id: str) -> str:
    """
    Import a character from another series' collection into the target series —
    the character, all its variants (wardrobe), and their styled reference
    sheets are copied and stamped with their origin.   The copy then behaves
    like a native character of the target series and may drift deliberately.

    Args:
        source_series_id: The series the character currently lives in.
        character_id: The character to import.
        target_series_id: The series to import it into.

    Returns:
        A status message.
    """
    state: APPState = wrapper.context
    err = _import_asset(state.storage, CharacterModel, source_series_id, character_id, target_series_id, "character_id")
    if err:
        return err
    state.is_dirty = True
    return (f"Imported character '{character_id}' (with variants and reference sheets) into "
            f"'{target_series_id}'.  NOTE: if the target series uses styles the character has no "
            f"reference sheet for, create them (create_styled_image_for_character_variant).")


@function_tool
def import_setting(wrapper: RunContextWrapper[APPState], source_series_id: str, setting_id: str, target_series_id: str) -> str:
    """
    Import a setting from another series' collection into the target series —
    the setting, its props, and its master backgrounds are copied and stamped
    with their origin.

    Args:
        source_series_id: The series the setting currently lives in.
        setting_id: The setting to import.
        target_series_id: The series to import it into.

    Returns:
        A status message.
    """
    state: APPState = wrapper.context
    err = _import_asset(state.storage, Setting, source_series_id, setting_id, target_series_id, "setting_id")
    if err:
        return err
    state.is_dirty = True
    return (f"Imported setting '{setting_id}' (with props and master backgrounds) into "
            f"'{target_series_id}'.  NOTE: if the target series uses styles the setting has no "
            f"master background for, render them (generate_setting_background).")
